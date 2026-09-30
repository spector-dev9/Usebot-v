"""Sendonce — send yourself test view-once / self-destruct media."""
import io
import random

import httpx

from helpers.decorators import command
from utils.messages import Messages
from core.logger import setup_logger

logger = setup_logger(__name__)

VIEW_ONCE = 2147483647  # Telegram's max-int32 marker for view-once

TIMERS = {
    "5": 5,
    "10": 10,
    "30": 30,
    "60": 60,
    "1m": 60,
    "2m": 120,
    "5s": 5,
    "10s": 10,
    "30s": 30,
    "60s": 60,
    "5m": 300,
}

# Image sources (all free, keyless)
PICSUM = "https://picsum.photos/720/720?random={r}"
LOREMFLICKR = "https://loremflickr.com/720/720/{kw}?random={r}"

# Some fun keywords that work well with loremflickr
SUGGESTED_KEYWORDS = [
    "nature", "city", "mountain", "ocean", "forest",
    "cat", "dog", "bird", "flower", "sunset",
    "snow", "desert", "rain", "food", "coffee",
]


async def _fetch_image(keyword: str | None) -> tuple[io.BytesIO | None, str]:
    """
    Fetch a random image.
    Returns (buffer, description) or (None, "").
    """
    seed = random.randint(1, 999999)
    if keyword:
        url = LOREMFLICKR.format(kw=keyword, r=seed)
        desc = f"tag: `{keyword}`"
    else:
        url = PICSUM.format(r=seed)
        desc = "random"

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
            r = await c.get(url)
            r.raise_for_status()
            buf = io.BytesIO(r.content)
            buf.name = f"once_{seed}.jpg"
            return buf, desc
    except Exception as e:
        logger.warning(f"sendonce fetch ({keyword or 'random'}): {e}")
        return None, ""


def _parse_args(raw: str | None) -> tuple[int, str | None]:
    """
    Parse the command args.
    Returns (ttl, keyword).
    Accepts:
        ""              → view-once, random image
        "5"             → 5s, random image
        "cat"           → view-once, cat image
        "5 cat"         → 5s, cat image
        "view cat"      → view-once, cat image
    """
    if not raw:
        return VIEW_ONCE, None

    parts = raw.strip().split(None, 1)
    first = parts[0].lower()

    # First token is a timer / view marker
    if first in ("view", "once"):
        ttl = VIEW_ONCE
        keyword = parts[1].strip() if len(parts) > 1 else None
        return ttl, keyword

    if first in TIMERS:
        ttl = TIMERS[first]
        keyword = parts[1].strip() if len(parts) > 1 else None
        return ttl, keyword

    # First token is not a timer → treat entire input as keyword
    return VIEW_ONCE, raw.strip()


@command(r"once(?: (.+))?", "Send test view-once / self-destruct media")
async def once_handler(event):
    """
    Send yourself test ephemeral media to exercise `.grab`.

    Usage:
        .once                    → view-once random photo
        .once cat                → view-once cat photo
        .once 5                  → 5-second self-destruct random photo
        .once 5 cat              → 5-second cat photo
        .once 30 nature          → 30-second nature photo
        .once view               → view-once random photo (same as .once)

    Notes:
        - Random image from picsum.photos
        - Keywords route through loremflickr.com
        - Then reply to it with `.grab` to save
    """
    raw = event.pattern_match.group(1)
    ttl, keyword = _parse_args(raw)

    if ttl == VIEW_ONCE:
        label = "view-once"
    else:
        label = f"self-destruct {ttl}s"

    await event.edit(Messages.loading(
        f"Preparing {label} image…"
    ))

    buf, desc = await _fetch_image(keyword)
    if not buf:
        await event.edit(Messages.error(
            "Couldn't fetch image. Try again or use a different keyword."
        ))
        return

    caption = (
        f"🧪 Test **{label}**\n"
        f"Image: {desc}"
    )

    try:
        await event.client.send_file(
            event.chat_id,
            buf,
            caption=caption,
            ttl=ttl,
        )
        await event.delete()
    except Exception as e:
        logger.error(f"sendonce send: {e}", exc_info=True)
        try:
            await event.edit(Messages.error(f"Send failed: `{e}`"))
        except Exception:
            pass


@command("oncehelp", "Sendonce help")
async def oncehelp_handler(event):
    """Usage: `.oncehelp`"""
    sample = " · ".join(f"`{k}`" for k in SUGGESTED_KEYWORDS[:8])
    await event.edit(
        "🧪 **SENDONCE — Test ephemeral media**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "**Random image:**\n"
        "• `.once` — view-once\n"
        "• `.once 5` — 5s self-destruct\n"
        "• `.once 10` — 10s\n"
        "• `.once 30` — 30s\n"
        "• `.once 60` — 1 minute\n\n"
        "**Themed image:**\n"
        "• `.once cat` — view-once cat photo\n"
        "• `.once 30 nature` — 30s nature photo\n"
        "• `.once city` — view-once city photo\n\n"
        f"**Suggested keywords:** {sample}\n\n"
        "**Test flow:**\n"
        "1. Send `.once` here\n"
        "2. Reply to the media with `.grab`\n"
        "3. Check `data/downloads/`"
    )