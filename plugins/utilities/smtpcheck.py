"""SMTP RCPT verification — probe whether a mailbox exists.

Works only where mail servers respond honestly. Gmail/Outlook/Yahoo/
iCloud/Proton always return 250 regardless, so verification is
"unknown" on those.
"""
import asyncio
import random
import re
import time

import httpx

from helpers.decorators import command
from utils.messages import Messages
from core.logger import setup_logger

logger = setup_logger(__name__)

DOH = "https://cloudflare-dns.com/dns-query"
DOH_HEADERS = {"accept": "application/dns-json"}

# Providers known to hide real answers
_OPAQUE_PROVIDERS = {
    "gmail.com", "googlemail.com",
    "outlook.com", "hotmail.com", "live.com", "msn.com",
    "yahoo.com", "yahoo.co.uk", "ymail.com", "rocketmail.com",
    "icloud.com", "me.com", "mac.com",
    "protonmail.com", "proton.me", "pm.me",
    "aol.com", "zoho.com", "yandex.com", "mail.ru",
    "gmx.com", "gmx.net", "fastmail.com", "tutanota.com",
    "qq.com", "163.com", "126.com",
}

# Sender used during the probe. Use a domain that won't get you blocked.
_PROBE_SENDER = "verify@example.com"

COOLDOWN = 15
_last_call: dict[int, float] = {}

_EMAIL_RX = re.compile(r"^([A-Za-z0-9._%+\-]+)@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})$")
_TIMEOUT = 12


# ────────────────────────── DNS ──────────────────────────

async def _mx_records(domain: str) -> list[str]:
    """Return MX hostnames sorted by preference."""
    try:
        async with httpx.AsyncClient(timeout=10, headers=DOH_HEADERS) as c:
            r = await c.get(DOH, params={"name": domain, "type": "MX"})
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning(f"MX lookup: {e}")
        return []

    answers = data.get("Answer") or []
    parsed = []
    for a in answers:
        d = str(a.get("data", "")).strip()
        # Format: "10 mail.example.com."
        parts = d.split()
        if len(parts) == 2 and parts[0].isdigit():
            parsed.append((int(parts[0]), parts[1].rstrip(".")))
        elif len(parts) == 1:
            parsed.append((0, parts[0].rstrip(".")))
    parsed.sort()
    return [h for _, h in parsed]


# ────────────────────────── SMTP ──────────────────────────

async def _read_smtp(reader: asyncio.StreamReader) -> tuple[int, str]:
    """Read one SMTP reply (handles multiline `250-...` continuations)."""
    lines = []
    while True:
        line = await asyncio.wait_for(reader.readline(), timeout=_TIMEOUT)
        if not line:
            break
        text = line.decode("utf-8", errors="replace").rstrip("\r\n")
        lines.append(text)
        if len(text) >= 4 and text[3] == " ":
            break
        if len(text) < 4:
            break
    if not lines:
        return 0, ""
    try:
        code = int(lines[-1][:3])
    except Exception:
        code = 0
    return code, " / ".join(lines)


