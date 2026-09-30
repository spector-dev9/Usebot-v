"""Grab — unified media saver for view-once, self-destruct, and channels."""
import asyncio
import io
import time
from pathlib import Path

from telethon import events
from telethon.tl.types import (
    MessageMediaDocument, MessageMediaPhoto,
    Document, Photo,
)

from helpers.decorators import command, sudo_only, listener
from utils.messages import Messages
from utils.formatters import Formatters
from Config.settings import Config
from core.logger import setup_logger

logger = setup_logger(__name__)

DOWNLOADS = Path(Config.DATA_DIR) / "downloads"
DOWNLOADS.mkdir(parents=True, exist_ok=True)

# Max int32 — Telegram uses this as the "view-once" marker
VIEW_ONCE_MARKER = 2147483647

# Auto-save state + batch cooldown
_state = {"auto": False}
_batch_cooldown: dict[int, float] = {}


# ──────────────────────────────────────────────────────────────────
#  DETECTION HELPERS
# ──────────────────────────────────────────────────────────────────

def _ttl(msg) -> int:
    """Return TTL seconds for a message's media, 0 if none."""
    if not msg or not msg.media:
        return 0
    return int(getattr(msg.media, "ttl_seconds", 0) or 0)


def _media_kind(msg) -> str:
    """
    Classify the media type.
    Returns: 'none' | 'photo' | 'document' | 'video' | 'audio' | 'voice' | 'sticker' | 'gif'
    """
    if not msg or not msg.media:
        return "none"
    if isinstance(msg.media, MessageMediaPhoto):
        return "photo"
    if isinstance(msg.media, MessageMediaDocument):
        doc = msg.media.document
        mime = getattr(doc, "mime_type", "") or ""
        if mime.startswith("video/"):
            return "video"
        if mime.startswith("audio/"):
            return "audio"
        if mime.startswith("image/"):
            return "photo"
        for attr in getattr(doc, "attributes", []) or []:
            tname = type(attr).__name__
            if tname == "DocumentAttributeVideo":
                return "video"
            if tname == "DocumentAttributeAudio":
                return "voice" if getattr(attr, "voice", False) else "audio"
            if tname == "DocumentAttributeSticker":
                return "sticker"
            if tname == "DocumentAttributeAnimated":
                return "gif"
        return "document"
    return "none"


def _ttl_label(ttl: int) -> str:
    """Human label for a TTL value."""
    if ttl == 0:
        return "normal"
    if ttl >= VIEW_ONCE_MARKER:
        return "view-once / view-twice"
    return f"self-destruct {ttl}s"


def _is_ephemeral(msg) -> bool:
    """True if the message is view-once OR self-destruct."""
    return _ttl(msg) > 0


def _has_media(msg) -> bool:
    return _media_kind(msg) != "none"


def _file_name(msg) -> str:
    """Best-effort filename for a message."""
    if not msg or not msg.media:
        return "file"
    doc = getattr(msg.media, "document", None)
    if doc and getattr(doc, "attributes", None):
        for attr in doc.attributes:
            name = getattr(attr, "file_name", None)
            if name:
                # sanitize
                name = (name or "file").strip()
                for ch in ('/', '\\', '\x00', '\n', '\r'):
                    name = name.replace(ch, "_")
                return name[:180] or "file"
    kind = _media_kind(msg)
    ext = {
        "photo": "jpg",
        "video": "mp4",
        "audio": "mp3",
        "voice": "ogg",
        "sticker": "webp",
        "gif": "mp4",
        "document": "bin",
    }.get(kind, "bin")
    return f"{kind}_{msg.id}.{ext}"


def _size_of(msg) -> int:
    """Return media size in bytes (0 if unknown)."""
    if not msg or not msg.media:
        return 0
    if isinstance(msg.media, MessageMediaDocument):
        return int(getattr(msg.media.document, "size", 0) or 0)
    if isinstance(msg.media, MessageMediaPhoto):
        # Photos have multiple size variants; approximate
        sizes = getattr(msg.media.photo, "sizes", []) or []
        best = 0
        for s in sizes:
            sz = getattr(s, "size", 0) or 0
            if sz > best:
                best = sz
        return int(best)
    return 0


