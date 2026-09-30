"""Files — browse, download, and navigate the userbot's data folder."""
import io
from pathlib import Path

from helpers.decorators import command, sudo_only
from utils.messages import Messages
from utils.formatters import Formatters
from Config.settings import Config
from core.logger import setup_logger

logger = setup_logger(__name__)

ALLOWED_ROOTS = [Path(Config.DATA_DIR)]
DOWNLOADS = Path(Config.DATA_DIR) / "downloads"

# Per-user current directory (relative to DATA_DIR)
_cwd: dict[int, str] = {}


def _is_safe(path: Path) -> bool:
    try:
        p = path.resolve()
        return any(
            p == root.resolve() or str(p).startswith(str(root.resolve()) + "/")
            for root in ALLOWED_ROOTS
        )
    except Exception:
        return False


def _normalize(rel: str) -> str:
    """Normalize a relative path: strip '.', collapse '..'."""
    parts = []
    for p in rel.split("/"):
        if not p or p == ".":
            continue
        if p == "..":
            if parts:
                parts.pop()
            continue
        parts.append(p)
    return "/".join(parts)


def _resolve_path(uid: int, arg: str) -> Path:
    """Resolve a path argument relative to the user's cwd."""
    current = _cwd.get(uid, "")
    if not arg:
        rel = current
    elif arg.startswith("/"):
        rel = arg.lstrip("/")
    else:
        rel = f"{current}/{arg}" if current else arg
    rel = _normalize(rel)
    return (Path(Config.DATA_DIR) / rel) if rel else Path(Config.DATA_DIR)


# ──────────────────────────────────────────────────────────────────
#  .cd
# ──────────────────────────────────────────────────────────────────

@command(r"cd(?: (.+))?", "Change or show current directory")
@sudo_only
async def cd_handler(event):
    """Usage: `.cd [path|..|/]`"""
    sub = (event.pattern_match.group(1) or "").strip()
    uid = event.sender_id
    current = _cwd.get(uid, "")

    if not sub:
        await event.edit(Messages.info(f"📁 **cwd:** `data/{current}`"))
        return

    if sub in ("/", "data", "~"):
        _cwd[uid] = ""
        await event.edit(Messages.success("📁 cwd → `data/`"))
        return

    if sub == "..":
        parts = current.split("/") if current else []
        new_rel = "/".join(parts[:-1])
    elif sub.startswith("/"):
        new_rel = _normalize(sub.lstrip("/"))
    else:
        new_rel = _normalize(f"{current}/{sub}" if current else sub)

    target = Path(Config.DATA_DIR) / new_rel if new_rel else Path(Config.DATA_DIR)
    if not _is_safe(target):
        await event.edit(Messages.error("Path outside data/ is not allowed."))
        return
    if not target.exists():
        await event.edit(Messages.error(f"Not found: `data/{new_rel}`"))
        return
    if not target.is_dir():
        await event.edit(Messages.error(f"Not a directory: `data/{new_rel}`"))
        return

    _cwd[uid] = new_rel
    await event.edit(Messages.success(f"📁 cwd → `data/{new_rel}`"))


# ──────────────────────────────────────────────────────────────────
#  .ls
# ──────────────────────────────────────────────────────────────────

@command(r"ls(?: (.+))?", "List files")
@sudo_only
async def ls_handler(event):
    """Usage: `.ls [subpath]`"""
    sub = (event.pattern_match.group(1) or "").strip()
    target = _resolve_path(event.sender_id, sub)

    if not _is_safe(target):
        await event.edit(Messages.error("Path outside data/ is not allowed."))
        return
    if not target.exists():
        await event.edit(Messages.error(f"Not found: `{target}`"))
        return
    if not target.is_dir():
        await event.edit(Messages.error(f"Not a directory: `{target}`"))
        return

    try:
        entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name))
    except Exception as e:
        await event.edit(Messages.error(f"Read failed: `{e}`"))
        return

    if not entries:
        await event.edit(Messages.info(f"`{target}` is empty."))
        return

    try:
        rel = target.relative_to(Config.DATA_DIR)
    except ValueError:
        rel = target

    lines = [f"📁 **`data/{rel}`**\n"]
    total_size = 0
    dirs = files = 0

    for p in entries[:40]:
        try:
            if p.is_dir():
                sub_count = len(list(p.iterdir()))
                lines.append(f"📂 `{p.name}/`  ·  {sub_count} item(s)")
                dirs += 1
            else:
                sz = p.stat().st_size
                total_size += sz
                lines.append(f"📄 `{p.name}`  ·  {Formatters.format_size(sz)}")
                files += 1
        except Exception:
            continue

    if len(entries) > 40:
        lines.append(f"\n_…+{len(entries)-40} more_")

    lines.append(
        f"\n**{dirs} folder(s) · {files} file(s) · "
        f"{Formatters.format_size(total_size)}**"
    )
    await event.edit("\n".join(lines))


