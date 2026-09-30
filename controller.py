#!/usr/bin/env python3
"""ZeroX Controller — optional remote process controller."""
import asyncio
import os
import sys
import time
from pathlib import Path

from telethon import TelegramClient, events

from Config.settings import Config
from core.logger import setup_logger

logger = setup_logger("Controller")
PROJECT_ROOT = Path(__file__).resolve().parent
USERBOT_SCRIPT = PROJECT_ROOT / "main.py"
SESSION_NAME = "controller_session"

_proc = None
_started_at = None
_stop_requested = False


async def _spawn_userbot():
    global _proc, _started_at

    if _proc is not None and _proc.returncode is None:
        return False, "Userbot is already running."

    if not USERBOT_SCRIPT.exists():
        return False, f"`{USERBOT_SCRIPT}` not found."

    try:
        _proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(USERBOT_SCRIPT),
            cwd=str(PROJECT_ROOT),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        _started_at = time.monotonic()
        logger.info("▶️ Userbot started (pid=%s)", _proc.pid)
        return True, f"▶️ Userbot started (pid `{_proc.pid}`)."
    except Exception as e:
        logger.error("spawn failed: %s", e, exc_info=True)
        return False, f"Start failed: `{e}`"


async def _stop_userbot(timeout=15.0):
    global _proc, _started_at

    if _proc is None or _proc.returncode is not None:
        return False, "Userbot is not running."

    proc = _proc
    try:
        proc.terminate()
    except ProcessLookupError:
        _proc = None
        _started_at = None
        return False, "Userbot already exited."

    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass

    _proc = None
    _started_at = None
    return True, "⏹ Userbot stopped."


def _is_running():
    return _proc is not None and _proc.returncode is None


def _uptime():
    if not _is_running() or _started_at is None:
        return "—"
    total = int(time.monotonic() - _started_at)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _tail_logs(n=30):
    log_dir = Path(Config.LOGS_DIR)
    if not log_dir.exists():
        return "(no log dir)"

    files = sorted(
        (p for p in log_dir.rglob("*.log") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        return "(no logs)"

    path = files[0]
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
        lines = data.splitlines()[-n:]
        return f"📄 `{path.name}`\n\n" + "\n".join(lines)
    except Exception as e:
        return f"(read failed: {e})"


def _authorized(event):
    return bool(Config.CONTROL_BOT_ADMIN_ID) and (
        event.sender_id == Config.CONTROL_BOT_ADMIN_ID
    )


def register_handlers(client):
    async def deny(event):
        await event.reply("⛔ Not authorized.")

    @client.on(events.NewMessage(pattern=r"^/start(?:\s+.*)?$"))
    async def cmd_start(event):
        if not _authorized(event):
            return await deny(event)
        global _stop_requested
        _stop_requested = False
        _, msg = await _spawn_userbot()
        await event.reply(msg)

    @client.on(events.NewMessage(pattern=r"^/stop(?:\s+.*)?$"))
    async def cmd_stop(event):
        if not _authorized(event):
            return await deny(event)
        global _stop_requested
        _stop_requested = True
        _, msg = await _stop_userbot()
        await event.reply(msg)

    @client.on(events.NewMessage(pattern=r"^/restart(?:\s+.*)?$"))
    async def cmd_restart(event):
        if not _authorized(event):
            return await deny(event)
        global _stop_requested
        _stop_requested = False
        await event.reply("🔄 Restarting…")
        await _stop_userbot()
        await asyncio.sleep(1)
        _, msg = await _spawn_userbot()
        await event.reply(msg)

    @client.on(events.NewMessage(pattern=r"^/status(?:\s+.*)?$"))
    async def cmd_status(event):
        if not _authorized(event):
            return await deny(event)
        running = _is_running()
        pid = _proc.pid if running and _proc else "—"
        await event.reply(
            "🎛 **ZeroX Controller**\n\n"
            f"**Userbot:** {'🟢 running' if running else '🔴 stopped'}\n"
            f"**PID:** `{pid}`\n"
            f"**Uptime:** {_uptime()}\n"
            f"**Auto-restart:** {'paused' if _stop_requested else 'active'}"
        )

    @client.on(events.NewMessage(pattern=r"^/logs(?:\s+(\d+))?$"))
    async def cmd_logs(event):
        if not _authorized(event):
            return await deny(event)
        n = max(1, min(int(event.pattern_match.group(1) or 30), 200))
        text = _tail_logs(n)
        if len(text) > 3800:
            text = text[-3800:]
        await event.reply(f"```\n{text}\n```")

    @client.on(events.NewMessage(pattern=r"^/help$"))
    async def cmd_help(event):
        if not _authorized(event):
            return await deny(event)
        await event.reply(
            "🎛 **ZeroX Controller**\n\n"
            "`/start` `/stop` `/restart` `/status` `/logs [n]` `/help`"
        )


async def _supervise(client):
    global _proc, _started_at

    while True:
        await asyncio.sleep(5)
        if _stop_requested:
            continue
        if _proc is not None and _proc.returncode is not None:
            code = _proc.returncode
            _proc = None
            _started_at = None
            logger.warning("⚠️ Userbot exited (%s); restarting…", code)
            try:
                await client.send_message(
                    Config.CONTROL_BOT_ADMIN_ID,
                    f"⚠️ Userbot exited (code `{code}`). Restarting…",
                )
            except Exception:
                pass
            await _spawn_userbot()


async def main():
    if not Config.CONTROL_BOT_TOKEN:
        print("❌ CONTROL_BOT_TOKEN is not set")
        return 1
    if not Config.CONTROL_BOT_ADMIN_ID:
        print("❌ CONTROL_BOT_ADMIN_ID is not set")
        return 1

    print("🎛 ZeroX Controller starting…")
    client = TelegramClient(
        SESSION_NAME,
        Config.API_ID,
        Config.API_HASH,
        device_model="ZeroX Controller",
        system_version="Linux",
        app_version=Config.VERSION,
    )

    await client.start(bot_token=Config.CONTROL_BOT_TOKEN)
    me = await client.get_me()
    logger.info("✅ Controller online as @%s", me.username or me.id)

    register_handlers(client)
    await _spawn_userbot()
    asyncio.create_task(_supervise(client))

    try:
        await client.send_message(
            Config.CONTROL_BOT_ADMIN_ID,
            "🎛 Controller online. `/help` for commands.",
        )
    except Exception:
        pass

    await client.run_until_disconnected()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n👋 Controller stopped.")
