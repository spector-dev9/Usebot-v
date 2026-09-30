"""Mailcheck — validate email domains via DNS-over-HTTPS (Cloudflare)."""
import re

import httpx

from helpers.decorators import command
from utils.messages import Messages
from core.logger import setup_logger

logger = setup_logger(__name__)

DOH = "https://cloudflare-dns.com/dns-query"
HEADERS = {"accept": "application/dns-json"}
TIMEOUT = 12

# Common disposable / throwaway domains (curated, not exhaustive)
_DISPOSABLE = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "10minutemail.com",
    "throwawaymail.com", "yopmail.com", "trashmail.com", "sharklasers.com",
    "getnada.com", "dispostable.com", "maildrop.cc", "mintemail.com",
    "fakeinbox.com", "tempinbox.com", "mailnesia.com", "spamgourmet.com",
    "tempr.email", "discard.email", "mohmal.com", "emailondeck.com",
    "moakt.com", "tempmail.net", "1secmail.com", "1secmail.org",
    "1secmail.net", "email-temp.com", "mytrashmail.com", "throwam.com",
    "getairmail.com", "spambog.com", "mailcatch.com", "filzmail.com",
    "mailnull.com", "trashmail.net", "trbvm.com", "temp-mail.org",
    "temp-mail.io", "tempmailo.com", "burnermail.io", "anonaddy.com",
    "33mail.com", "spam4.me", "grr.la", "guerrillamailblock.com",
}

# Domains that look like typos of common providers
_COMMON_TYPOS = {
    "gmial.com": "gmail.com", "gmai.com": "gmail.com", "gmaill.com": "gmail.com",
    "gmail.co": "gmail.com", "gmail.con": "gmail.com", "gmail.cm": "gmail.com",
    "gnail.com": "gmail.com", "gamil.com": "gmail.com",
    "yaho.com": "yahoo.com", "yahooo.com": "yahoo.com", "yahho.com": "yahoo.com",
    "hotmial.com": "hotmail.com", "hotmai.com": "hotmail.com",
    "hotmal.com": "hotmail.com", "hotmail.co": "hotmail.com",
    "outlok.com": "outlook.com", "outloo.com": "outlook.com",
    "outllook.com": "outlook.com",
    "iclod.com": "icloud.com", "iclould.com": "icloud.com",
    "protonmai.com": "protonmail.com", "protonmal.com": "protonmail.com",
}

