"""Zerox — profile cloning for users, bots, channels, and groups."""
import io
from pathlib import Path

from sqlalchemy import select
from telethon import functions
from telethon.tl.types import (
    Channel, Chat, User as TLUser,
)

from helpers.decorators import command
from utils.messages import Messages
from Config.settings import Config
from core.logger import setup_logger
from database.connection import get_session
from database.models import Preset

logger = setup_logger(__name__)


# ──────────────────────────────────────────────────────────────────
#  TELEGRAM HELPERS
# ──────────────────────────────────────────────────────────────────

async def _resolve(client, arg):
    """
    Resolve @username, numeric id, or bare name into an entity.
    Returns (entity, kind) where kind ∈ {user, bot, channel, chat}.
    """
    arg = arg.strip()
    if not arg:
        return None, None
    try:
        if arg.startswith("@"):
            e = await client.get_entity(arg)
        elif arg.lstrip("-").isdigit():
            e = await client.get_entity(int(arg))
        else:
            e = await client.get_entity(arg)
    except Exception as e:
        logger.warning(f"zerox resolve '{arg}': {e}")
        return None, None

    if e is None:
        return None, None

    # Classify
    if isinstance(e, TLUser):
        return e, ("bot" if getattr(e, "bot", False) else "user")
    if isinstance(e, Channel):
        return e, ("channel" if getattr(e, "broadcast", False) else "supergroup")
    if isinstance(e, Chat):
        return e, "chat"
    # Fallback by attribute sniffing
    if hasattr(e, "first_name"):
        return e, "user"
    if hasattr(e, "title"):
        return e, "chat"
    return None, None


def _name_parts(entity, kind):
    """Return (first_name, last_name) to push to the profile."""
    if kind in ("user", "bot"):
        return (entity.first_name or "", entity.last_name or "")
    # channel / chat / supergroup — use title
    title = getattr(entity, "title", "") or ""
    if not title:
        return ("", "")
    if " " in title:
        first, last = title.split(" ", 1)
        return (first, last)
    return (title, "")


async def _get_bio(client, entity, kind):
    """Fetch 'about' text for a user/bot or channel/group."""
    try:
        if kind in ("user", "bot"):
            full = await client(functions.users.GetFullUserRequest(id=entity.id))
            return full.full_user.about or ""
        if kind in ("channel", "supergroup"):
            full = await client(functions.channels.GetFullChannelRequest(channel=entity))
            return full.full_chat.about or ""
        if kind == "chat":
            full = await client(functions.messages.GetFullChatRequest(chat_id=entity.id))
            return full.full_chat.about or ""
    except Exception as e:
        logger.warning(f"zerox bio fetch ({kind}): {e}")
    return ""


async def _get_photos(client, entity, kind):
    """Return list of photos for user/bot/channel/group."""
    try:
        return await client.get_profile_photos(entity)
    except Exception as e:
        logger.warning(f"zerox photo list ({kind}): {e}")
        return []


async def _download(client, photo) -> io.BytesIO:
    buf = io.BytesIO()
    await client.download_media(photo, file=buf)
    buf.seek(0)
    return buf


async def _set_my_photo(client, file_obj):
    uploaded = await client.upload_file(file_obj, file_name="dp.jpg")
    await client(functions.photos.UploadProfilePhotoRequest(file=uploaded))


async def _wipe_my_photos(client):
    try:
        photos = await client.get_profile_photos("me")
        if photos:
            await client(functions.photos.DeletePhotosRequest(id=list(photos)))
    except Exception as e:
        logger.warning(f"wipe photos: {e}")


async def _update_profile(client, first=None, last=None, about=None):
    kwargs = {}
    if first:
        kwargs["first_name"] = first[:64]
    if last is not None:
        kwargs["last_name"] = (last or "")[:64]
    if about is not None:
        kwargs["about"] = (about or "")[:70]
    if kwargs:
        await client(functions.account.UpdateProfileRequest(**kwargs))