def _human_bar(done: int, total: int) -> str:
    pct = (done / total * 100) if total else 0
    bar_len = 12
    filled = int(bar_len * pct / 100)
    bar = "▰" * filled + "▱" * (bar_len - filled)
    return f"{bar} {pct:.1f}%  {Formatters.format_size(done)}/{Formatters.format_size(total)}"


def _unique_path(base: Path) -> Path:
    if not base.exists():
        return base
    stem, suffix = base.stem, base.suffix
    i = 1
    while True:
        candidate = base.parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


# ──────────────────────────────────────────────────────────────────
#  CORE DOWNLOAD  (used by all commands)
# ──────────────────────────────────────────────────────────────────

async def _download(msg, event, status_msg=None, show_progress=True):
    """
    Download a message's media to disk. Returns Path or None.
    Updates status_msg with progress if provided.
    """
    fname = _file_name(msg)
    target = _unique_path(DOWNLOADS / fname)

    last_update = [0.0]

    async def _progress(received, total):
        if not show_progress or not status_msg or not total:
            return
        now = time.time()
        if now - last_update[0] < 2.0:
            return
        last_update[0] = now
        try:
            await status_msg.edit(
                f"⬇️ **{fname}**\n`{_human_bar(received, total)}`"
            )
        except Exception:
            pass

    try:
        path = await event.client.download_media(
            msg, file=str(target), progress_callback=_progress,
        )
    except Exception as e:
        logger.error(f"grab download failed: {e}", exc_info=True)
        return None

    if not path:
        return None
    return Path(path)


# ──────────────────────────────────────────────────────────────────
#  .grab — save to disk
# ──────────────────────────────────────────────────────────────────

@command("grab", "Save replied media to disk (any type)")
async def grab_handler(event):
    """
    Download the replied message's media/file to disk.

    Works on:
      • Photos, videos, audio, voice notes, files, GIFs, stickers
      • View-once media
      • Self-destructing media (any TTL)
      • Channel posts (reply to the post)

    Usage:
        .grab               (reply to a message)

    Notes:
        - Saves to `data/downloads/`
        - Progress bar for files > a few MB
        - Auto-renames if a file with the same name exists
        - Telegram's hard cap is 2 GB per file (4 GB for Premium)
    """
    if not event.is_reply:
        await event.edit(Messages.error("Reply to a message with media."))
        return

    replied = await event.get_reply_message()
    if not replied or not _has_media(replied):
        await event.edit(Messages.error("That message has no media/file."))
        return

    kind = _media_kind(replied)
    ttl = _ttl(replied)
    fname = _file_name(replied)
    size = _size_of(replied)

    status = await event.edit(
        f"⬇️ **{fname}**\n"
        f"Type: `{kind}` · {_ttl_label(ttl)}\n"
        f"_{Formatters.format_size(size) if size else '…'}_"
    )

    final = await _download(replied, event, status_msg=status)
    if not final:
        await event.edit(Messages.error("Download failed."))
        return

    fs = final.stat().st_size if final.exists() else 0
    await event.edit(Messages.success(
        f"Saved `{final.name}`\n"
        f"📁 `{final.parent}`\n"
        f"💾 {Formatters.format_size(fs)}"
    ))


# ──────────────────────────────────────────────────────────────────
#  .grabdm — save to Saved Messages
# ──────────────────────────────────────────────────────────────────

