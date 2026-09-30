"""Module manager — upload, unload, delete, reload modules, export project."""
import io
import re
import zipfile
from pathlib import Path

from helpers.decorators import command, sudo_only
from utils.messages import Messages
from utils.formatters import Formatters
from Config.settings import Config
from core.logger import setup_logger

logger = setup_logger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
PLUGINS_DIR = PROJECT_ROOT / "plugins"

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")


# ══════════════════════════════════════════════════════════════════
#  ZIP HELPERS
# ══════════════════════════════════════════════════════════════════

# Folders/files excluded from code-only export
_EXPORT_EXCLUDE_DIRS = {
    "venv", "env", ".venv", ".git", "__pycache__",
    "data", "logs", ".idea", ".vscode",
}
_EXPORT_EXCLUDE_SUFFIXES = (".pyc", ".pyo", ".session", ".session-journal", ".zip")


def _should_include(path: Path) -> bool:
    """Filter function for code-only export."""
    parts = set(path.parts)
    if parts & _EXPORT_EXCLUDE_DIRS:
        return False
    if path.name == ".env":
        return False
    if path.suffix in _EXPORT_EXCLUDE_SUFFIXES:
        return False
    if path.name.endswith(".session") or ".session-" in path.name:
        return False
    if path.name == "zerox.db":
        return False
    return True