# ──────────────────────────────────────────────────────────────────
#  ZEROX
# ──────────────────────────────────────────────────────────────────

@command(r"zerox(?:\s+(.+))?", "Clone a user/bot/channel/group's profile")
async def zerox_handler(event):
    """
    Clone another entity's profile onto yours.

    Supports:
      • Users (name + bio + DP)
      • Bots (name + bio + DP)
      • Channels (title → name, description → bio, photo → DP)
      • Groups (title → name, description → bio, photo → DP)

    Usage:
        .zerox                       (reply to a user/bot)
        .zerox @username
        .zerox <user_id>
        .zerox @channelusername
        .zerox --nodp                (skip photo)
        .zerox @username --nodp

    Examples:
        .zerox
        .zerox @stranger
        .zerox @durov
        .zerox @somechannel
        .zerox 8178559972

    Notes:
        - For channels/groups, the title is split on the first space
          into first name + last name
        - Bio / description is capped at 70 chars (Telegram limit)
        - DP wipe is destructive — use .save first if you care
    """
    raw = (event.pattern_match.group(1) or "").strip()
    toks = raw.split()
    skip_dp = "--nodp" in toks
    target_arg = " ".join(t for t in toks if t != "--nodp").strip()

    # ── Resolve target ──
    if target_arg:
        target, kind = await _resolve(event.client, target_arg)
        if target is None:
            await event.edit(Messages.error(
                f"Couldn't resolve `{target_arg}`.\n"
                f"Try a numeric id, `@username`, or reply to a message."
            ))
            return
    elif event.is_reply:
        replied = await event.get_reply_message()
        try:
            target = await replied.get_sender()
        except Exception:
            target = None
        if target is None:
            await event.edit(Messages.error("Couldn't resolve the replied user."))
            return
        if isinstance(target, TLUser):
            kind = "bot" if getattr(target, "bot", False) else "user"
        elif isinstance(target, Channel):
            kind = "channel" if getattr(target, "broadcast", False) else "supergroup"
        elif isinstance(target, Chat):
            kind = "chat"
        else:
            await event.edit(Messages.error("Unknown reply target type."))
            return
    else:
        await event.edit(Messages.error(
            "**Usage:**\n"
            "• `.zerox` — reply to a user/bot\n"
            "• `.zerox @username`\n"
            "• `.zerox <user_id>`\n"
            "• `.zerox [target] --nodp`"
        ))
        return

    await event.edit(Messages.loading("Zeroxing…"))

    # ── Fetch name + bio ──
    first, last = _name_parts(target, kind)
    about = await _get_bio(event.client, target, kind)

    if not first:
        await event.edit(Messages.error(
            "Target has no name/title to clone."
        ))
        return

    await _update_profile(
        event.client,
        first=first,
        last=last,
        about=about,
    )

    # ── Photos ──
    photos = await _get_photos(event.client, target, kind)
    dp_count = len(photos)
    dp_status = "skipped"

    if not skip_dp and dp_count:
        try:
            await _wipe_my_photos(event.client)
            buf = await _download(event.client, photos[0])
            await _set_my_photo(event.client, buf)
            dp_status = "cloned"
        except Exception as e:
            dp_status = f"failed: {e}"
            logger.error(f"zerox dp: {e}")

    # ── Report ──
    display_name = f"{first} {last}".strip()
    kind_label = {
        "user": "👤 User",
        "bot": "🤖 Bot",
        "channel": "📢 Channel",
        "supergroup": "👥 Supergroup",
        "chat": "👥 Group",
    }.get(kind, kind)

    msg = f"**{kind_label} cloned**\n"
    msg += Messages.format_key_value("Name", display_name or "—") + "\n"
    msg += Messages.format_key_value(
        "Bio", (about[:60] + "…") if len(about) > 60 else (about or "—")
    ) + "\n"
    msg += Messages.format_key_value("DPs found", str(dp_count)) + "\n"
    msg += Messages.format_key_value("DP action", dp_status)
    await event.edit(msg)