@command("grabdm", "Resend replied media to Saved Messages")
async def grabdm_handler(event):
    """
    Copy the replied media to your Saved Messages.

    Works around no-forward flags (uses re-upload, not forward).

    Usage:
        .grabdm             (reply to a message)

    Notes:
        - Downloads to memory, then re-uploads
        - Slower for large files (2× bandwidth)
        - Original message stays untouched
    """
    if not event.is_reply:
        await event.edit(Messages.error("Reply to a message with media."))
        return

    replied = await event.get_reply_message()
    if not replied or not _has_media(replied):
        await event.edit(Messages.error("That message has no media/file."))
        return

    fname = _file_name(replied)
    kind = _media_kind(replied)
    ttl = _ttl(replied)

    await event.edit(Messages.loading(
        f"Copying `{fname}` to Saved Messages…\n"
        f"_{kind} · {_ttl_label(ttl)}_"
    ))

    try:
        buf = await event.client.download_media(replied, file=bytes)
    except Exception as e:
        await event.edit(Messages.error(f"Download failed: `{e}`"))
        return

    if not buf:
        await event.edit(Messages.error("Download returned nothing."))
        return

    try:
        f = io.BytesIO(buf)
        f.name = fname
        await event.client.send_file("me", f, force_document=True)
    except Exception as e:
        await event.edit(Messages.error(f"Upload failed: `{e}`"))
        return

    await event.edit(Messages.success(
        f"Sent `{fname}` to Saved Messages."
    ))


# ──────────────────────────────────────────────────────────────────
#  .grabinfo — inspect without downloading
# ──────────────────────────────────────────────────────────────────

@command("grabinfo", "Show metadata for replied media")
async def grabinfo_handler(event):
    """
    Inspect a message's media metadata without downloading.

    Usage:
        .grabinfo           (reply to a message)
    """
    if not event.is_reply:
        await event.edit(Messages.error("Reply to a message."))
        return

    replied = await event.get_reply_message()
    if not replied:
        await event.edit(Messages.error("Couldn't read replied message."))
        return

    kind = _media_kind(replied)
    ttl = _ttl(replied)
    size = _size_of(replied)

    lines = ["🔍 **Media info**\n"]
    lines.append(f"• Type: **{kind}**")
    lines.append(f"• TTL: `{ttl}` — {_ttl_label(ttl)}")
    lines.append(f"• Size: {Formatters.format_size(size) if size else '?'}")
    lines.append(f"• Message ID: `{replied.id}`")
    lines.append(f"• Date: `{replied.date}`")

    if not replied.media:
        lines.append("\n_No media in this message._")
        await event.edit("\n".join(lines))
        return

    sender = None
    try:
        sender = await replied.get_sender()
    except Exception:
        pass
    if sender:
        name = getattr(sender, "first_name", None) or getattr(sender, "title", None) or "?"
        lines.append(f"• Sender: **{name}**")

    if isinstance(replied.media, MessageMediaDocument):
        doc = replied.media.document
        lines.append(f"• MIME: `{getattr(doc, 'mime_type', '?')}`")
        lines.append(f"• DC: `{getattr(doc, 'dc_id', '?')}`")
    elif isinstance(replied.media, MessageMediaPhoto):
        lines.append(f"• Photo ID: `{replied.media.photo.id}`")

    await event.edit("\n".join(lines))


# ──────────────────────────────────────────────────────────────────
#  .grabbatch — batch from a channel
# ──────────────────────────────────────────────────────────────────

