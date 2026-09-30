"""Identity — info, whois, getid."""
import html
from datetime import datetime, timezone

from telethon import functions

from helpers.decorators import command
from utils.messages import Messages
from core.logger import setup_logger

logger = setup_logger(__name__)


def _esc(s) -> str:
    return html.escape(str(s)) if s is not None else "—"


async def _resolve(client, event, arg):
    """Resolve a user from arg (id/@user), reply, or sender."""
    if arg:
        arg = arg.strip()
        try:
            if arg.startswith("@"):
                return await client.get_entity(arg)
            if arg.lstrip("-").isdigit():
                return await client.get_entity(int(arg))
        except Exception as e:
            logger.warning(f"resolve '{arg}' failed: {e}")
            return None

    if event.is_reply:
        replied = await event.get_reply_message()
        if replied:
            try:
                return await replied.get_sender()
            except Exception:
                return None

    try:
        return await event.get_sender()
    except Exception:
        return None


def _fmt_dt(dt) -> str:
    if dt is None:
        return "—"
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    return str(dt)


# ─────────────────────── commands ───────────────────────

@command(r"info(?:\s+(.+))?", "Show user information")
async def info_handler(event):
    """
    Show detailed information about a user.

    Usage:
        .info                  (reply to a user)
        .info <user_id>
        .info @username

    Notes:
        - Falls back to your own info if no reply/arg
        - Never reveals phone numbers (privacy-safe)
    """
    arg = event.pattern_match.group(1)
    user = await _resolve(event.client, event, arg)
    if user is None:
        await event.edit(Messages.error("Couldn't resolve user."))
        return

    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "—"

    lines = [f"👤 **{_esc(name)}**\n"]
    lines.append(f"**ID:** `{user.id}`")
    if getattr(user, "username", None):
        lines.append(f"**Username:** @{user.username}")
    lines.append(f"**Bot:** {'Yes' if getattr(user, 'bot', False) else 'No'}")
    lines.append(f"**Verified:** {'Yes' if getattr(user, 'verified', False) else 'No'}")
    lines.append(f"**Restricted:** {'Yes' if getattr(user, 'restricted', False) else 'No'}")
    lines.append(f"**Scam:** {'Yes' if getattr(user, 'scam', False) else 'No'}")
    lines.append(f"**Premium:** {'Yes' if getattr(user, 'premium', False) else 'No'}")

    await event.edit("\n".join(lines))


@command(r"whois(?:\s+(.+))?", "Detailed user or chat lookup")
async def whois_handler(event):
    """
    Detailed lookup with bio, status, common chats count.

    Usage:
        .whois                 (reply)
        .whois <user_id>
        .whois @username

    Notes:
        - Never reveals phone numbers
    """
    arg = event.pattern_match.group(1)

    if not arg and not event.is_reply:
        target = await event.get_chat()
        is_chat = True
        user = None
    else:
        user = await _resolve(event.client, event, arg)
        target = user
        is_chat = False

    if target is None:
        await event.edit(Messages.error("Couldn't resolve."))
        return

    lines = ["🔎 **Whois**\n"]

    if is_chat:
        title = getattr(target, "title", None) or "—"
        lines.append(f"**Title:** {_esc(title)}")
        lines.append(f"**Chat ID:** `{target.id}`")
        if getattr(target, "username", None):
            lines.append(f"**Username:** @{target.username}")
        lines.append(f"**Type:** {type(target).__name__}")
        await event.edit("\n".join(lines))
        return

    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "—"
    lines.append(f"**Name:** {_esc(name)}")
    lines.append(f"**ID:** `{user.id}`")
    if getattr(user, "username", None):
        lines.append(f"**Username:** @{user.username}")

    try:
        full = await event.client(functions.users.GetFullUserRequest(id=user.id))
        fu = full.full_user
        if fu.about:
            lines.append(f"**Bio:** {_esc(fu.about)}")
        if getattr(fu, "common_chats_count", None):
            lines.append(f"**Common chats:** {fu.common_chats_count}")
    except Exception as e:
        logger.warning(f"full user failed: {e}")

    status = getattr(user, "status", None)
    if status is not None:
        lines.append(
            f"**Status:** {type(status).__name__.replace('UserStatus', '')}"
        )

    await event.edit("\n".join(lines))


@command(r"getid(?:\s+(.+))?", "Show IDs for user / chat / message")
async def getid_handler(event):
    """
    Show all relevant IDs for the current context.

    Usage:
        .getid                 (context: chat + sender)
        .getid <user_id>
        .getid @username

    Notes:
        - If replying: shows replied user's ID
        - Always shows current chat ID
    """
    arg = event.pattern_match.group(1)
    lines = ["🆔 **IDs**\n"]

    try:
        chat = await event.get_chat()
        chat_title = (
            getattr(chat, "title", None)
            or getattr(chat, "first_name", "Private")
        )
        lines.append(f"**Chat:** {_esc(chat_title)}")
        lines.append(f"**Chat ID:** `{event.chat_id}`")
    except Exception:
        pass

    if arg:
        user = await _resolve(event.client, event, arg)
        if user:
            lines.append(f"**User ID:** `{user.id}`")
            if getattr(user, "username", None):
                lines.append(f"**Username:** @{user.username}")
    elif event.is_reply:
        replied = await event.get_reply_message()
        if replied:
            try:
                sender = await replied.get_sender()
                if sender:
                    lines.append(f"**Replied user ID:** `{sender.id}`")
            except Exception:
                pass
            lines.append(f"**Replied message ID:** `{replied.id}`")
    else:
        sender = await event.get_sender()
        if sender:
            lines.append(f"**Your ID:** `{sender.id}`")

    lines.append(f"**This message ID:** `{event.message.id}`")
    await event.edit("\n".join(lines))


@command("chatid", "Show the current chat ID")
async def chatid_handler(event):
    """
    Show only the current chat ID.

    Usage:
        .chatid
    """
    await event.edit(f"🆔 **Chat ID:** `{event.chat_id}`")


@command("identityhelp", "Identity module help")
async def identity_help(event):
    """
    Show all Identity commands.

    Usage:
        .identityhelp
    """
    await event.edit(
        "🪪 **IDENTITY**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "• `.info` — user basic info\n"
        "• `.whois` — detailed lookup (bio, status)\n"
        "• `.getid` — all relevant IDs\n"
        "• `.chatid` — current chat ID only\n\n"
        "**Targets:** reply, `<id>`, or `@username`\n"
        "**Fallback:** self / current chat\n\n"
        "🔒 Phone numbers are never displayed.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )