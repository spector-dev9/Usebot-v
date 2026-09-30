"""Plugin registry and loader."""
import importlib
import inspect
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from telethon import events

from core.logger import setup_logger
from .errors import ErrorHandler
from .module_info import ModuleInfo

logger = setup_logger(__name__)


class PluginRegistry:
    def __init__(self, client):
        self.client = client
        self.modules: Dict[str, ModuleInfo] = {}
        self.error_handler = ErrorHandler()
        self.commands: Dict[str, dict] = {}
        self._handlers_by_module: Dict[str, List[Tuple[Any, Any]]] = {}

    @property
    def plugins_dir(self) -> Path:
        return Path(__file__).parent.parent / "plugins"

    @staticmethod
    def module_key(category: str, module_name: str) -> str:
        return f"{category}.{module_name}"

    def resolve_module_key(self, name: str) -> str | None:
        """Resolve either an exact category.name key or a unique module name."""
        if name in self.modules:
            return name
        matches = [key for key, info in self.modules.items() if info.name == name]
        return matches[0] if len(matches) == 1 else None

    def get_module_disk_path(self, module_key: str) -> Path | None:
        info = self.modules.get(module_key)
        if not info:
            return None
        return self.plugins_dir / info.category / f"{info.name}.py"

    def load_all(self):
        if not self.plugins_dir.exists():
            logger.error(f"❌ Plugins directory not found: {self.plugins_dir}")
            return 0, 0

        total_modules = total_handlers = 0
        for category_dir in sorted(self.plugins_dir.iterdir()):
            if not category_dir.is_dir() or category_dir.name.startswith("_"):
                continue
            for module_file in sorted(category_dir.glob("*.py")):
                if module_file.name.startswith("_"):
                    continue
                count = self._load_module(
                    f"plugins.{category_dir.name}.{module_file.stem}",
                    category_dir.name,
                    module_file.stem,
                )
                if count:
                    total_modules += 1
                    total_handlers += count

        logger.info(
            f"✅ Loaded {total_handlers} handlers from "
            f"{total_modules} modules"
        )
        logger.info(f"📋 Registered {len(self.commands)} commands")
        return total_modules, total_handlers

    def _load_module(self, module_path: str, category: str, module_name: str):
        key = self.module_key(category, module_name)
        try:
            importlib.invalidate_caches()
            module = importlib.import_module(module_path)
            info = ModuleInfo(module_name, module_path, category)
            count = 0

            for name, obj in inspect.getmembers(module):
                if not callable(obj):
                    continue

                if getattr(obj, "_is_handler", False):
                    builder = events.NewMessage(
                        pattern=obj._pattern,
                        outgoing=True,
                    )
                    self._register(key, obj, builder)
                    info.add_handler(name)
                    command_name = obj._command_name.lower()
                    self.commands[command_name] = {
                        "name": obj._command_name,
                        "pattern": obj._raw_pattern,
                        "description": obj._description,
                        "docstring": obj._docstring,
                        "category": obj._category or category,
                        "module": key,
                        "handler": name,
                        "sudo_only": getattr(obj, "_sudo_only", False),
                    }
                    count += 1

                elif getattr(obj, "_is_listener", False):
                    self._register(key, obj, obj._event_builder)
                    info.add_handler(name)
                    count += 1

            hook = getattr(module, "on_startup", None)
            if callable(hook):
                import asyncio
                asyncio.create_task(hook(self.client))

            if count:
                self.modules[key] = info
                logger.info(f"  ✅ {key}: {count} handler(s)")
            return count

        except Exception as e:
            self.error_handler.log_error(e, f"Loading module {module_path}")
            logger.error(
                f"  ❌ Failed to load {module_path}: {e}",
                exc_info=True,
            )
            return 0

    def _register(self, module_key, callback, builder):
        self.client.add_event_handler(callback, builder)
        self._handlers_by_module.setdefault(module_key, []).append(
            (callback, builder)
        )

    def unload_module(self, module_key: str) -> bool:
        if module_key not in self.modules:
            return False

        pairs = self._handlers_by_module.pop(module_key, [])
        for callback, builder in pairs:
            try:
                self.client.remove_event_handler(callback, builder)
            except Exception as e:
                logger.warning(
                    f"remove handler failed for {module_key}: {e}"
                )

        for cmd_name, info in list(self.commands.items()):
            if info["module"] == module_key:
                del self.commands[cmd_name]

        self.modules.pop(module_key, None)

        for key in list(sys.modules):
            if key == f"plugins.{module_key}":
                sys.modules.pop(key, None)

        logger.info(f"🗑 Unloaded module: {module_key}")
        return True

    def reload_module(self, module_key: str) -> bool:
        path = self.get_module_disk_path(module_key)
        if not path or not path.exists():
            logger.error(f"reload: file not found for {module_key}")
            return False

        info = self.modules.get(module_key)
        category = info.category if info else path.parent.name
        name = info.name if info else path.stem

        self.unload_module(module_key)
        importlib.invalidate_caches()
        count = self._load_module(
            f"plugins.{category}.{name}",
            category,
            name,
        )
        return count > 0

    def delete_module(self, module_key: str) -> bool:
        path = self.get_module_disk_path(module_key)
        if not path:
            return False

        self.unload_module(module_key)
        try:
            if path.exists():
                path.unlink()
            if path.parent.exists() and not any(path.parent.iterdir()):
                path.parent.rmdir()
            return True
        except Exception as e:
            logger.error(f"delete file failed: {e}", exc_info=True)
            return False

    def reload_all(self):
        names = list(self.modules)
        total_modules = total_handlers = 0
        for key in names:
            if self.reload_module(key):
                info = self.modules.get(key)
                if info:
                    total_modules += 1
                    total_handlers += len(info.handlers)
        return total_modules, total_handlers

    def get_command_info(self, name):
        return self.commands.get(name.lower())

    def get_commands_by_category(self, category=None):
        out = {}
        for info in self.commands.values():
            cat = info["category"]
            if category and cat.lower() != category.lower():
                continue
            out.setdefault(cat, []).append(info)
        for cat in out:
            out[cat].sort(key=lambda x: x["name"])
        return out

    def get_all_categories(self):
        return sorted({x["category"] for x in self.commands.values()})

    def search_commands(self, query):
        q = query.lower()
        return [
            x for x in self.commands.values()
            if q in x["name"].lower() or q in x["description"].lower()
        ]

    def list_modules(self):
        if not self.modules:
            return "❌ No modules loaded"

        out = "**📦 Loaded Modules:**\n\n"
        for cat in sorted({m.category for m in self.modules.values()}):
            out += f"**{cat.upper()}:**\n"
            for key, m in sorted(
                ((k, m) for k, m in self.modules.items() if m.category == cat),
                key=lambda item: item[1].name,
            ):
                out += (
                    f"  {'✅' if m.enabled else '❌'} "
                    f"`{m.name}` ({len(m.handlers)})\n"
                )
            out += "\n"
        return out

    def get_stats(self):
        return {
            "total_modules": len(self.modules),
            "total_handlers": sum(
                len(m.handlers) for m in self.modules.values()
            ),
            "total_commands": len(self.commands),
            "categories": len(
                {m.category for m in self.modules.values()}
            ),
        }
