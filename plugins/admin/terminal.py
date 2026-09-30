"""Terminal — run shell commands on the host from Telegram."""
import asyncio
import os
import signal
import sys
import time
import shlex
from pathlib import Path

from helpers.decorators import command, sudo_only
from utils.messages import Messages
from utils.formatters import Formatters
from Config.settings import Config
from core.logger import setup_logger

logger = setup_logger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent

# Hard limits
MAX_OUTPUT_CHARS = 3500
DEFAULT_TIMEOUT = 20       # seconds
MAX_TIMEOUT = 120          # seconds

# Commands that are always refused, even to sudo.
# These will destroy the host, the deployment, or the session.
_BLOCKED_PATTERNS = (
    "rm -rf /",
    "rm -rf /*",
    "dd if=",
    "mkfs",
    ":(){ :|:& };:",        # fork bomb
    "chmod -R 000 /",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "> /dev/sda",
)

# Currently running background jobs, keyed by user_id → process
_running: dict[int, asyncio.subprocess.Process] = {}


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════

def _is_blocked(cmd: str) -> str | None:
    """Return the offending pattern, or None if the command is allowed."""
    lowered = cmd.lower()
    for pat in _BLOCKED_PATTERNS:
        if pat.lower() in lowered:
            return pat
    return None


def _wrap_output(text: str) -> str:
    """Trim and format output for Telegram."""
    if not text:
        return "(no output)"
    text = text.strip()
    if len(text) > MAX_OUTPUT_CHARS:
        keep = MAX_OUTPUT_CHARS - 60
        text = (
            text[:keep]
            + f"\n\n_… truncated ({len(text) - keep} more chars)_"
        )
    return text


# ══════════════════════════════════════════════════════════════════
#  .sh — run a command
# ══════════════════════════════════════════════════════════════════

@command(r"sh (.+)", "Run a shell command")
@sudo_only
async def sh_handler(event):
    """
    Run a shell command on the host and return its output.

    Usage:
        .sh <command>

    Examples:
        .sh pwd
        .sh ls -la
        .sh python --version
        .sh df -h
        .sh git status

    Notes:
        - Sudo only
        - Output capped at ~3500 chars
        - Timeout: 20s (use `.shbg` for long jobs)
        - Some destructive commands are always blocked
        - Runs in the project root directory
    """
    cmd = event.pattern_match.group(1).strip()

    blocked = _is_blocked(cmd)
    if blocked:
        await event.edit(Messages.error(
            f"🚫 Command blocked (matches `{blocked}`).\n"
            "Refusing to run."
        ))
        return

    await event.edit(Messages.loading(f"$ `{cmd}`"))

    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
            env=os.environ.copy(),
        )
    except Exception as e:
        await event.edit(Messages.error(f"spawn failed: `{e}`"))
        return

    start = time.time()
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=DEFAULT_TIMEOUT)
        elapsed = time.time() - start
        code = proc.returncode
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        await event.edit(Messages.error(
            f"⏱ Timed out after {DEFAULT_TIMEOUT}s.\n"
            f"Use `.shbg <cmd>` for long-running commands."
        ))
        return

    output = stdout.decode("utf-8", errors="replace") if stdout else ""
    body = _wrap_output(output)

    status = "✅" if code == 0 else "❌"
    header = (
        f"{status} **$** `{cmd}`\n"
        f"_exit `{code}` · {elapsed:.2f}s_\n"
        "```\n" + body + "\n```"
    )

    if len(header) > 4000:
        # Send as document if still too big
        import io
        buf = io.BytesIO(output.encode("utf-8"))
        buf.name = "output.txt"
        await event.client.send_file(
            event.chat_id, buf,
            caption=f"{status} `{cmd}` · exit {code} · {elapsed:.2f}s",
            force_document=True,
        )
        await event.delete()
        return

    await event.edit(header)


# ══════════════════════════════════════════════════════════════════
#  .shbg — background command
# ══════════════════════════════════════════════════════════════════

@command(r"shbg(?: (\d+))? (.+)", "Run a long shell command in background")
@sudo_only
async def shbg_handler(event):
    """
    Run a shell command in the background, up to N seconds.

    Usage:
        .shbg <command>             → default 120s timeout
        .shbg <seconds> <command>

    Examples:
        .shbg 60 pip install -r requirements.txt
        .shbg 300 git pull

    Notes:
        - Sudo only
        - Max timeout: 120s
        - Output streamed only at the end
        - Use `.shkill` to abort
    """
    timeout_arg = event.pattern_match.group(1)
    cmd = event.pattern_match.group(2).strip()

    try:
        timeout = int(timeout_arg) if timeout_arg else MAX_TIMEOUT
    except ValueError:
        timeout = MAX_TIMEOUT
    timeout = max(1, min(timeout, MAX_TIMEOUT))

    blocked = _is_blocked(cmd)
    if blocked:
        await event.edit(Messages.error(
            f"🚫 Blocked (`{blocked}`)."
        ))
        return

    sender = event.sender_id
    if sender in _running and _running[sender].returncode is None:
        await event.edit(Messages.error(
            "You already have a background command running. "
            "Use `.shkill` first."
        ))
        return

    await event.edit(Messages.loading(f"$ `{cmd}` · running (max {timeout}s)…"))

    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
            env=os.environ.copy(),
        )
    except Exception as e:
        await event.edit(Messages.error(f"spawn failed: `{e}`"))
        return

    _running[sender] = proc
    start = time.time()

    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        elapsed = time.time() - start
        code = proc.returncode
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        _running.pop(sender, None)
        await event.edit(Messages.error(f"⏱ Timed out after {timeout}s."))
        return
    finally:
        _running.pop(sender, None)

    output = stdout.decode("utf-8", errors="replace") if stdout else ""
    body = _wrap_output(output)
    status = "✅" if code == 0 else "❌"
    header = (
        f"{status} **$** `{cmd}`\n"
        f"_exit `{code}` · {elapsed:.2f}s_\n"
        "```\n" + body + "\n```"
    )
    await event.edit(header)