async def _smtp_rcpt(mx_host: str, email: str) -> dict:
    """
    Connect to mx_host:25, run a RCPT probe for email.
    Returns dict with keys: code, stage, detail, catchall
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(mx_host, 25), timeout=_TIMEOUT
        )
    except Exception as e:
        return {"code": 0, "stage": "connect", "error": str(e)}

    result = {"code": 0, "stage": "?", "detail": "", "catchall": None}

    try:
        # Banner
        code, text = await _read_smtp(reader)
        if code != 220:
            result.update(code=code, stage="banner", detail=text)
            return result

        # HELO
        writer.write(b"HELO verifier.local\r\n")
        await writer.drain()
        code, text = await _read_smtp(reader)
        if code not in (250, 220):
            result.update(code=code, stage="helo", detail=text)
            return result

        # MAIL FROM
        writer.write(f"MAIL FROM:<{_PROBE_SENDER}>\r\n".encode())
        await writer.drain()
        code, text = await _read_smtp(reader)
        if code != 250:
            result.update(code=code, stage="mail_from", detail=text)
            return result

        # RCPT TO — the interesting one
        writer.write(f"RCPT TO:<{email}>\r\n".encode())
        await writer.drain()
        code, text = await _read_smtp(reader)
        result.update(code=code, stage="rcpt_to", detail=text)

        # If 250 → test a random bogus address to detect catch-all
        if code == 250:
            rand_user = "zzq" + "".join(
                random.choice("abcdefghijklmnopqrstuvwxyz0123456789")
                for _ in range(14)
            )
            bogus = f"{rand_user}@{email.split('@', 1)[1]}"
            writer.write(b"RSET\r\n")
            await writer.drain()
            await _read_smtp(reader)
            writer.write(f"MAIL FROM:<{_PROBE_SENDER}>\r\n".encode())
            await writer.drain()
            await _read_smtp(reader)
            writer.write(f"RCPT TO:<{bogus}>\r\n".encode())
            await writer.drain()
            code2, _ = await _read_smtp(reader)
            result["catchall"] = (code2 == 250)
    except Exception as e:
        result.update(code=0, stage="protocol", detail=str(e))
    finally:
        try:
            writer.write(b"QUIT\r\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

    return result


# ────────────────────────── commands ──────────────────────────

@command(r"verify (\S+)", "Verify whether a mailbox exists (SMTP probe)")
async def verify_handler(event):
    """
    Probe a mail server to check if a specific mailbox exists.

    Usage:
        .verify user@example.com

    Notes:
        - Real SMTP RCPT TO probe on port 25
        - Works for custom domains & small providers
        - Gmail / Outlook / Yahoo / iCloud always return 250,
          so the result is "unknown" for those
        - Port 25 must be open outbound on the host
        - Cooldown: 15s per user
    """
    raw = event.pattern_match.group(1).strip()
    m = _EMAIL_RX.match(raw)
    if not m:
        await event.edit(Messages.error("Give a full email: `user@domain.com`"))
        return

    local, domain = m.group(1), m.group(2).lower()

    # Cooldown
    now = time.time()
    wait = COOLDOWN - (now - _last_call.get(event.sender_id, 0))
    if wait > 0:
        await event.edit(Messages.warning(f"Cooldown — wait **{wait:.0f}s**."))
        return
    _last_call[event.sender_id] = now

    await event.edit(Messages.loading(f"Probing `{domain}`…"))

    # Opaque providers: skip the probe
    if domain in _OPAQUE_PROVIDERS:
        await event.edit(
            f"❓ **{raw}**\n\n"
            f"**Unknown.** `{domain}` is a large provider that always "
            f"returns `250` regardless of whether the mailbox exists. "
            f"Real verification isn't possible for these."
        )
        return

    mxs = await _mx_records(domain)
    if not mxs:
        await event.edit(Messages.error(f"No MX records for `{domain}`."))
        return

    # Try up to 2 MX hosts
    result = None
    tried = []
    for mx in mxs[:2]:
        r = await _smtp_rcpt(mx, raw)
        tried.append(f"`{mx}` → code {r.get('code')}")
        if r.get("stage") == "rcpt_to":
            result = (mx, r)
            break

    if result is None:
        # Couldn't reach port 25 on any MX
        details = "\n".join(f"• {t}" for t in tried)
        await event.edit(
            f"⚠️ **{raw}**\n\n"
            f"Couldn't complete the SMTP probe.\n"
            f"{details}\n\n"
            f"Common causes:\n"
            f"• Port 25 blocked by your host / ISP\n"
            f"• MX server refused the connection\n\n"
            f"Try `.mailcheck {raw}` for a domain-level answer."
        )
        return

    mx_host, r = result
    code = r["code"]

    if code == 250:
        if r.get("catchall"):
            await event.edit(
                f"❓ **{raw}**\n\n"
                f"**Unknown.** `{mx_host}` accepts *any* address at "
                f"`{domain}` (catch-all). The mailbox may or may not exist."
            )
        else:
            await event.edit(
                f"✅ **{raw}**\n\n"
                f"**Exists.** `{mx_host}` accepted the recipient.\n"
                f"_Code 250, no catch-all detected._"
            )
    elif code in (550, 551, 552, 553, 554):
        await event.edit(
            f"❌ **{raw}**\n\n"
            f"**Does not exist.** `{mx_host}` rejected the recipient.\n"
            f"_Code {code}._"
        )
    elif 400 <= code < 500:
        await event.edit(
            f"⚠️ **{raw}**\n\n"
            f"**Temporary.** `{mx_host}` returned a soft failure "
            f"(greylisted / rate-limited).\n"
            f"_Code {code}. Try again in a minute._"
        )
    else:
        await event.edit(
            f"❓ **{raw}**\n\n"
            f"**Inconclusive.** `{mx_host}` returned code `{code}` "
            f"at stage `{r.get('stage')}`."
        )


@command("port25", "Check if outbound port 25 is open on this host")
async def port25_handler(event):
    """
    Test whether this host can reach the internet on port 25.

    Usage:
        .port25

    Tries a TCP connection to a few well-known mail servers.
    If all fail, `.verify` won't work on this host.
    """
    await event.edit(Messages.loading("Testing outbound port 25…"))

    targets = [
        ("gmail-smtp-in.l.google.com", 25),
        ("mx1.mail.yahoo.com", 25),
    ]
    results = []
    for host, port in targets:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=8
            )
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            results.append(f"✅ `{host}:{port}` — reachable")
        except Exception as e:
            results.append(f"❌ `{host}:{port}` — {type(e).__name__}")

    if all(r.startswith("✅") for r in results):
        verdict = "🟢 Port 25 is open. `.verify` should work."
    elif any(r.startswith("✅") for r in results):
        verdict = "🟡 Partial. `.verify` may work sometimes."
    else:
        verdict = "🔴 Port 25 blocked. `.verify` won't work here."

    await event.edit(verdict + "\n\n" + "\n".join(results))


@command("verifyhelp", "SMTP verification help")
async def verifyhelp_handler(event):
    """Usage: `.verifyhelp`"""
    await event.edit(
        "🔬 **SMTP VERIFY**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "• `.verify user@domain.com` — probe mailbox\n"
        "• `.port25` — test outbound port 25\n\n"
        "**Works for:** custom domains, small providers, universities.\n"
        "**Unknown for:** Gmail, Outlook, Yahoo, iCloud, Proton, …\n"
        "**Needs:** port 25 open outbound on the host.\n\n"
        "Cooldown: 15s per user."
    )