@command(r"grabbatch (\S+)(?:\s+(\d+)-(\d+))?", "Batch-download from a channel or group")
@sudo_only
async def grabbatch_handler(event):
    """
    Batch-download media/files from a channel or group.

    Usage:
        .grabbatch <@channel|link|id> <start>-<end>
        .grabbatch <@channel|link|id>                     (last 50)

    Examples:
        .grabbatch @somechannel 100-200
        .grabbatch @somechannel

    Notes:
        - Sudo only
        - Downloads everything with media in the range
        - Skips files already on disk (by name)
        - Capped at 200 files per run
        - Cooldown: 60s between runs per user
    """
    now = time.time()
    last = _batch_cooldown.get(event.sender_id, 0)
    if now - last < 60:
        await event.edit(Messages.warning(
            f"Cooldown — wait {60 - int(now - last)}s."
        ))
        return
    _batch_cooldown[event.sender_id] = now

    raw = event.pattern_match.group(1)
    n1 = event.pattern_match.group(2)
    n2 = event.pattern_match.group(3)

    if n1 and n2:
        start_id, end_id = int(n1), int(n2)
        if end_id < start_id:
            start_id, end_id = end_id, start_id
        if end_id - start_id > 199:
            end_id = start_id + 199
    else:
        start_id = end_id = None

    await event.edit(Messages.loading(f"Resolving `{raw}`…"))

    try:
        entity = await event.client.get_entity(raw)
    except Exception as e:
        await event.edit(Messages.error(f"Couldn't resolve: `{e}`"))
        return

    title = getattr(entity, "title", None) or raw

    await event.edit(Messages.loading(f"Scanning **{title}**…"))

    targets = []
    try:
        kwargs = {"limit": 200}
        if start_id is not None and end_id is not None:
            kwargs["min_id"] = start_id - 1
            kwargs["max_id"] = end_id + 1
        async for msg in event.client.iter_messages(entity, **kwargs):
            if _has_media(msg):
                targets.append(msg)
    except Exception as e:
        await event.edit(Messages.error(f"Scan failed: `{e}`"))
        return

    if not targets:
        await event.edit(Messages.info("No media found in that range."))
        return

    total = len(targets)
    done = failed = skipped = 0
    saved_bytes = 0

    status = await event.edit(
        f"📥 **Batch from {title}**\n"
        f"`0/{total}`"
    )

    for i, msg in enumerate(targets, 1):
        fname = _file_name(msg)
        target = DOWNLOADS / fname

        if target.exists():
            skipped += 1
        else:
            try:
                path = await event.client.download_media(msg, file=str(target))
                if path:
                    saved_bytes += Path(path).stat().st_size
                    done += 1
                else:
                    failed += 1
            except Exception as e:
                logger.warning(f"grabbatch {msg.id}: {e}")
                failed += 1

        if i % 3 == 0 or i == total:
            try:
                await status.edit(
                    f"📥 **Batch from {title}**\n"
                    f"`{i}/{total}` · saved {done} · skipped {skipped} · failed {failed}"
                )
            except Exception:
                pass

        await asyncio.sleep(0.3)

    await event.edit(Messages.success(
        f"Batch complete from **{title}**\n"
        f"• Saved: **{done}**\n"
        f"• Skipped (existing): **{skipped}**\n"
        f"• Failed: **{failed}**\n"
        f"• Total: **{Formatters.format_size(saved_bytes)}**\n\n"
        f"📁 `{DOWNLOADS}`"
    ))


# ──────────────────────────────────────────────────────────────────
#  .grabclean — manage downloads folder
# ──────────────────────────────────────────────────────────────────

@command(r"grabclean(?:\s+(.+))?", "Manage downloads folder")
@sudo_only
async def grabclean_handler(event):
    """
    Show downloads folder stats, or delete files.

    Usage:
        .grabclean                → show size + count
        .grabclean wipe           → delete all files
        .grabclean older <days>   → delete files older than N days

    Notes:
        - Sudo only
        - `wipe` and `older` are irreversible
    """
    arg = (event.pattern_match.group(1) or "").strip().lower()

    files = [f for f in DOWNLOADS.iterdir() if f.is_file()] if DOWNLOADS.exists() else []
    total = sum(f.stat().st_size for f in files)

    if arg.startswith("older"):
        parts = arg.split()
        days = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 7
        cutoff = time.time() - days * 86400
        freed = deleted = 0
        for f in files:
            try:
                if f.stat().st_mtime < cutoff:
                    freed += f.stat().st_size
                    f.unlink()
                    deleted += 1
            except Exception:
                pass
        await event.edit(Messages.success(
            f"Deleted **{deleted}** file(s) older than {days}d · "
            f"freed {Formatters.format_size(freed)}"
        ))
        return

    if arg == "wipe":
        freed = deleted = 0
        for f in files:
            try:
                freed += f.stat().st_size
                f.unlink()
                deleted += 1
            except Exception:
                pass
        await event.edit(Messages.success(
            f"Deleted **{deleted}** file(s) · freed {Formatters.format_size(freed)}"
        ))
        return

    await event.edit(
        f"📁 **Downloads folder**\n"
        f"• Path: `{DOWNLOADS}`\n"
        f"• Files: **{len(files)}**\n"
        f"• Total: **{Formatters.format_size(total)}**\n\n"
        f"_Options:_\n"
        f"• `.grabclean wipe` — delete all\n"
        f"• `.grabclean older <days>` — delete older than N days"
    )