@command("shkill", "Kill your running background shell command")
@sudo_only
async def shkill_handler(event):
    """
    Terminate the background command you started.

    Usage:
        .shkill
    """
    sender = event.sender_id
    proc = _running.get(sender)
    if proc is None or proc.returncode is not None:
        await event.edit(Messages.warning("No running command to kill."))
        return

    try:
        proc.kill()
        await proc.wait()
        _running.pop(sender, None)
        await event.edit(Messages.success("Process killed."))
    except Exception as e:
        await event.edit(Messages.error(f"Kill failed: `{e}`"))


# ══════════════════════════════════════════════════════════════════
#  .shcd — change working directory for future commands
# ══════════════════════════════════════════════════════════════════

_cwd_state = {"path": PROJECT_ROOT}


@command(r"shcd(?: (.+))?", "Show or change working directory")
@sudo_only
async def shcd_handler(event):
    """
    Show or change the working directory for `.sh` / `.shbg`.

    Usage:
        .shcd                → show current
        .shcd <path>         → change
        .shcd ..             → up one
        .shcd /              → root (dangerous, but allowed)

    Notes:
        - Persists only in memory — resets on restart
        - Sudo only
    """
    arg = event.pattern_match.group(1)

    if not arg:
        await event.edit(Messages.info(
            f"📁 **cwd:** `{_cwd_state['path']}`"
        ))
        return

    target = (Path(_cwd_state["path"]) / arg).resolve() if not arg.startswith("/") \
             else Path(arg).resolve()

    if not target.exists():
        await event.edit(Messages.error(f"Path doesn't exist: `{target}`"))
        return
    if not target.is_dir():
        await event.edit(Messages.error(f"Not a directory: `{target}`"))
        return

    _cwd_state["path"] = target
    await event.edit(Messages.success(f"📁 cwd → `{target}`"))


# ══════════════════════════════════════════════════════════════════
#  .shinfo — system info quick
# ══════════════════════════════════════════════════════════════════

@command("shinfo", "Show host environment info")
@sudo_only
async def shinfo_handler(event):
    """
    Show python version, cwd, user, and platform.

    Usage:
        .shinfo
    """
    import platform
    lines = [
        "🖥 **Host info**\n",
        f"**Python:** `{sys.version.split()[0]}`",
        f"**Platform:** `{platform.platform()}`",
        f"**Machine:** `{platform.machine()}`",
        f"**User:** `{os.environ.get('USER', '?')}`",
        f"**CWD:** `{os.getcwd()}`",
        f"**Project:** `{PROJECT_ROOT}`",
    ]
    await event.edit("\n".join(lines))


# ══════════════════════════════════════════════════════════════════
#  .shexec — pipe a stdin payload into a program
# ══════════════════════════════════════════════════════════════════

@command(r"shexec (.+?) \| (.+)", "Pipe text into a shell command")
@sudo_only
async def shexec_handler(event):
    """
    Send stdin to a command.

    Usage:
        .shexec <command> | <stdin text>

    Examples:
        .shexec cat | hello world
        .shexec wc -c | some text
        .shexec grep foo | bar foo baz

    Notes:
        - Sudo only
        - 20s timeout
    """
    cmd = event.pattern_match.group(1).strip()
    stdin_text = event.pattern_match.group(2)

    blocked = _is_blocked(cmd)
    if blocked:
        await event.edit(Messages.error(f"🚫 Blocked (`{blocked}`)."))
        return

    await event.edit(Messages.loading(f"$ `{cmd}` ← stdin"))

    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
            env=os.environ.copy(),
        )
    except Exception as e:
        await event.edit(Messages.error(f"spawn failed: `{e}`"))
        return

    try:
        stdout, _ = await asyncio.wait_for(
            proc.communicate(input=stdin_text.encode("utf-8")),
            timeout=DEFAULT_TIMEOUT,
        )
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        await event.edit(Messages.error("⏱ Timed out."))
        return

    code = proc.returncode
    body = _wrap_output(stdout.decode("utf-8", errors="replace") if stdout else "")
    status = "✅" if code == 0 else "❌"
    await event.edit(
        f"{status} **$** `{cmd}` ← stdin\n_exit `{code}`_\n"
        "```\n" + body + "\n```"
    )


# ══════════════════════════════════════════════════════════════════
#  .shellhelp
# ══════════════════════════════════════════════════════════════════

@command("shellhelp", "Terminal module help")
async def shellhelp_handler(event):
    """
    Show all terminal commands.

    Usage:
        .shellhelp
    """
    await event.edit(
        "🖥 **TERMINAL**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "• `.sh <cmd>` — run a command (20s timeout)\n"
        "• `.shbg [sec] <cmd>` — long-running command\n"
        "• `.shkill` — abort your running background job\n"
        "• `.shexec <cmd> | <text>` — pipe stdin\n"
        "• `.shcd [path]` — show/change working dir\n"
        "• `.shinfo` — host env info\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ **Sudo only.** Destructive patterns are blocked.\n"
        "⚠️ Output capped at ~3500 chars."
    )