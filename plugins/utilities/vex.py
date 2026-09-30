"""Vex — wild pack: spam, fake, troll, snipe."""
import asyncio
import html
import random
from collections import defaultdict, deque

from telethon import events

from helpers.decorators import command, sudo_only, listener
from utils.messages import Messages
from Config.settings import Config
from core.logger import setup_logger

logger = setup_logger(__name__)


# ══════════════════════════════════════════════════════════════════
#  SPAM
# ══════════════════════════════════════════════════════════════════

_spam_active: dict[int, bool] = {}
_SPAM_MAX = 100          # hard cap per invocation
_SPAM_DELAY = 0.35       # seconds between sends


@command(r"spam (\d+) (.+)", "Spam a message N times")
@sudo_only
async def spam_handler(event):
    """
    Send a message N times in the current chat.

    Rate-limited on purpose: 0.35s between sends so you
    don't trip Telegram's floodwaiter.

    Usage:
        .spam <count> <text>

    Examples:
        .spam 5 hello
        .spam 20 ZEROX

    Notes:
        - Count capped at 100 per run
        - Use .spamstop to abort mid-run
        - Sudo only
    """
    count = int(event.pattern_match.group(1))
    text = event.pattern_match.group(2)

    if count < 1:
        await event.edit(Messages.error("Count must be ≥ 1."))
        return
    if count > _SPAM_MAX:
        await event.edit(Messages.error(f"Count capped at {_SPAM_MAX}."))
        return

    sender_id = event.sender_id
    _spam_active[sender_id] = True

    await event.delete()

    sent = 0
    try:
        for i in range(count):
            if not _spam_active.get(sender_id, False):
                break
            try:
                await event.client.send_message(event.chat_id, text)
                sent += 1
            except Exception as e:
                logger.warning(f"spam send {i+1} failed: {e}")
                break
            await asyncio.sleep(_SPAM_DELAY)
    finally:
        _spam_active[sender_id] = False

    note = await event.client.send_message(
        event.chat_id, f"✅ Spam done — sent {sent}/{count}"
    )
    await asyncio.sleep(4)
    try:
        await note.delete()
    except Exception:
        pass


@command("spamstop", "Stop an ongoing spam")
@sudo_only
async def spamstop_handler(event):
    """
    Stop your running `.spam` job.

    Usage:
        .spamstop
    """
    _spam_active[event.sender_id] = False
    await event.edit(Messages.success("Spam stopped."))


# ══════════════════════════════════════════════════════════════════
#  FAKE
# ══════════════════════════════════════════════════════════════════

def _esc(s: str) -> str:
    return html.escape(s or "")


@command(r"fakeme (.+)", "Send text with your name as a header")
async def fakeme_handler(event):
    """
    Send a message styled with your display name as a fake
    header, then the text below — reads like a forwarded quote.

    Usage:
        .fakeme <text>

    Examples:
        .fakeme hello world
    """
    text = event.pattern_match.group(1)
    me = await event.client.get_me()
    display = f"{me.first_name or ''} {me.last_name or ''}".strip() or "Me"

    body = f"<b>{_esc(display)}</b>\n{_esc(text)}"
    await event.edit(body, parse_mode="html")


@command(r"faketag (\S+) (.+)", "Fake a mention header")
async def faketag_handler(event):
    """
    Send text with an @username-style header.

    Usage:
        .faketag <handle> <text>

    Examples:
        .faketag @someone hello there
    """
    handle = event.pattern_match.group(1)
    text = event.pattern_match.group(2)

    if not handle.startswith("@"):
        handle = "@" + handle

    body = f"<b>{_esc(handle)}</b>\n{_esc(text)}"
    await event.edit(body, parse_mode="html")


@command(r"fakeid (\d+) (.+)", "Fake a user-id header")
async def fakeid_handler(event):
    """
    Send text with a fake numeric user-id header.

    Usage:
        .fakeid <id> <text>

    Examples:
        .fakeid 12345 hello
    """
    uid = event.pattern_match.group(1)
    text = event.pattern_match.group(2)

    body = f"<b>[id {_esc(uid)}]</b>\n{_esc(text)}"
    await event.edit(body, parse_mode="html")


@command(r"fakechat (.+?) \| (.+)", "Fake a chat-title header")
async def fakechat_handler(event):
    """
    Send text with a fake chat title header (split by |).

    Usage:
        .fakechat <title> | <text>

    Examples:
        .fakechat Group Announcement | hello everyone
    """
    title = event.pattern_match.group(1)
    text = event.pattern_match.group(2)

    body = f"<b>{_esc(title)}</b>\n{_esc(text)}"
    await event.edit(body, parse_mode="html")


# ══════════════════════════════════════════════════════════════════
#  TROLL
# ══════════════════════════════════════════════════════════════════

_LEET_TABLE = str.maketrans({
    "a": "4", "A": "4",
    "e": "3", "E": "3",
    "i": "1", "I": "1",
    "o": "0", "O": "0",
    "s": "5", "S": "5",
    "t": "7", "T": "7",
    "b": "8", "B": "8",
    "g": "9", "G": "9",
})


@command(r"reverse (.+)", "Reverse text")
async def reverse_handler(event):
    """
    Reverse a string.

    Usage:
        .reverse <text>
    """
    text = event.pattern_match.group(1)
    await event.edit(text[::-1])


@command(r"leet (.+)", "Convert to 1337 sp34k")
async def leet_handler(event):
    """
    Convert text to leetspeak.

    Usage:
        .leet <text>
    """
    text = event.pattern_match.group(1)
    await event.edit(text.translate(_LEET_TABLE))


