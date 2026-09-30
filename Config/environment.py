"""Environment variable loader."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _int_env(name, default=0):
    value = os.getenv(name, str(default)).strip()
    try:
        return int(value)
    except ValueError:
        return default


class Environment:
    API_ID = _int_env("API_ID")
    API_HASH = os.getenv("API_HASH", "").strip()
    PHONE_NUMBER = os.getenv("PHONE_NUMBER", "").strip()
    SESSION_NAME = os.getenv("SESSION_NAME", "userbot_session").strip()
    CMD_PREFIX = os.getenv("CMD_PREFIX", ".")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"
    SESSION_STRING = os.getenv('SESSION_STRING', '')

    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///data/zerox.db",
    ).strip()

    SUDO_USERS = [
        int(x.strip())
        for x in os.getenv("SUDO_USERS", "").split(",")
        if x.strip().lstrip("-").isdigit()
    ]

    CONTROL_BOT_TOKEN = os.getenv("CONTROL_BOT_TOKEN", "").strip()
    CONTROL_BOT_ADMIN_ID = _int_env("CONTROL_BOT_ADMIN_ID")

    BASE_DIR = BASE_DIR
    DATA_DIR = BASE_DIR / "data"
    LOGS_DIR = DATA_DIR / "logs"
    CACHE_DIR = DATA_DIR / "cache"

    @classmethod
    def create_directories(cls):
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
