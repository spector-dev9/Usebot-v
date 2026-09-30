"""Alive — comprehensive liveness + system info."""
import asyncio, os, sys, platform, time
from datetime import datetime
from helpers.decorators import command
from utils.messages import Messages, SEP_FANCY
from utils.formatters import Formatters
from Config.settings import Config
from core.logger import setup_logger
try: import psutil
except ImportError: psutil=None
logger=setup_logger(__name__)
def _cpu_percent():
    if psutil is None:return "—"
    try:return f"{psutil.cpu_percent(interval=.3):.1f}%"
    except Exception:return "N/A"
def _ram():
    if psutil is None:return "—"
    try:m=psutil.virtual_memory(); return f"{m.percent:.0f}% · {Formatters.format_size(m.used)}/{Formatters.format_size(m.total)}"
    except Exception:return "N/A"
def _disk():
    if psutil is None:return "—"
    for path in (str(Config.DATA_DIR),"/",os.path.expanduser("~")):
        try:d=psutil.disk_usage(path); return f"{d.percent:.0f}% · {Formatters.format_size(d.used)}/{Formatters.format_size(d.total)}"
        except Exception:continue
    return "N/A"
def _proc_uptime():
    if psutil:
        try:return Formatters.format_duration(time.time()-psutil.Process(os.getpid()).create_time())
        except Exception:pass
    return "—"
def _bot_uptime(event):
    try:
        state=getattr(event.client,"bot_state",None)
        if state and getattr(state,"started_at",None):return Formatters.format_uptime(state.started_at)
    except Exception:pass
    return "—"
def _py_ver():return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
def _os_line():
    p=platform.platform(); return p[:42]+("…" if len(p)>42 else "")
def _uptime_dot(seconds):return "🟢" if seconds<86400 else "💎"
@command("alive","Show bot liveness and system status")
async def alive_handler(event):
    await event.edit("🔋"); await asyncio.sleep(.1); await event.edit("🔋 ˙"); await asyncio.sleep(.1)
    me=await event.client.get_me(); name=me.first_name or "?"; uname=f"@{me.username}" if me.username else "no username"; uid=me.id
    state=getattr(event.client,"bot_state",None); registry=getattr(event.client,"plugin_registry",None); uptime_bot=_bot_uptime(event); uptime_proc=_proc_uptime(); cpu=_cpu_percent(); ram=_ram(); disk=_disk()
    cmds=getattr(state,"command_count",0) if state else 0; errs=getattr(state,"error_count",0) if state else 0; reg_stats=registry.get_stats() if registry else {}; modules=reg_stats.get("total_modules","?"); handlers=reg_stats.get("total_handlers","?")
    uptime_sec=(datetime.now()-state.started_at).total_seconds() if state and getattr(state,"started_at",None) else 0; dot=_uptime_dot(uptime_sec)
    await event.edit(f"💎  **ZEROX IS ALIVE**\n{SEP_FANCY}\n**Account**   {name}\n**Handle**    {uname}\n**User ID**   `{uid}`\n{SEP_FANCY}\n{dot}  **Uptime**      {uptime_bot}\n⚙️  **Process**     {uptime_proc}\n🎯  **Commands**    {cmds}\n⚠️  **Errors**      {errs}\n{SEP_FANCY}\n🧠  **CPU**         {cpu}\n💾  **RAM**         {ram}\n📀  **Disk**        {disk}\n{SEP_FANCY}\n📦  **Modules**     {modules}\n🎁  **Handlers**    {handlers}\n🐍  **Python**      {_py_ver()}\n🖥️  **Platform**    {_os_line()}\n{SEP_FANCY}\n_v{Config.VERSION}  ·  prefix `{Config.CMD_PREFIX}`_")
@command("a","Quick alive check")
async def a_handler(event):
    state=getattr(event.client,"bot_state",None); reg=getattr(event.client,"plugin_registry",None); uptime=Formatters.format_uptime(state.started_at) if state and getattr(state,"started_at",None) else "—"; stats=reg.get_stats() if reg else {}; await event.edit(f"💎 **Alive**  ·  `{uptime}`\n📦 {stats.get('total_modules','?')} modules  ·  🎁 {stats.get('total_handlers','?')} handlers  ·  🧠 {_cpu_percent()}")