# ──────────────────────────────────────────────────────────────────
#  .getfile
# ──────────────────────────────────────────────────────────────────

@command(r"getfile (.+)", "Download a file")
@sudo_only
async def getfile_handler(event):
    """Usage: `.getfile <path>`"""
    raw = event.pattern_match.group(1).strip()
    target = _resolve_path(event.sender_id, raw)

    if not _is_safe(target):
        await event.edit(Messages.error("Path outside data/ is not allowed."))
        return
    if not target.exists():
        await event.edit(Messages.error(f"Not found: `{raw}`"))
        return

    if target.is_dir():
        files = [f for f in target.iterdir() if f.is_file()]
        if not files:
            await event.edit(Messages.error(f"`{raw}` has no files."))
            return
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        target = files[0]

    await event.edit(Messages.loading(f"Sending `{target.name}`…"))

    try:
        await event.client.send_file(
            event.chat_id, str(target),
            caption=(
                f"📄 `{target.relative_to(Config.DATA_DIR)}`\n"
                f"💾 {Formatters.format_size(target.stat().st_size)}"
            ),
            force_document=True,
        )
        await event.delete()
    except Exception as e:
        logger.error(f"getfile: {e}", exc_info=True)
        await event.edit(Messages.error(f"Send failed: `{e}`"))


# ──────────────────────────────────────────────────────────────────
#  .rmfile
# ──────────────────────────────────────────────────────────────────

@command(r"rmfile (.+)", "Delete a file")
@sudo_only
async def rmfile_handler(event):
    """Usage: `.rmfile <path>`"""
    raw = event.pattern_match.group(1).strip()
    target = _resolve_path(event.sender_id, raw)

    if not _is_safe(target):
        await event.edit(Messages.error("Path outside data/ is not allowed."))
        return
    if not target.exists():
        await event.edit(Messages.error(f"Not found: `{raw}`"))
        return

    if target.is_dir():
        deleted = 0
        for f in target.iterdir():
            if f.is_file():
                try:
                    f.unlink()
                    deleted += 1
                except Exception:
                    pass
        await event.edit(Messages.success(f"Deleted {deleted} file(s) in `{raw}`."))
        return

    try:
        target.unlink()
        await event.edit(Messages.success(f"Deleted `{raw}`."))
    except Exception as e:
        await event.edit(Messages.error(f"Delete failed: `{e}`"))


# ──────────────────────────────────────────────────────────────────
#  .pwd + .filehelp
# ──────────────────────────────────────────────────────────────────

@command("pwd", "Show current directory")
@sudo_only
async def pwd_handler(event):
    """Usage: `.pwd`"""
    current = _cwd.get(event.sender_id, "")
    await event.edit(f"📁 `data/{current}`")


@command("filehelp", "Files module help")
async def filehelp_handler(event):
    """Usage: `.filehelp`"""
    await event.edit(
        "📁 **FILES**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "**Navigation:**\n"
        "• `.cd` — show current directory\n"
        "• `.cd <folder>` — enter folder\n"
        "• `.cd ..` — go up one level\n"
        "• `.cd /` — back to data/\n"
        "• `.pwd` — show absolute path\n\n"
        "**Browse & transfer:**\n"
        "• `.ls [subpath]` — list contents\n"
        "• `.getfile <path>` — download to this chat\n"
        "• `.rmfile <path>` — delete a file\n\n"
        "**Examples:**\n"
        "• `.cd downloads`\n"
        "• `.ls`\n"
        "• `.getfile photo.jpg`\n"
        "• `.cd ..`\n\n"
        "Traversal out of `data/` is blocked."
    )