def _zalgo(text: str, intensity: int = 3) -> str:
    """Add combining diacritics to each character."""
    ranges = [
        (0x0300, 0x036F),  # combining diacritical marks
        (0x1AB0, 0x1AFF),  # combining diacritical marks extended
    ]
    out = []
    for ch in text:
        out.append(ch)
        if ch.strip():
            for _ in range(random.randint(0, intensity)):
                lo, hi = random.choice(ranges)
                out.append(chr(random.randint(lo, hi)))
    return "".join(out)


@command(r"zalgo (.+)", "Zalgo-ify text")
async def zalgo_handler(event):
    """
    Turn text into cursed zalgo text.

    Usage:
        .zalgo <text>
    """
    text = event.pattern_match.group(1)
    await event.edit(_zalgo(text))


def _uwu(text: str) -> str:
    subs = [
        ("r", "w"), ("R", "W"),
        ("l", "w"), ("L", "W"),
        ("th", "f"), ("TH", "F"),
        ("ove", "uv"), ("OVE", "UV"),
    ]
    out = text
    for a, b in subs:
        out = out.replace(a, b)
    faces = ["(・`ω´・)", "uwu", "owo", "UwU", ">w<", "^w^"]
    return f"{out} {random.choice(faces)}"


@command(r"uwu (.+)", "UwU-ify text")
async def uwu_handler(event):
    """
    Convert text to uwu-speak.

    Usage:
        .uwu <text>
    """
    text = event.pattern_match.group(1)
    await event.edit(_uwu(text))


@command(r"clap (.+)", "Clap between words")
async def clap_handler(event):
    """
    Insert clap emojis between words.

    Usage:
        .clap <text>

    Examples:
        .clap this is important
    """
    text = event.pattern_match.group(1)
    words = text.split()
    await event.edit(" 👏 ".join(words) + " 👏")


# ══════════════════════════════════════════════════════════════════
#  SNIPE
# ══════════════════════════════════════════════════════════════════

_msg_cache: dict[int, deque] = defaultdict(lambda: deque(maxlen=300))
_sniped: dict[int, deque] = defaultdict(lambda: deque(maxlen=10))


@listener(events.NewMessage())
async def _cache_watcher(event):
    """Cache every message so we can snipe it if deleted."""
    text = event.raw_text
    if not text:
        return

    sender = await event.get_sender()
    sender_name = ""
    if sender:
        sender_name = (
            f"{getattr(sender, 'first_name', '') or ''} "
            f"{getattr(sender, 'last_name', '') or ''}"
        ).strip() or getattr(sender, "username", "") or str(event.sender_id)

    _msg_cache[event.chat_id].append({
        "id": event.message.id,
        "sender_id": event.sender_id,
        "sender_name": sender_name,
        "text": text,
    })


@listener(events.MessageDeleted())
async def _delete_watcher(event):
    """Move deleted messages from cache into the snipe buffer."""
    chat_id = event.chat_id
    if chat_id is None:
        return

    cache = _msg_cache.get(chat_id)
    if not cache:
        return

    for msg_id in event.deleted_ids:
        for entry in list(cache):
            if entry["id"] == msg_id:
                _sniped[chat_id].append(entry)
                try:
                    cache.remove(entry)
                except ValueError:
                    pass
                break


@command(r"snipe(?:\s+(\d+))?", "Show a recently deleted message")
async def snipe_handler(event):
    """
    Show a recently deleted message from this chat.

    Usage:
        .snipe              latest deleted
        .snipe <n>          nth most recent (1 = latest)

    Examples:
        .snipe
        .snipe 3

    Notes:
        - Only snipes messages seen by the userbot since startup
        - Cache is per-chat, up to 10 deletions remembered
    """
    n = int(event.pattern_match.group(1) or 1)
    chat_id = event.chat_id
    entries = list(_sniped.get(chat_id, []))

    if not entries:
        await event.edit(Messages.info("Nothing to snipe."))
        return
    if n < 1 or n > len(entries):
        await event.edit(Messages.error(f"Only {len(entries)} sniped."))
        return

    entry = entries[-n]

    body = "🔫 **Sniped**\n"
    body += Messages.format_key_value("Sender", entry["sender_name"] or "—") + "\n"
    body += Messages.format_key_value("Text", entry["text"])
    await event.edit(body)


# ══════════════════════════════════════════════════════════════════
#  HELP
# ══════════════════════════════════════════════════════════════════

@command("vexhelp", "Show Vex module help")
async def vex_help_handler(event):
    """
    Show all commands in the Vex wild pack.

    Usage:
        .vexhelp
    """
    help_text = (
        "🔥 **VEX — WILD PACK**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "**🌪 SPAM** _(sudo)_\n"
        "• `.spam <n> <text>` — send N times\n"
        "• `.spamstop` — abort running spam\n\n"
        "**🎭 FAKE**\n"
        "• `.fakeme <text>` — your name as header\n"
        "• `.faketag <@handle> <text>` — fake mention\n"
        "• `.fakeid <id> <text>` — fake id header\n"
        "• `.fakechat <title> | <text>` — fake chat title\n\n"
        "**🎮 TROLL**\n"
        "• `.reverse <text>` — abc → cba\n"
        "• `.leet <text>` — l33t sp34k\n"
        "• `.zalgo <text>` — cursed text\n"
        "• `.uwu <text>` — uwu-ify\n"
        "• `.clap <text>` — 👏 clap 👏 between 👏 words\n\n"
        "**🔫 SNIPE**\n"
        "• `.snipe` — latest deleted\n"
        "• `.snipe <n>` — nth most recent\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 Sudo required: spam only"
    )
    await event.edit(help_text)