# ──────────────────────────────────────────────────────────────────
#  .autograb — auto-save incoming ephemeral media
# ──────────────────────────────────────────────────────────────────

@command(r"autograb(?:\s+(on|off))?", "Auto-save incoming view-once/self-destruct media")
@sudo_only
async def autograb_handler(event):
    """
    Auto-copy incoming ephemeral media (view-once, self-destruct)
    to your Saved Messages.

    Usage:
        .autograb           → status
        .autograb on        → enable
        .autograb off       → disable

    Notes:
        - Sudo only
        - When ON, every view-once / self-destruct media you receive
          is downloaded and re-uploaded to Saved Messages
        - Uses re-upload (not forward), so the original stays untouched
        - Sender cannot see the save happened
    """
    arg = (event.pattern_match.group(1) or "").lower()

    if not arg:
        state = "🟢 ON" if _state["auto"] else "🔴 OFF"
        await event.edit(Messages.info(f"Auto-grab ephemeral: **{state}**"))
        return

    if arg == "off":
        _state["auto"] = False
        await event.edit(Messages.success("Auto-grab **disabled**."))
        return

    if arg == "on":
        _state["auto"] = True
        await event.edit(Messages.success(
            "Auto-grab **enabled**. Incoming view-once and "
            "self-destruct media will be copied to Saved Messages."
        ))
        return

    await event.edit(Messages.error("Usage: `.autograb on|off`"))


# ──────────────────────────────────────────────────────────────────
#  WATCHER — fires on incoming ephemeral media
# ──────────────────────────────────────────────────────────────────

@listener(events.NewMessage(incoming=True))
async def _ephemeral_watcher(event):
    if not _state["auto"]:
        return
    if not event.media:
        return
    if not _is_ephemeral(event):
        return

    try:
        buf = await event.client.download_media(event, file=bytes)
        if not buf:
            return
        fname = _file_name(event)
        f = io.BytesIO(buf)
        f.name = fname
        kind = _media_kind(event)
        ttl = _ttl(event)
        caption = (
            f"📥 **Auto-saved**\n"
            f"• From: `{event.sender_id}`\n"
            f"• Type: {kind}\n"
            f"• Mode: {_ttl_label(ttl)}"
        )
        await event.client.send_file("me", f, caption=caption, force_document=True)
        logger.info(f"autograb: saved {kind} from {event.sender_id}")
    except Exception as e:
        logger.warning(f"autograb watcher: {e}")


# ──────────────────────────────────────────────────────────────────
#  HELP
# ──────────────────────────────────────────────────────────────────

@command("grabhelp", "Grab module help")
async def grabhelp_handler(event):
    """Usage: `.grabhelp`"""
    await event.edit(
        "📥 **GRAB — Unified Media Saver**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "**Save to disk:**\n"
        "• `.grab` — reply to any media → save locally\n\n"
        "**Save to Saved Messages:**\n"
        "• `.grabdm` — reply → re-upload to Saved\n\n"
        "**Inspect:**\n"
        "• `.grabinfo` — metadata without downloading\n\n"
        "**Batch (sudo):**\n"
        "• `.grabbatch <@chan> [n1-n2]` — batch download\n"
        "• `.grabclean` — folder stats\n"
        "• `.grabclean wipe` — delete all\n"
        "• `.grabclean older <days>` — prune old\n\n"
        "**Auto mode (sudo):**\n"
        "• `.autograb on` — auto-save incoming view-once\n"
        "• `.autograb off` — disable\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "**Handles:**\n"
        "• Photos · Videos · Files · Audio · Voice · GIFs · Stickers\n"
        "• View-once · View-twice · Self-destruct timers\n"
        "• Channel posts · Group files · DMs\n\n"
        "📁 Files land in `data/downloads/`"
    )