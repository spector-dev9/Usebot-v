"""Logs — view, delete, auto-clean."""
import asyncio
import time
from datetime import datetime
from pathlib import Path

from helpers.decorators import command, sudo_only
from utils.messages import Messages
from utils.formatters import Formatters
from Config.settings import Config
from core.logger import setup_logger

logger = setup_logger(__name__)
AUTO = {"enabled": False, "keep_days": 3, "task": None}


def _logs_dir() -> Path:
    """Resolve logs dir safely, creating if missing."""
    try:
        d = Path(Config.LOGS_DIR)
    except Exception:
        d = Path(Config.BASE_DIR) / "data" / "logs"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return d


def _list():
    d = _logs_dir()
    if not d.exists():
        return []
    fs = []
    for f in d.rglob("*"):
        try:
            if f.is_file():
                fs.append(f)
        except (PermissionError, OSError):
            continue
    fs.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return fs


def _size():
    total = 0
    for f in _list():
        try:
            total += f.stat().st_size
        except (PermissionError, OSError):
            pass
    return total


def _human(s):
    if s < 60: return f"{int(s)}s"
    if s < 3600: return f"{int(s/60)}m"
    if s < 86400: return f"{s/3600:.1f}h"
    return f"{s/86400:.1f}d"


@command("loglist", "List log files")
@sudo_only
async def loglist_handler(event):
    """Usage: `.loglist`"""
    fs = _list()
    d = _logs_dir()
    if not fs:
        await event.edit(Messages.info(
            f"No log files.\n\n_Path:_ `{d}`\n"
            f"_Exists:_ {'yes' if d.exists() else 'no'}"
        )); return
    now = time.time()
    lines = [f"📄 **LOGS**  ·  {Formatters.format_size(_size())} total\n",
             f"_Path:_ `{d}`\n", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    for f in fs[:20]:
        try:
            sz = Formatters.format_size(f.stat().st_size)
            age = _human(now - f.stat().st_mtime)
            lines.append(f"▸ `{f.name}`  —  {sz}  ·  {age} ago")
        except Exception:
            lines.append(f"▸ `{f.name}`")
    if len(fs) > 20:
        lines.append(f"\n_…and {len(fs)-20} more_")
    await event.edit("\n".join(lines))


@command(r"logview(?:\s+(\d+))?", "Send newest log")
@sudo_only
async def logview_handler(event):
    """Usage: `.logview [n]`"""
    n = int(event.pattern_match.group(1) or 1)
    fs = _list()
    if not fs:
        await event.edit(Messages.error("No log files.")); return
    if n < 1 or n > len(fs):
        await event.edit(Messages.error(f"Only {len(fs)} file(s).")); return
    target = fs[n-1]
    await event.edit(Messages.loading(f"Sending `{target.name}`..."))
    try:
        await event.client.send_file(
            "me", str(target),
            caption=f"📄 `{target.name}` · {Formatters.format_size(target.stat().st_size)}",
            force_document=True,
        )
    except Exception as e:
        logger.error(f"send log: {e}", exc_info=True)
        await event.edit(Messages.error(f"Send failed: {e}")); return
    await event.edit(Messages.success(f"Sent `{target.name}`."))


@command(r"logdel(?:\s+(\w+))?", "Delete log files")
@sudo_only
async def logdel_handler(event):
    """Usage: `.logdel [all|old|<name>]`"""
    arg = (event.pattern_match.group(1) or "").strip()
    today = datetime.now().strftime("%Y%m%d")
    active = f"userbot_{today}.log"
    fs = _list()
    if not fs:
        await event.edit(Messages.error("No log files.")); return

    if arg and arg not in ("all", "old"):
        t = next((f for f in fs if f.name == arg), None)
        if not t:
            await event.edit(Messages.error(f"`{arg}` not found.")); return
        try:
            if t.name == active:
                t.write_text("")
                await event.edit(Messages.success(f"`{arg}` truncated."))
            else:
                sz = t.stat().st_size; t.unlink()
                await event.edit(Messages.success(f"Deleted `{arg}` — freed {Formatters.format_size(sz)}."))
        except Exception as e:
            await event.edit(Messages.error(f"Failed: {e}"))
        return

    to_del = [f for f in fs if f.name != active]
    if not to_del:
        await event.edit(Messages.info("Nothing to delete.")); return
    freed = deleted = 0
    for f in to_del:
        try:
            freed += f.stat().st_size; f.unlink(); deleted += 1
        except Exception:
            pass
    if arg != "old":
        a = _logs_dir() / active
        if a.exists():
            try: a.write_text("")
            except Exception: pass
    await event.edit(Messages.success(
        f"Deleted **{deleted}** file(s) — freed {Formatters.format_size(freed)}."
    ))


@command(r"logauto(?:\s+(on|off|\d+))?", "Auto-clean logs")
@sudo_only
async def logauto_handler(event):
    """Usage: `.logauto [on|off|<days>]`"""
    arg = (event.pattern_match.group(1) or "").strip().lower()
    if not arg:
        st = "🟢 ON" if AUTO["enabled"] else "🔴 OFF"
        await event.edit(Messages.info(f"Auto-clean: **{st}** · keep **{AUTO['keep_days']}d**")); return
    if arg == "off":
        AUTO["enabled"] = False
        await event.edit(Messages.success("Auto-clean off.")); return
    if arg == "on":
        AUTO["enabled"] = True
    elif arg.isdigit():
        AUTO["enabled"] = True; AUTO["keep_days"] = max(1, int(arg))
    else:
        await event.edit(Messages.error("Usage: `.logauto on|off|<days>`")); return
    if AUTO["task"] is None or AUTO["task"].done():
        AUTO["task"] = asyncio.create_task(_loop())
    await event.edit(Messages.success(f"Auto-clean on — keep {AUTO['keep_days']}d."))


@command("logwipe", "Truncate active log")
@sudo_only
async def logwipe_handler(event):
    """Usage: `.logwipe`"""
    today = datetime.now().strftime("%Y%m%d")
    active = _logs_dir() / f"userbot_{today}.log"
    if not active.exists():
        await event.edit(Messages.error("No active log.")); return
    try:
        sz = active.stat().st_size; active.write_text("")
        await event.edit(Messages.success(f"Truncated — freed {Formatters.format_size(sz)}."))
    except Exception as e:
        await event.edit(Messages.error(f"Failed: {e}"))


async def _loop():
    while AUTO["enabled"]:
        try:
            await asyncio.sleep(6*3600)
            if not AUTO["enabled"]: break
            cutoff = time.time() - AUTO["keep_days"]*86400
            today = datetime.now().strftime("%Y%m%d")
            active = f"userbot_{today}.log"
            for f in _list():
                if f.name == active: continue
                try:
                    if f.stat().st_mtime < cutoff: f.unlink()
                except Exception: pass
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"clean loop: {e}")


@command("loghelp", "Log manager help")
async def loghelp_handler(event):
    await event.edit(
        "📄 **LOG MANAGER**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "• `.loglist` — list files\n"
        "• `.logview [n]` — send log → Saved\n"
        "• `.logdel [all|old|<name>]` — delete\n"
        "• `.logwipe` — truncate active\n"
        "• `.logauto on|off|<days>` — schedule\n\n"
        "⚠️ Sudo only."
    )
