"""Toolkit — purge, del, notes, ghost, fake typing, filters."""
import asyncio
import time

from telethon import events
from sqlalchemy import select

from helpers.decorators import command, sudo_only, listener
from utils.messages import Messages
from Config.settings import Config
from core.logger import setup_logger
from database.connection import get_session
from database.models import Note, Filter

logger = setup_logger(__name__)


# ══════════════════════════════════════════════════════════════════
#  PURGE / DEL
# ══════════════════════════════════════════════════════════════════

async def _bulk_delete(client, chat_id, ids):
    total = 0
    for i in range(0, len(ids), 100):
        batch = ids[i:i+100]
        try:
            await client.delete_messages(chat_id, batch)
            total += len(batch)
        except Exception as e:
            logger.warning(f"batch delete failed: {e}")
    return total


@command("purge", "Delete messages from reply to now")
@sudo_only
async def purge_handler(event):
    """
    Delete all messages from the replied message up to now.

    Usage:
        .purge              (reply to start message)

    Notes:
        - Deletes up to 3000 messages
        - Sudo only
    """
    if not event.is_reply:
        await event.edit(Messages.error("Reply to the message to start from."))
        return

    replied = await event.get_reply_message()
    await event.edit(Messages.loading("Purging..."))

    ids = [event.message.id]
    async for msg in event.client.iter_messages(
        event.chat_id,
        min_id=replied.id - 1,
        max_id=event.message.id,
        reverse=True,
    ):
        ids.append(msg.id)

    deleted = await _bulk_delete(event.client, event.chat_id, ids)
    note = await event.respond(Messages.success(f"Purged {deleted} messages."))
    await asyncio.sleep(3)
    try:
        await note.delete()
    except Exception:
        pass


@command(r"purgeme(?:\s+(\d+))?", "Delete your own recent messages")
@sudo_only
async def purgeme_handler(event):
    """
    Delete your own last N messages in this chat.

    Usage:
        .purgeme <n>

    Notes:
        - Only deletes messages sent by this account
        - Sudo only
    """
    n = int(event.pattern_match.group(1) or 10)
    if n < 1 or n > 500:
        await event.edit(Messages.error("Number must be 1–500."))
        return

    await event.edit(Messages.loading(f"Purging your last {n}..."))

    me = await event.client.get_me()
    ids = [event.message.id]
    async for msg in event.client.iter_messages(event.chat_id, limit=300):
        if msg.sender_id == me.id:
            ids.append(msg.id)
        if len(ids) >= n + 1:
            break

    deleted = await _bulk_delete(event.client, event.chat_id, ids)
    note = await event.respond(Messages.success(f"Deleted {deleted} of your messages."))
    await asyncio.sleep(3)
    try:
        await note.delete()
    except Exception:
        pass


@command("del", "Delete a single replied message")
@sudo_only
async def del_handler(event):
    """
    Delete the replied message.

    Usage:
        .del                (reply)
    """
    if not event.is_reply:
        await event.edit(Messages.error("Reply to a message."))
        return
    replied = await event.get_reply_message()
    await event.client.delete_messages(event.chat_id, [replied.id, event.message.id])


@command("delf", "Forward then delete a replied message")
@sudo_only
async def delf_handler(event):
    """
    Forward the replied message to Saved Messages, then delete it.

    Usage:
        .delf               (reply)
    """
    if not event.is_reply:
        await event.edit(Messages.error("Reply to a message."))
        return
    replied = await event.get_reply_message()
    try:
        await replied.forward_to("me")
    except Exception as e:
        await event.edit(Messages.error(f"Forward failed: {e}"))
        return
    await event.client.delete_messages(event.chat_id, [replied.id, event.message.id])


# ══════════════════════════════════════════════════════════════════
#  NOTES
# ══════════════════════════════════════════════════════════════════

