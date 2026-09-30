"""AFK — away status with automatic reply."""
import asyncio
import time

from telethon import events
from sqlalchemy import select

from helpers.decorators import command, listener
from utils.messages import Messages
from utils.formatters import Formatters
from Config.settings import Config
from core.logger import setup_logger
from database.connection import get_session
from database.models import Afk

logger = setup_logger(__name__)


# Messages sent BY the AFK auto-reply — auto-clear must ignore these.
# Keyed by (chat_id, message_id). Bounded to avoid leaks.
_afk_reply_ids: set[tuple[int, int]] = set()
_AFK_REPLY_ID_MAX = 500


def _mark_afk_reply(chat_id: int, msg_id: int) -> None:
    _afk_reply_ids.add((chat_id, msg_id))
    if len(_afk_reply_ids) > _AFK_REPLY_ID_MAX:
        # Drop oldest
        for _ in range(len(_afk_reply_ids) - _AFK_REPLY_ID_MAX):
            _afk_reply_ids.pop()


def _is_afk_reply(chat_id: int, msg_id: int) -> bool:
    key = (chat_id, msg_id)
    if key in _afk_reply_ids:
        _afk_reply_ids.discard(key)
        return True
    return False


# ─────────────────────── commands ───────────────────────

@command("afk(?:\\s+(.*))?", "Set AFK status")
async def afk_set(event):
    """
    Set your AFK status. Anyone who messages or mentions you
    will get an automatic reply with your reason.

    Usage:
        .afk                set AFK, no reason
        .afk <reason>       set AFK with a reason

    Examples:
        .afk
        .afk lunch
        .afk in a meeting

    Notes:
        - Replying or sending any message clears AFK
        - Auto-replies sent by ZeroX do NOT clear AFK
        - Use .unafk to clear manually
        - Status survives bot restarts (DB-backed)
    """
    reason = (event.pattern_match.group(1) or "").strip() or "AFK"
    me = await event.client.get_me()

    try:
        async with get_session() as session:
            result = await session.execute(
                select(Afk).where(Afk.user_id == me.id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                row = Afk(user_id=me.id, reason=reason, since=int(time.time()))
                session.add(row)
            else:
                row.reason = reason
                row.since = int(time.time())
    except Exception as e:
        logger.error(f"afk set failed: {e}", exc_info=True)
        await event.edit(Messages.error(f"Database error: {e}"))
        return

    await event.edit(Messages.success(f"💤 AFK — {reason}"))


@command("unafk", "Clear AFK status")
async def afk_unset(event):
    """
    Clear your AFK status manually.

    Usage:
        .unafk

    Notes:
        - Sending any other message also clears AFK
        - Reports how long you were away
    """
    me = await event.client.get_me()

    try:
        async with get_session() as session:
            result = await session.execute(
                select(Afk).where(Afk.user_id == me.id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                await event.edit(Messages.warning("You weren't AFK."))
                return
            elapsed = time.time() - row.since
            await session.delete(row)
    except Exception as e:
        logger.error(f"afk unset failed: {e}", exc_info=True)
        await event.edit(Messages.error(f"Database error: {e}"))
        return

    await event.edit(Messages.success(
        f"Welcome back — away for {Formatters.format_duration(elapsed)}"
    ))


# ─────────────────────── auto-reply listener ───────────────────────

@listener(events.NewMessage(incoming=True))
async def afk_watcher(event):
    """Reply automatically if the user is AFK."""
    if event.sender_id is None:
        return

    me = await event.client.get_me()
    if event.sender_id == me.id:
        return

    # In groups, only reply if mentioned or replied to
    if not event.is_private:
        replied_is_me = False
        if event.is_reply:
            try:
                replied = await event.get_reply_message()
                replied_is_me = replied is not None and replied.sender_id == me.id
            except Exception:
                pass
        if not (event.mentioned or replied_is_me):
            return

    # Look up AFK status
    try:
        async with get_session() as session:
            result = await session.execute(
                select(Afk).where(Afk.user_id == me.id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return
            reason = row.reason
            since = row.since
    except Exception as e:
        logger.warning(f"afk lookup failed: {e}")
        return

    elapsed = Formatters.format_duration(time.time() - since)
    text = f"💤 **AFK** — {reason}\n_Away for {elapsed}_"

    try:
        sent = await event.reply(text)
        # Remember this message so auto-clear ignores it
        if sent is not None:
            _mark_afk_reply(sent.chat_id, sent.id)
    except Exception as e:
        logger.warning(f"afk reply failed: {e}")


# ─────────────────────── auto-clear listener ───────────────────────

@listener(events.NewMessage(outgoing=True))
async def afk_auto_clear(event):
    """Clear AFK on any outgoing message the user actually sent."""
    # Skip messages the AFK system itself sent
    if _is_afk_reply(event.chat_id, event.message.id):
        return

    # Skip Saved Messages — not real activity
    try:
        me = await event.client.get_me()
        if event.chat_id == me.id:
            return
    except Exception:
        pass

    text = event.raw_text or ""

    # Ignore .afk / .unafk themselves
    if text.startswith(Config.CMD_PREFIX):
        rest = text[len(Config.CMD_PREFIX):].strip()
        cmd_name = rest.split()[0].lower() if rest.split() else ""
        if cmd_name in ("afk", "unafk"):
            return

    # Look up AFK row
    try:
        me = await event.client.get_me()
        async with get_session() as session:
            result = await session.execute(
                select(Afk).where(Afk.user_id == me.id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return
            elapsed = time.time() - row.since
            await session.delete(row)
    except Exception as e:
        logger.warning(f"afk auto-clear failed: {e}")
        return

    # Quietly notify, then remove the notification
    try:
        note = await event.respond(
            f"✅ AFK cleared — away for {Formatters.format_duration(elapsed)}"
        )
        # Mark it too so it doesn't re-trigger the listener
        _mark_afk_reply(note.chat_id, note.id)
        await asyncio.sleep(4)
        await note.delete()
    except Exception:
        pass