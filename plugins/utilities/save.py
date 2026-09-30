"""Save current Telegram profile as a named preset, or save a DP."""
from sqlalchemy import select, delete
import io
import time
from pathlib import Path

from sqlalchemy import select
from telethon import functions

from helpers.decorators import command
from utils.messages import Messages
from Config.settings import Config
from core.logger import setup_logger
from database.connection import get_session
from database.models import Preset

logger = setup_logger(__name__)

PRESETS_DIR = Path(Config.DATA_DIR) / "presets"


# ─────────────────────── telegram helpers ───────────────────────

async def _get_full_user(client, user_id: int):
    return await client(functions.users.GetFullUserRequest(id=user_id))


async def _photos(client, user_id: int, limit: int = 0):
    try:
        res = await client(functions.photos.GetUserPhotosRequest(
            user_id=user_id, offset=0, max_id=0, limit=limit
        ))
        return res.photos
    except Exception as e:
        logger.warning(f"photo fetch failed: {e}")
        return []


async def _download_to_path(client, user_id: int, photo) -> str | None:
    """Download DP to data/presets/<user_id>/<ts>.jpg, return path."""
    if photo is None:
        return None
    try:
        user_dir = PRESETS_DIR / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        path = user_dir / f"{int(time.time())}.jpg"
        await client.download_media(photo, file=str(path))
        return str(path)
    except Exception as e:
        logger.warning(f"photo download failed: {e}")
        return None


async def _download_to_buffer(client, photo) -> io.BytesIO:
    buf = io.BytesIO()
    await client.download_media(photo, file=buf)
    buf.seek(0)
    return buf


# ─────────────────────── .save dp <n> ───────────────────────

async def _handle_save_dp(event, arg: str):
    """Reply to a user, save their nth DP to Saved Messages."""
    parts = arg.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await event.edit(Messages.error(
            "Usage: `.save dp <number>` (reply to a user)."
        ))
        return

    n = int(parts[1])
    if n < 1:
        await event.edit(Messages.error("Number must be ≥ 1 (1 = latest)."))
        return

    if not event.is_reply:
        await event.edit(Messages.error("Reply to a user to save their DP."))
        return

    replied = await event.get_reply_message()
    target = await replied.get_sender()
    if target is None:
        await event.edit(Messages.error("Couldn't resolve target user."))
        return

    photos = await _photos(event.client, target.id, limit=0)
    if not photos:
        await event.edit(Messages.error("That user has no profile photos."))
        return
    if n > len(photos):
        await event.edit(Messages.error(f"Only {len(photos)} DP(s) available."))
        return

    photo = photos[n - 1]
    buf = await _download_to_buffer(event.client, photo)
    buf.name = f"dp_{target.id}_{n}.jpg"
    await event.client.send_file(
        "me", buf,
        caption=f"DP #{n} of {target.first_name or target.id}",
    )
    await event.edit(Messages.success(
        f"Saved DP #{n} of **{target.first_name}** to Saved Messages."
    ))


# ─────────────────────── .save [name] ───────────────────────

async def _handle_save_preset(event, preset_name: str):
    """Snapshot current profile into the database."""
    await event.edit(Messages.loading(f"Saving preset `{preset_name}`..."))

    me = await event.client.get_me()
    full = await _get_full_user(event.client, me.id)
    bio = full.full_user.about or ""
    username = me.username or ""

    photos = await _photos(event.client, me.id, limit=1)
    photo_ref = await _download_to_path(
        event.client, me.id, photos[0] if photos else None
    )

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
                preset = Preset(
                    user_id=me.id,
                    name=preset_name,
                    first_name=me.first_name or "",
                    last_name=me.last_name or "",
                    bio=bio,
                    username=username,
                    photo_reference=photo_ref,
                )
                session.add(preset)
                action = "created"
            else:
                preset.first_name = me.first_name or ""
                preset.last_name = me.last_name or ""
                preset.bio = bio
                preset.username = username
                if photo_ref:
                    preset.photo_reference = photo_ref
                action = "updated"
    except Exception as e:
        logger.error(f"DB save failed: {e}", exc_info=True)
        await event.edit(Messages.error(f"Database error: {e}"))
        return

    display_name = f"{me.first_name or ''} {me.last_name or ''}".strip() or "—"
    msg = f"✅ **Preset `{preset_name}` {action}**\n"
    msg += Messages.format_key_value("Name", display_name) + "\n"
    msg += Messages.format_key_value("Bio", f"{len(bio)} chars") + "\n"
    msg += Messages.format_key_value("Photo", "✅ stored" if photo_ref else "—")
    await event.edit(msg)


# ─────────────────────── single entry point ───────────────────────

@command("save(?:\\s+(.*))?", "Save current profile preset or a DP")
async def save_handler(event):
    """
    Save your current profile as a preset, or save a DP.

    Two modes:
      1. Preset save    — snapshots name + bio + username + DP
      2. DP save        — downloads a specific DP of the replied
                          user to your Saved Messages

    Usage:
        .save               save as "default"
        .save <name>        save/overwrite preset "<name>"
        .save dp <n>        save replied user's nth DP (1 = latest)

    Examples:
        .save
        .save gaming
        .save work
        .save dp 1
        .save dp 3
    """
    arg = (event.pattern_match.group(1) or "").strip()

    if arg.lower().startswith("dp"):
        await _handle_save_dp(event, arg)
        return

    preset_name = arg or "default"
    await _handle_save_preset(event, preset_name)
@command("presetdel(?:\\s+(.*))?", "Delete a saved preset")
async def delpreset_handler(event):
    """
    Delete a saved profile preset from the database.

    Removes the preset row and (optionally) the DP file on
    disk. Confirmation is required to prevent accidents.

    Usage:
        .delpreset              delete "default" preset
        .delpreset <name>       delete a specific preset

    Examples:
        .delpreset
        .delpreset gaming
        .delpreset work

    Notes:
        - Default preset name is "default"
        - Removes the associated DP file if one is stored
        - Irreversible — no undo
        - Use .presets to see what's available first
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
                # list what's available
                avail_result = await session.execute(
                    select(Preset.name).where(Preset.user_id == me.id)
                )
                available = [r[0] for r in avail_result.all()]
                avail = ", ".join(available) or "none"
                await event.edit(Messages.error(
                    f"Preset `{preset_name}` not found. Available: {avail}"
                ))
                return

            dp_file = preset.photo_reference
            await session.delete(preset)
    except Exception as e:
        logger.error(f"DB delete failed: {e}", exc_info=True)
        await event.edit(Messages.error(f"Database error: {e}"))
        return

    # Try to remove the DP file too
    dp_status = "—"
    if dp_file:
        try:
            p = Path(dp_file)
            if p.exists():
                p.unlink()
                dp_status = "deleted"
            else:
                dp_status = "missing"
        except Exception as e:
            logger.warning(f"could not delete DP file: {e}")
            dp_status = "kept"

    await event.edit(Messages.success(
        f"Deleted preset **{preset_name}** (dp: {dp_status})."
    ))