@command(r"note (\w+)(?:\s+(.+))?", "Save a text note")
async def note_handler(event):
    """
    Save a text note under a name.

    Usage:
        .note <name>             (reply to a message)
        .note <name> <text>

    Examples:
        .note address 123 Main St
        .note quote              (reply to a message)
    """
    name = event.pattern_match.group(1).strip()
    inline = event.pattern_match.group(2)

    if inline:
        content = inline
    elif event.is_reply:
        replied = await event.get_reply_message()
        content = replied.raw_text or ""
        if not content:
            await event.edit(Messages.error("Replied message has no text."))
            return
    else:
        await event.edit(Messages.error(
            "Usage: `.note <name> <text>` or reply to a message with `.note <name>`."
        ))
        return

    me = await event.client.get_me()
    try:
        async with get_session() as session:
            result = await session.execute(
                select(Note).where(Note.user_id == me.id, Note.name == name)
            )
            row = result.scalar_one_or_none()
            if row is None:
                row = Note(user_id=me.id, name=name, content=content)
                session.add(row)
                action = "saved"
            else:
                row.content = content
                action = "updated"
    except Exception as e:
        logger.error(f"note save failed: {e}", exc_info=True)
        await event.edit(Messages.error(f"Database error: {e}"))
        return

    await event.edit(Messages.success(f"Note `{name}` {action}."))


@command(r"get (\w+)", "Retrieve a saved note")
async def get_handler(event):
    """
    Retrieve a note by name.

    Usage:
        .get <name>

    Examples:
        .get address
    """
    name = event.pattern_match.group(1).strip()
    me = await event.client.get_me()

    try:
        async with get_session() as session:
            result = await session.execute(
                select(Note).where(Note.user_id == me.id, Note.name == name)
            )
            row = result.scalar_one_or_none()
    except Exception as e:
        await event.edit(Messages.error(f"Database error: {e}"))
        return

    if row is None:
        await event.edit(Messages.error(f"Note `{name}` not found."))
        return

    await event.edit(f"📝 **{name}**\n\n{row.content}")


@command("notes", "List all saved notes")
async def notes_handler(event):
    """
    List every saved note.

    Usage:
        .notes
    """
    me = await event.client.get_me()
    try:
        async with get_session() as session:
            result = await session.execute(
                select(Note).where(Note.user_id == me.id).order_by(Note.name)
            )
            rows = result.scalars().all()
    except Exception as e:
        await event.edit(Messages.error(f"Database error: {e}"))
        return

    if not rows:
        await event.edit(Messages.info("No notes saved yet."))
        return

    lines = ["📝 **Saved notes**\n"]
    for r in rows:
        preview = (r.content[:40] + "…") if len(r.content) > 40 else r.content
        preview = preview.replace("\n", " ")
        lines.append(f"• `{r.name}` — {preview}")
    await event.edit("\n".join(lines))


@command(r"notedel (\w+)", "Delete a note")
async def notedel_handler(event):
    """
    Delete a note.

    Usage:
        .notedel <name>
    """
    name = event.pattern_match.group(1).strip()
    me = await event.client.get_me()

    try:
        async with get_session() as session:
            result = await session.execute(
                select(Note).where(Note.user_id == me.id, Note.name == name)
            )
            row = result.scalar_one_or_none()
            if row is None:
                await event.edit(Messages.error(f"Note `{name}` not found."))
                return
            await session.delete(row)
    except Exception as e:
        await event.edit(Messages.error(f"Database error: {e}"))
        return

    await event.edit(Messages.success(f"Deleted note `{name}`."))


# ══════════════════════════════════════════════════════════════════
#  GHOST (self-destructing outgoing messages)
# ══════════════════════════════════════════════════════════════════

_ghost_state = {"enabled": False, "delay": 30, "skip": set()}


@command(r"ghoston(?:\s+(\d+))?", "Auto-delete your outgoing messages")
async def ghoston_handler(event):
    """
    Enable ghost mode — every message you send self-destructs
    after N seconds.

    Usage:
        .ghoston            default 30s
        .ghoston <seconds>

    Notes:
        - Only affects messages sent AFTER enabling
        - Commands (starting with prefix) are not deleted
        - Disable with .ghostoff
    """
    delay = int(event.pattern_match.group(1) or 30)
    if delay < 5:
        await event.edit(Messages.error("Minimum delay is 5s."))
        return

    _ghost_state["enabled"] = True
    _ghost_state["delay"] = delay

    note = await event.respond(Messages.success(f"👻 Ghost ON — {delay}s"))
    _ghost_state["skip"].add(note.id)
    await asyncio.sleep(3)
    try:
        await note.delete()
    except Exception:
        pass


