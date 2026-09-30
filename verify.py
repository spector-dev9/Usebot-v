#!/usr/bin/env python3
"""Offline ZeroX project verifier.

This checks project structure and Python syntax without connecting to Telegram.
Run: python verify.py
"""
import ast
import compileall
from pathlib import Path
import sys
import re

ROOT = Path(__file__).resolve().parent
REQUIRED = [
    "main.py",
    "controller.py",
    "requirements.txt",
    ".env.example",
    "Config/settings.py",
    "Config/environment.py",
    "Run/runtime.py",
    "Run/registry.py",
    "database/connection.py",
    "database/models.py",
    "plugins/admin/system.py",
    "plugins/admin/modules.py",
    "plugins/admin/host.py",
    "plugins/utilities/help.py",
    "plugins/utilities/games.py",
    "plugins/utilities/ping.py",
]


def main():
    missing = [p for p in REQUIRED if not (ROOT / p).exists()]
    if missing:
        print("❌ Missing files:")
        print("\n".join(f"  - {p}" for p in missing))
        return 1

    ok = compileall.compile_dir(
        str(ROOT),
        quiet=1,
        maxlevels=20,
        rx=re.compile(r"(^|[\\/])(\.git|venv|env|\.venv|__pycache__)([\\/]|$)"),
    )
    if not ok:
        print("❌ Python compilation failed.")
        return 1

    plugins = list((ROOT / "plugins").rglob("*.py"))
    commands = listeners = 0

    for path in plugins:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call):
                        name = getattr(dec.func, "id", "")
                        if name == "command":
                            commands += 1
                        elif name == "listener":
                            listeners += 1

    print("✅ Structure: OK")
    print("✅ Python syntax: OK")
    print(f"✅ Plugin files: {len(plugins)}")
    print(f"✅ Commands: {commands}")
    print(f"✅ Listeners: {listeners}")
    print("ℹ️ Live Telegram/database connectivity was not tested.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