_EMAIL_RX = re.compile(
    r"^[A-Za-z0-9._%+\-]+@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})$"
)
_DOMAIN_RX = re.compile(r"^[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


# ────────────────────────── DNS helpers ──────────────────────────

async def _dns_query(name: str, rtype: str) -> list[str]:
    """Query Cloudflare DNS-over-HTTPS. Returns list of record data strings."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as c:
            r = await c.get(DOH, params={"name": name, "type": rtype})
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning(f"dns {rtype} {name}: {e}")
        return []

    answers = data.get("Answer") or []
    return [str(a.get("data", "")) for a in answers if a.get("data")]


def _extract_domain(raw: str) -> str | None:
    """Return domain from email or plain domain, or None if malformed."""
    raw = raw.strip().lower()
    m = _EMAIL_RX.match(raw)
    if m:
        return m.group(1)
    if _DOMAIN_RX.match(raw):
        return raw
    return None


async def _analyze(domain: str) -> dict:
    """Gather DNS facts for a domain."""
    mx = await _dns_query(domain, "MX")
    txt = await _dns_query(domain, "TXT")
    dmarc = await _dns_query(f"_dmarc.{domain}", "TXT")
    a = await _dns_query(domain, "A")

    spf = next(
        (t for t in txt if "v=spf1" in t.lower()),
        None,
    )
    dmarc_record = next(
        (t for t in dmarc if "v=dmarc1" in t.lower()),
        None,
    )

    return {
        "domain": domain,
        "mx": mx,
        "a": a,
        "spf": spf,
        "dmarc": dmarc_record,
    }


def _verdict(domain: str, facts: dict) -> tuple[str, str]:
    """Return (emoji_verdict, short_reason)."""
    if domain in _DISPOSABLE:
        return "⚠️", "Disposable / throwaway domain"
    if domain in _COMMON_TYPOS:
        return "❓", f"Looks like a typo of `{_COMMON_TYPOS[domain]}`"
    if not facts["mx"]:
        if facts["a"]:
            return "⚠️", "No MX records (can't receive mail directly)"
        return "❌", "Domain does not resolve"
    return "✅", "Domain can receive email"


# ────────────────────────── commands ──────────────────────────

@command(r"mailcheck (\S+)", "Check if an email domain can receive mail")
async def mailcheck_handler(event):
    """
    Validate an email address by inspecting its domain's DNS.

    Usage:
        .mailcheck <email>
        .mailcheck <domain>

    Examples:
        .mailcheck user@gmail.com
        .mailcheck example.com
        .mailcheck x@mailinator.com

    Checks:
        - MX records (can the domain receive mail?)
        - A record (does the domain exist?)
        - SPF policy
        - DMARC policy
        - Disposable / typo domain list

    Notes:
        - Safe: uses Cloudflare DNS-over-HTTPS (no ToS issues)
        - Doesn't verify the mailbox exists, only the domain
    """
    raw = event.pattern_match.group(1).strip()
    domain = _extract_domain(raw)

    if not domain:
        await event.edit(Messages.error(
            "Invalid email or domain.\n"
            "Try `.mailcheck user@example.com` or `.mailcheck example.com`"
        ))
        return

    await event.edit(Messages.loading(f"Checking `{domain}`…"))

    facts = await _analyze(domain)
    verdict, reason = _verdict(domain, facts)

    lines = [f"{verdict} **{domain}**", f"_{reason}_", ""]

    # MX
    if facts["mx"]:
        lines.append(f"**MX ({len(facts['mx'])} record{'s' if len(facts['mx'])>1 else ''})**")
        for rec in facts["mx"][:5]:
            lines.append(f"  `{rec}`")
        if len(facts["mx"]) > 5:
            lines.append(f"  _…+{len(facts['mx'])-5} more_")
    else:
        lines.append("**MX:** _none_")

    # A
    if facts["a"]:
        lines.append(f"\n**A:** `{facts['a'][0]}`")

    # SPF
    if facts["spf"]:
        spf = facts["spf"].strip('"')
        if len(spf) > 100:
            spf = spf[:100] + "…"
        lines.append(f"\n**SPF:** `{spf}`")

    # DMARC
    if facts["dmarc"]:
        dm = facts["dmarc"].strip('"')
        if len(dm) > 100:
            dm = dm[:100] + "…"
        lines.append(f"**DMARC:** `{dm}`")

    await event.edit("\n".join(lines))


@command(r"mx (\S+)", "Show MX records for a domain")
async def mx_handler(event):
    """
    List MX records for a domain.

    Usage:
        .mx gmail.com
        .mx example.com
    """
    raw = event.pattern_match.group(1).strip()
    domain = _extract_domain(raw)
    if not domain:
        await event.edit(Messages.error("Invalid domain."))
        return

    await event.edit(Messages.loading(f"Querying MX for `{domain}`…"))
    mx = await _dns_query(domain, "MX")

    if not mx:
        await event.edit(Messages.info(f"No MX records for `{domain}`."))
        return

    lines = [f"📬 **MX — {domain}**\n"]
    for rec in mx:
        lines.append(f"• `{rec}`")
    await event.edit("\n".join(lines))


@command(r"spf (\S+)", "Show SPF record for a domain")
async def spf_handler(event):
    """
    Show the SPF record for a domain.

    Usage:
        .spf gmail.com
    """
    raw = event.pattern_match.group(1).strip()
    domain = _extract_domain(raw)
    if not domain:
        await event.edit(Messages.error("Invalid domain."))
        return

    await event.edit(Messages.loading("Querying SPF…"))
    txt = await _dns_query(domain, "TXT")
    spf = next((t for t in txt if "v=spf1" in t.lower()), None)

    if not spf:
        await event.edit(Messages.info(f"No SPF record for `{domain}`."))
        return
    await event.edit(f"🛡 **SPF — {domain}**\n`{spf.strip(chr(34))}`")


@command(r"dmarc (\S+)", "Show DMARC record for a domain")
async def dmarc_handler(event):
    """
    Show the DMARC policy for a domain.

    Usage:
        .dmarc gmail.com
    """
    raw = event.pattern_match.group(1).strip()
    domain = _extract_domain(raw)
    if not domain:
        await event.edit(Messages.error("Invalid domain."))
        return

    await event.edit(Messages.loading("Querying DMARC…"))
    recs = await _dns_query(f"_dmarc.{domain}", "TXT")
    dm = next((t for t in recs if "v=dmarc1" in t.lower()), None)

    if not dm:
        await event.edit(Messages.info(f"No DMARC record for `{domain}`."))
        return
    await event.edit(f"🛡 **DMARC — {domain}**\n`{dm.strip(chr(34))}`")


@command("disposable", "List known disposable email domains")
async def disposable_handler(event):
    """Usage: `.disposable`"""
    doms = sorted(_DISPOSABLE)
    body = "\n".join(f"• `{d}`" for d in doms)
    await event.edit(f"🗑 **{len(doms)} disposable domains**\n\n{body}")


@command("mailhelp", "Mailcheck help")
async def mailhelp_handler(event):
    """Usage: `.mailhelp`"""
    await event.edit(
        "📧 **MAILCHECK**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "• `.mailcheck <email|domain>` — full check\n"
        "• `.mx <domain>` — MX records\n"
        "• `.spf <domain>` — SPF record\n"
        "• `.dmarc <domain>` — DMARC record\n"
        "• `.disposable` — disposable list\n\n"
        "Safe: DNS-over-HTTPS (Cloudflare).\n"
        "No ToS issues, no API keys."
    )