@command("ghostoff", "Disable ghost mode")
async def ghostoff_handler(event):
    """
    Disable ghost mode.

    Usage:
        .ghostoff
    """
    _ghost_state["enabled"] = False
    note = await event.respond(Messages.success("👻 Ghost OFF"))
    _ghost_state["skip"].add(note.id)
    await asyncio.sleep(3)
    try:
        await note.delete()
    except Exception:
        pass


@command("ghost", "Show ghost status")
async def ghost_handler(event):
    """
    Show ghost mode status.

    Usage:
        .ghost
    """
    if _ghost_state["enabled"]:
        await event.edit(Messages.info(
            f"👻 Ghost is **ON** — delay {_ghost_state['delay']}s"
        ))
    else:
        await event.edit(Messages.info("👻 Ghost is **OFF**"))


@listener(events.NewMessage(outgoing=True))
async def _ghost_watcher(event):
    """Schedule deletion of outgoing messages when ghost is on."""
    if not _ghost_state["enabled"]:
        return

    text = event.raw_text or ""
    if text.startswith(Config.CMD_PREFIX):
        return

    try:
        me = await event.client.get_me()
        if event.chat_id == me.id:
            return
    except Exception:
        pass

    if event.message.id in _ghost_state["skip"]:
        _ghost_state["skip"].discard(event.message.id)
        return

    delay = _ghost_state["delay"]
    chat_id = event.chat_id
    msg_id = event.message.id

    async def _delete_later():
        await asyncio.sleep(delay)
        try:
            await event.client.delete_messages(chat_id, [msg_id])
        except Exception:
            pass

    asyncio.create_task(_delete_later())


# ══════════════════════════════════════════════════════════════════
#  FAKE TYPING / ACTIONS
# ══════════════════════════════════════════════════════════════════

async def _fake_action(event, action: str):
    try:
        seconds = int(event.pattern_match.group(1) or 5)
    except Exception:
        seconds = 5
    if seconds < 1 or seconds > 60:
        await event.edit(Messages.error("Duration must be 1–60s."))
        return
    await event.delete()
    async with event.client.action(event.chat_id, action):
        await asyncio.sleep(seconds)


@command(r"typing(?:\s+(\d+))?", "Show typing indicator for N seconds")
async def typing_handler(event):
    """
    Show "typing…" in the current chat for N seconds.

    Usage:
        .typing <seconds>

    Examples:
        .typing 10
    """
    await _fake_action(event, "typing")


@command(r"recording(?:\s+(\d+))?", "Show recording audio indicator")
async def recording_handler(event):
    """
    Show "recording audio…" for N seconds.

    Usage:
        .recording <seconds>
    """
    await _fake_action(event, "record-audio")


@command(r"uploading(?:\s+(\d+))?", "Show uploading photo indicator")
async def uploading_handler(event):
    """
    Show "uploading photo…" for N seconds.

    Usage:
        .uploading <seconds>
    """
    await _fake_action(event, "photo")


@command(r"playing(?:\s+(\d+))?", "Show playing game indicator")
async def playing_handler(event):
    """
    Show "playing a game…" for N seconds.

    Usage:
        .playing <seconds>
    """
    await _fake_action(event, "game")


# ══════════════════════════════════════════════════════════════════
#  FILTERS (auto-reply)
# ══════════════════════════════════════════════════════════════════

@command(r"filter (\w+) (.+)", "Add an auto-reply filter")
async def filter_add(event):
    """
    Add an auto-reply filter. When any incoming message contains
    the keyword, ZeroX replies with the saved response.

    Usage:
        .filter <keyword> <response>

    Examples:
        .filter hi Hello there!
        .filter price Contact us at @shop

    Notes:
        - Case-insensitive match
        - Response can contain emojis and markdown
        - Disable with .filterdel <keyword>
    """
    keyword = event.pattern_match.group(1).strip().lower()
    response = event.pattern_match.group(2).strip()

    me = await event.client.get_me()
    try:
        async with get_session() as session:
            result = await session.execute(
                select(Filter).where(
                    Filter.user_id == me.id,
                    Filter.keyword == keyword,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                row = Filter(user_id=me.id, keyword=keyword, response=response)
                session.add(row)
                action = "added"
            else:
                row.response = response
                action = "updated"
    except Exception as e:
        await event.edit(Messages.error(f"Database error: {e}"))
        return

    await event.edit(Messages.success(f"Filter `{keyword}` {action}."))


@command(r"filterdel (\w+)", "Remove a filter")
async def filter_del(event):
    """
    Remove an auto-reply filter.

    Usage:
        .filterdel <keyword>
    """
    keyword = event.pattern_match.group(1).strip().lower()
    me = await event.client.get_me()

    try:
        async with get_session() as session:
            result = await session.execute(
                select(Filter).where(
                    Filter.user_id == me.id,
                    Filter.keyword == keyword,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                await event.edit(Messages.error(f"Filter `{keyword}` not found."))
                return
            await session.delete(row)
    except Exception as e:
        await event.edit(Messages.error(f"Database error: {e}"))
        return

    await event.edit(Messages.success(f"Filter `{keyword}` removed."))


@command("filters", "List all filters")
async def filters_list(event):
    """
    List every active auto-reply filter.

    Usage:
        .filters
    """
    me = await event.client.get_me()
    try:
        async with get_session() as session:
            result = await session.execute(
                select(Filter).where(Filter.user_id == me.id).order_by(Filter.keyword)
            )
            rows = result.scalars().all()
    except Exception as e:
        await event.edit(Messages.error(f"Database error: {e}"))
        return

    if not rows:
        await event.edit(Messages.info("No filters set."))
        return

    lines = ["🎯 **Active filters**\n"]
    for r in rows:
        preview = (r.response[:40] + "…") if len(r.response) > 40 else r.response
        lines.append(f"• `{r.keyword}` → {preview}")
    await event.edit("\n".join(lines))


@command("filterclear", "Delete all filters")
async def filter_clear(event):
    """
    Remove ALL auto-reply filters at once.

    Usage:
        .filterclear
    """
    me = await event.client.get_me()
    try:
        async with get_session() as session:
            result = await session.execute(
                select(Filter).where(Filter.user_id == me.id)
            )
            rows = result.scalars().all()
            for r in rows:
                await session.delete(r)
    except Exception as e:
        await event.edit(Messages.error(f"Database error: {e}"))
        return

    await event.edit(Messages.success(f"Cleared {len(rows)} filter(s)."))


@listener(events.NewMessage(incoming=True))
async def _filter_watcher(event):
    """Reply to incoming messages that match a filter."""
    text = (event.raw_text or "").lower()
    if not text:
        return

    me = await event.client.get_me()
    if event.sender_id == me.id:
        return

    # Skip bots
    try:
        sender = await event.get_sender()
        if getattr(sender, "bot", False):
            return
    except Exception:
        pass

    try:
        async with get_session() as session:
            result = await session.execute(
                select(Filter).where(Filter.user_id == me.id)
            )
            rows = result.scalars().all()
    except Exception as e:
        logger.warning(f"filter lookup failed: {e}")
        return

    # Match longest keyword first to prefer specific filters
    matches = [r for r in rows if r.keyword in text]
    if not matches:
        return

    matches.sort(key=lambda r: len(r.keyword), reverse=True)
    winner = matches[0]

    try:
        await event.reply(winner.response)
    except Exception as e:
        logger.warning(f"filter reply failed: {e}")


# ══════════════════════════════════════════════════════════════════
#  HELP
# ══════════════════════════════════════════════════════════════════

@command("toolkithelp", "Toolkit module help")
async def toolkit_help(event):
    """
    Show all Toolkit commands.

    Usage:
        .toolkithelp
    """
    await event.edit(
        "🧰 **TOOLKIT**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "**🗑 Purge / Del** _(sudo)_\n"
        "• `.purge` — delete from reply to now\n"
        "• `.purgeme <n>` — delete your last N\n"
        "• `.del` — delete one message\n"
        "• `.delf` — forward to Saved, then delete\n\n"
        "**📝 Notes**\n"
        "• `.note <name> <text>` / `.note <name>` (reply)\n"
        "• `.get <name>`\n"
        "• `.notes` · `.notedel <name>`\n\n"
        "**👻 Ghost**\n"
        "• `.ghoston <sec>` · `.ghostoff` · `.ghost`\n\n"
        "**⌨️ Fake Actions**\n"
        "• `.typing <sec>` · `.recording <sec>`\n"
        "• `.uploading <sec>` · `.playing <sec>`\n\n"
        "**🎯 Filters**\n"
        "• `.filter <kw> <reply>` · `.filterdel <kw>`\n"
        "• `.filters` · `.filterclear`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )