"""Timezone — convert time between zones, show current time."""
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from helpers.decorators import command
from utils.messages import Messages

_ALIASES = {
    "ist": "Asia/Kolkata", "pst": "America/Los_Angeles", "pdt": "America/Los_Angeles",
    "mst": "America/Denver", "mdt": "America/Denver", "cst": "America/Chicago",
    "cdt": "America/Chicago", "est": "America/New_York", "edt": "America/New_York",
    "gmt": "Etc/GMT", "utc": "UTC", "bst": "Europe/London", "cet": "Europe/Paris",
    "cest": "Europe/Paris", "eet": "Europe/Bucharest", "jst": "Asia/Tokyo",
    "kst": "Asia/Seoul", "sgt": "Asia/Singapore", "hkt": "Asia/Hong_Kong",
    "aest": "Australia/Sydney", "aedt": "Australia/Sydney", "nzst": "Pacific/Auckland",
}

def _resolve(name: str) -> ZoneInfo:
    name = name.strip()
    return ZoneInfo(_ALIASES.get(name.lower(), name))

@command(r"time(?: (.+))?", "Show current time in a zone")
async def time_handler(event):
    arg = (event.pattern_match.group(1) or "UTC").strip()
    try:
        tz = _resolve(arg)
    except Exception:
        await event.edit(Messages.error(f"Unknown zone `{arg}`."))
        return
    now = datetime.now(tz)
    await event.edit(f"🕒 **{tz.key}**\n`{now.strftime('%Y-%m-%d %H:%M:%S %Z %z')}`")

@command(r"tz (.+?) to (.+)", "Convert current time to another zone")
async def tz_handler(event):
    src, dst = event.pattern_match.group(1).strip(), event.pattern_match.group(2).strip()
    try:
        src_tz, dst_tz = _resolve(src), _resolve(dst)
    except Exception as e:
        await event.edit(Messages.error(f"Zone error: `{e}`"))
        return
    now_src = datetime.now(src_tz)
    now_dst = now_src.astimezone(dst_tz)
    await event.edit(
        f"🌍 **Time conversion**\n"
        f"• **{src_tz.key}:** `{now_src.strftime('%H:%M %d %b')}`\n"
        f"• **{dst_tz.key}:** `{now_dst.strftime('%H:%M %d %b')}`"
    )

@command(r"tzat (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) (.+?) to (.+)", "Convert a specific datetime")
async def tzat_handler(event):
    when_str = event.pattern_match.group(1)
    src, dst = event.pattern_match.group(2).strip(), event.pattern_match.group(3).strip()
    try:
        src_tz, dst_tz = _resolve(src), _resolve(dst)
        when = datetime.strptime(when_str, "%Y-%m-%d %H:%M").replace(tzinfo=src_tz)
    except ZoneInfoNotFoundError as e:
        await event.edit(Messages.error(f"Zone error: `{e}`"))
        return
    except ValueError as e:
        await event.edit(Messages.error(f"Bad datetime: `{e}`"))
        return
    converted = when.astimezone(dst_tz)
    await event.edit(f"🌍 **{when_str} {src_tz.key}**\n→ `{converted.strftime('%Y-%m-%d %H:%M %Z')}`")

@command("timezones", "Show world clock for major cities")
async def timezones_handler(event):
    cities = [("UTC","UTC"),("IST","Asia/Kolkata"),("London","Europe/London"),
              ("New York","America/New_York"),("Los Angeles","America/Los_Angeles"),
              ("Tokyo","Asia/Tokyo"),("Sydney","Australia/Sydney")]
    lines = ["🌍 **World clock**\n"]
    for label, key in cities:
        try:
            now = datetime.now(ZoneInfo(key))
            lines.append(f"• **{label}:** `{now.strftime('%H:%M %d %b')}`")
        except Exception:
            continue
    await event.edit("\n".join(lines))

@command("timehelp", "Timezone help")
async def timehelp_handler(event):
    await event.edit(
        "🕒 **TIMEZONE**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "• `.time [zone]` — current time\n"
        "• `.tz <src> to <dst>` — convert now\n"
        "• `.tzat <YYYY-MM-DD HH:MM> <src> to <dst>`\n"
        "• `.timezones` — world clock\n\n"
        "Aliases: IST, EST, PST, GMT, JST, …\nOr full: `America/New_York`"
    )