def _build_zip(root: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(root)
            if any(part in _EXPORT_EXCLUDE_DIRS for part in rel.parts):
                continue
            if not _should_include(file_path):
                continue
            zf.write(file_path, arcname=str(rel))
    buf.seek(0)
    return buf.read()


# Folders excluded from full export
_FULL_EXPORT_EXCLUDE_DIRS = {"venv", "env", ".venv", "__pycache__", ".git"}
_FULL_EXPORT_EXCLUDE_SUFFIXES = (".pyc", ".pyo")


def _should_include_full(path: Path) -> bool:
    """Include EVERYTHING except junk that's regenerable."""
    if path.suffix in _FULL_EXPORT_EXCLUDE_SUFFIXES:
        return False
    if path.name.endswith(".pyc") or path.name.endswith(".pyo"):
        return False
    return True


def _build_full_zip(root: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(root)
            if any(part in _FULL_EXPORT_EXCLUDE_DIRS for part in rel.parts):
                continue
            if not _should_include_full(file_path):
                continue
            zf.write(file_path, arcname=str(rel))
    buf.seek(0)
    return buf.read()


# ══════════════════════════════════════════════════════════════════
#  LOAD — upload a .py file as a new module
# ══════════════════════════════════════════════════════════════════

@command("modload(?:\\s+(\\w+))?", "Upload a .py file as a new module")
@sudo_only
async def modload_handler(event):
    """
    Upload a Python file as a plugin module.

    Reply to a .py file with this command. Optionally pass a
    category as an argument — defaults to "utilities".

    Usage:
        .modload                     (reply to .py → utilities/)
        .modload admin               (reply to .py → admin/)
        .modload utilities           (reply to .py → utilities/)

    Examples:
        .modload
        .modload admin

    Notes:
        - File name must be snake_case, no spaces
        - Overwrites if a module with the same name exists
        - Module is loaded immediately — no restart needed
        - Sudo only
    """
    if not event.is_reply:
        await event.edit(Messages.error("Reply to a `.py` file to load it."))
        return

    replied = await event.get_reply_message()
    if not replied.document:
        await event.edit(Messages.error("The replied message has no file."))
        return

    file_name = None
    for attr in replied.document.attributes:
        if hasattr(attr, "file_name"):
            file_name = attr.file_name
            break

    if not file_name or not file_name.endswith(".py"):
        await event.edit(Messages.error("Only `.py` files are supported."))
        return

    module_name = Path(file_name).stem.lower()
    if not _NAME_RE.match(module_name):
        await event.edit(Messages.error(
            f"Invalid module name `{module_name}`.\n"
            "Use snake_case: `my_module`, `group_tools`, etc."
        ))
        return

    category = (event.pattern_match.group(1) or "utilities").strip().lower()
    if not _NAME_RE.match(category):
        await event.edit(Messages.error("Invalid category name."))
        return

    await event.edit(Messages.loading(f"Downloading `{file_name}`..."))

    try:
        buf = io.BytesIO()
        await event.client.download_media(replied, file=buf)
        buf.seek(0)
        source = buf.read().decode("utf-8")
    except Exception as e:
        logger.error(f"download failed: {e}", exc_info=True)
        await event.edit(Messages.error(f"Download failed: {e}"))
        return

    # Basic syntax check
    try:
        compile(source, file_name, "exec")
    except SyntaxError as e:
        await event.edit(Messages.error(
            f"Syntax error in `{file_name}`:\n"
            f"`{e.msg}` at line {e.lineno}"
        ))
        return

    target_dir = PLUGINS_DIR / category
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{module_name}.py"

    overwrote = target_path.exists()
    try:
        target_path.write_text(source, encoding="utf-8")
    except Exception as e:
        await event.edit(Messages.error(f"Write failed: {e}"))
        return

    registry = event.client.plugin_registry
    existing = registry.resolve_module_key(module_name)
    if existing:
        registry.unload_module(existing)

    count = registry._load_module(
        f"plugins.{category}.{module_name}", category, module_name
    )

    if count == 0:
        await event.edit(Messages.error(
            f"`{module_name}.py` was written but **failed to load**.\n"
            f"Check the log — probably an import error."
        ))
        return

    action = "overwritten" if overwrote else "installed"
    await event.edit(Messages.success(
        f"Module `{module_name}` {action} in **{category}/** — "
        f"{count} handler(s) registered."
    ))


# ══════════════════════════════════════════════════════════════════
#  UNLOAD — unregister handlers, keep file
# ══════════════════════════════════════════════════════════════════

@command(r"modunload (\w+)", "Unload a module (keep file)")
@sudo_only
async def modunload_handler(event):
    """
    Unload a module — unregister its handlers but keep the file.

    Usage:
        .modunload <name>

    Examples:
        .modunload vex
        .modunload track

    Notes:
        - File stays on disk
        - Use restart or .modload to bring it back
        - Useful for pausing a module without deleting it
    """
    name = event.pattern_match.group(1).strip()
    registry = event.client.plugin_registry

    key = registry.resolve_module_key(name)
    if not key:
        await event.edit(Messages.error(f"Module `{name}` isn't loaded."))
        return

    ok = registry.unload_module(key)
    if ok:
        await event.edit(Messages.success(f"Unloaded `{name}` (file kept)."))
    else:
        await event.edit(Messages.error(f"Failed to unload `{name}`."))


# ══════════════════════════════════════════════════════════════════
#  DELETE — backup to Saved Messages, then delete
# ══════════════════════════════════════════════════════════════════

@command(r"moddel (\w+)", "Delete a module file (backup to Saved Messages first)")
@sudo_only
async def moddel_handler(event):
    """
    Delete a module file permanently.

    The .py file is first sent to Saved Messages as a backup,
    then removed from disk. If the backup send fails, nothing
    is deleted.

    Usage:
        .moddel <name>

    Examples:
        .moddel spam

    Notes:
        - Backup goes to Saved Messages with the file name
        - Only deletes after a successful backup
        - Unregisters handlers
        - Sudo only
    """
    name = event.pattern_match.group(1).strip()
    registry = event.client.plugin_registry
    key = registry.resolve_module_key(name)
    path = registry.get_module_disk_path(key) if key else None

    if not path or not path.exists():
        await event.edit(Messages.error(f"Module `{name}` not found on disk."))
        return

    await event.edit(Messages.loading(f"Backing up `{name}`..."))

    # ── 1. Backup to Saved Messages ──
    try:
        file_bytes = path.read_bytes()
        buf = io.BytesIO(file_bytes)
        buf.name = path.name

        info = registry.modules.get(key)
        category = info.category if info else path.parent.name

        backup_caption = (
            f"🗂 **Backup: `{name}`**\n"
            f"Category: `{category}`\n"
            f"Size: {Formatters.format_size(len(file_bytes))}\n"
            f"Use `.modload {category}` replying to this file to restore."
        )

        await event.client.send_file(
            "me", buf,
            caption=backup_caption,
            force_document=True,
        )
    except Exception as e:
        logger.error(f"backup failed: {e}", exc_info=True)
        await event.edit(Messages.error(
            f"Backup to Saved Messages failed — file NOT deleted.\n`{e}`"
        ))
        return

    # ── 2. Delete only after successful backup ──
    ok = registry.delete_module(key)
    if ok:
        await event.edit(Messages.success(
            f"Backed up and deleted `{name}`.\n"
            f"_Recover with `.modload` replying to the backup in Saved Messages._"
        ))
    else:
        await event.edit(Messages.warning(
            f"Backup saved but **deletion failed** — check the log."
        ))


# ══════════════════════════════════════════════════════════════════
#  RELOAD
# ══════════════════════════════════════════════════════════════════

@command(r"modreload (\w+)", "Hot-reload a module from disk")
@sudo_only
async def modreload_handler(event):
    """
    Reload a module from disk without restarting the bot.

    Usage:
        .modreload <name>

    Examples:
        .modreload vex
        .modreload save
        .modreload track

    Notes:
        - Reimports the file and re-registers handlers
        - Useful after editing the source
        - Sudo only
    """
    name = event.pattern_match.group(1).strip()
    registry = event.client.plugin_registry

    key = registry.resolve_module_key(name)
    if not key:
        await event.edit(Messages.error(f"Module `{name}` isn't loaded."))
        return

    await event.edit(Messages.loading(f"Reloading `{name}`..."))

    ok = registry.reload_module(key)
    if ok:
        info = registry.modules.get(key)
        count = len(info.handlers) if info else 0
        await event.edit(Messages.success(
            f"Reloaded `{name}` — {count} handler(s)."
        ))
    else:
        await event.edit(Messages.error(f"Failed to reload `{name}`."))


@command("modreloadall", "Hot-reload every loaded module")
@sudo_only
async def modreloadall_handler(event):
    """
    Reload every currently loaded module.

    Usage:
        .modreloadall

    Notes:
        - Useful after pulling multiple file changes
        - If any module fails to reload it will show in the log
        - Sudo only
    """
    await event.edit(Messages.loading("Reloading all modules..."))
    registry = event.client.plugin_registry
    modules, handlers = registry.reload_all()
    await event.edit(Messages.success(
        f"Reloaded **{modules}** modules · **{handlers}** handlers."
    ))


# ══════════════════════════════════════════════════════════════════
#  LIST
# ══════════════════════════════════════════════════════════════════

@command("modlist", "List modules with disk status")
@sudo_only
async def modlist_handler(event):
    """Usage: `.modlist`"""
    registry = event.client.plugin_registry
    if not registry.modules:
        await event.edit(Messages.info("No modules loaded.")); return

    by_cat = {}
    for name, info in registry.modules.items():
        by_cat.setdefault(info.category, []).append((name, info))

    total = len(registry.modules)
    total_h = sum(len(info.handlers) for mods in by_cat.values() for _, info in mods)

    lines = ["📦 **MODULE MANAGER**\n",
             f"_Total: {total} modules · {total_h} handlers_\n",
             "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    for cat in sorted(by_cat):
        mods = sorted(by_cat[cat])
        lines.append(f"\n**{cat.upper()}**  ·  {len(mods)}")
        for name, info in mods:
            path = registry.get_module_disk_path(name)
            exists = "✓" if path and path.exists() else "✗"
            lines.append(f"  {exists}  `{name}`  —  {len(info.handlers)} handler(s)")
    await event.edit("\n".join(lines))


# ══════════════════════════════════════════════════════════════════
#  EXPORT — code only
# ══════════════════════════════════════════════════════════════════

@command("export", "Export the project as a .zip (code only)")
@sudo_only
async def export_handler(event):
    """
    Zip the entire project (excluding secrets, venv, and DB)
    and send it to Saved Messages.

    Usage:
        .export

    Notes:
        - `.env` is excluded — your API keys stay private
        - session files, venv, data/, logs/, __pycache__ excluded
        - Sent to Saved Messages, not the current chat
        - Sudo only
        - For a full backup (with .env + DB), use `.exportfull`
    """
    await event.edit(Messages.loading("Building project zip..."))

    try:
        data = _build_zip(PROJECT_ROOT)
    except Exception as e:
        logger.error(f"zip build failed: {e}", exc_info=True)
        await event.edit(Messages.error(f"Zip failed: {e}"))
        return

    size = len(data)
    buf = io.BytesIO(data)
    buf.name = "zerox_project.zip"

    try:
        await event.client.send_file(
            "me", buf,
            caption=(
                f"📦 **ZeroX Project Export**\n"
                f"Size: {Formatters.format_size(size)}"
            ),
            force_document=True,
        )
    except Exception as e:
        logger.error(f"send_file failed: {e}", exc_info=True)
        await event.edit(Messages.error(f"Send failed: {e}"))
        return

    await event.edit(Messages.success(
        f"Exported to Saved Messages — {Formatters.format_size(size)}."
    ))


# ══════════════════════════════════════════════════════════════════
#  EXPORTFULL — everything including .env and DB
# ══════════════════════════════════════════════════════════════════

@command("exportfull", "Export EVERYTHING including .env and DB")
@sudo_only
async def exportfull_handler(event):
    """
    Full project export — everything, including secrets.

    Sends a complete .zip to your Saved Messages. Unlike
    `.export`, this INCLUDES:

      - .env (API keys, phone number)
      - session files
      - data/zerox.db (all presets, afk, tracks)
      - logs/

    Use with caution. The zip is a full identity-level backup.

    Usage:
        .exportfull

    Notes:
        - Sudo only
        - Only venv/, .git/, __pycache__/ are excluded
        - Sent to Saved Messages — never to the current chat
        - Delete the backup afterwards if you don't want it stored
    """
    await event.edit(Messages.loading("Building FULL project export..."))

    try:
        data = _build_full_zip(PROJECT_ROOT)
    except Exception as e:
        logger.error(f"full zip failed: {e}", exc_info=True)
        await event.edit(Messages.error(f"Zip failed: {e}"))
        return

    size = len(data)
    size_mb = size / (1024 * 1024)
    if size_mb > 45:
        await event.edit(Messages.error(
            f"Zip too large: {size_mb:.1f} MB (Telegram limit ~50 MB)."
        ))
        return

    buf = io.BytesIO(data)
    buf.name = "zerox_FULL_backup.zip"

    try:
        await event.client.send_file(
            "me", buf,
            caption=(
                f"🔐 **ZeroX FULL Backup**\n"
                f"Size: {Formatters.format_size(size)}\n"
                f"_Contains .env, session, and DB. Handle with care._"
            ),
            force_document=True,
        )
    except Exception as e:
        logger.error(f"send_file failed: {e}", exc_info=True)
        await event.edit(Messages.error(f"Send failed: {e}"))
        return

    await event.edit(Messages.success(
        f"Full export sent to Saved Messages — {Formatters.format_size(size)}."
    ))


# ══════════════════════════════════════════════════════════════════
#  HELP
# ══════════════════════════════════════════════════════════════════

@command("modhelp", "Module manager help")
async def modhelp_handler(event):
    """
    Show module manager commands.

    Usage:
        .modhelp
    """
    await event.edit(
        "🧩 **MODULE MANAGER**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "**🔹 `.modload [category]`** — reply to a `.py` to install\n"
        "**🔹 `.modunload <name>`** — unregister (keep file)\n"
        "**🔹 `.modreload <name>`** — hot reload from disk\n"
        "**🔹 `.modreloadall`** — reload everything\n"
        "**🔹 `.moddel <name>`** — backup to Saved, then delete\n"
        "**🔹 `.modlist`** — list modules + disk state\n"
        "**🔹 `.export`** — code-only zip → Saved Messages\n"
        "**🔹 `.exportfull`** — FULL dump (.env + DB) → Saved Messages\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ All commands are sudo-only.\n"
        "`.env` and session files are never included in `.export`."
    )