# ──────────────────────────────────────────────────────────────────
#  REVERT / PRESETS / HELP  (unchanged)
# ──────────────────────────────────────────────────────────────────

@command(r"revert(?:\s+(.*))?", "Revert to a saved preset")
async def revert_handler(event):
    """
    Restore a previously saved profile preset.

    Usage:
        .revert             → restore "default"
        .revert <name>      → restore named preset
    """
    preset_name = (event.pattern_match.group(1) or "default").strip()
    me = await event.client.get_me()

    try:
        async with get_session() as session:
            result = await session.execute(
                select(Preset).where(
                    Preset.user_id == me.id,
                    Preset.name == preset_name,
                )
            )
            preset = result.scalar_one_or_none()

            if preset is None:
                avail_result = await session.execute(
                    select(Preset.name).where(Preset.user_id == me.id)
                )
                available = [r[0] for r in avail_result.all()]

        if preset is None:
            avail = ", ".join(available) or "none"
            await event.edit(Messages.error(
                f"Preset `{preset_name}` not found. Available: {avail}"
            ))
            return

        first = preset.first_name or "Me"
        last = preset.last_name or ""
        about = preset.bio or ""
        dp_file = preset.photo_reference
    except Exception as e:
        logger.error(f"DB read failed: {e}", exc_info=True)
        await event.edit(Messages.error(f"Database error: {e}"))
        return

    await event.edit(Messages.loading(f"Reverting to `{preset_name}`…"))

    await _update_profile(event.client, first=first, last=last, about=about)

    photo_status = "no saved dp"
    if dp_file and Path(dp_file).exists():
        try:
            await _wipe_my_photos(event.client)
            with open(dp_file, "rb") as f:
                await _set_my_photo(event.client, f)
            photo_status = "restored"
        except Exception as e:
            photo_status = f"failed: {e}"
            logger.error(f"revert dp: {e}")

    await event.edit(Messages.success(
        f"Reverted to **{preset_name}** (dp: {photo_status})."
    ))


@command("presets", "List presets")
async def presets_handler(event):
    """Usage: `.presets`"""
    me = await event.client.get_me()
    try:
        async with get_session() as session:
            result = await session.execute(
                select(Preset)
                .where(Preset.user_id == me.id)
                .order_by(Preset.updated_at.desc())
            )
            presets = result.scalars().all()

            if not presets:
                await event.edit(Messages.info("No presets saved yet."))
                return

            lines = ["🗂 **Saved presets**\n"]
            for p in presets:
                full = f"{p.first_name or ''} {p.last_name or ''}".strip() or "—"
                dp_mark = "✅" if p.photo_reference and Path(p.photo_reference).exists() else "—"
                lines.append(
                    f"• `{p.name}` — {full}"
                    f" · bio={len(p.bio or '')}c"
                    f" · dp={dp_mark}"
                )

        await event.edit("\n".join(lines))
    except Exception as e:
        logger.error(f"DB list failed: {e}", exc_info=True)
        await event.edit(Messages.error(f"Database error: {e}"))


@command("zeroxhelp", "Zerox help")
async def zerox_help_handler(event):
    """Usage: `.zeroxhelp`"""
    await event.edit(
        "👤 **ZEROX**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "**Clone a profile:**\n"
        "▸ `.zerox` — reply to a user/bot\n"
        "▸ `.zerox @username`\n"
        "▸ `.zerox <user_id>`\n"
        "▸ `.zerox [target] --nodp`\n\n"
        "**Works on:**\n"
        "👤 Users · 🤖 Bots · 📢 Channels · 👥 Groups\n\n"
        "_For channels/groups, the title becomes your name "
        "and the description becomes your bio._\n\n"
        "**Presets:**\n"
        "▸ `.save [name]` — save current\n"
        "▸ `.save dp <n>` — archive DP\n"
        "▸ `.revert [name]` — restore\n"
        "▸ `.presets` — list\n"
        "▸ `.presetdel [name]` — delete"
    )