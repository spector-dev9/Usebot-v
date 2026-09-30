"""Main configuration facade."""
from .defaults import Defaults
from .environment import Environment


class Config:
    API_ID = Environment.API_ID
    API_HASH = Environment.API_HASH
    PHONE_NUMBER = Environment.PHONE_NUMBER
    SESSION_NAME = Environment.SESSION_NAME
    CMD_PREFIX = Environment.CMD_PREFIX
    LOG_LEVEL = Environment.LOG_LEVEL
    DEBUG_MODE = Environment.DEBUG_MODE
    DATABASE_URL = Environment.DATABASE_URL
    SUDO_USERS = Environment.SUDO_USERS
    CONTROL_BOT_TOKEN = Environment.CONTROL_BOT_TOKEN
    CONTROL_BOT_ADMIN_ID = Environment.CONTROL_BOT_ADMIN_ID

    BASE_DIR = Environment.BASE_DIR
    DATA_DIR = Environment.DATA_DIR
    LOGS_DIR = Environment.LOGS_DIR
    CACHE_DIR = Environment.CACHE_DIR

    VERSION = Defaults.BOT_VERSION
    NAME = Defaults.BOT_NAME
    AUTHOR = Defaults.BOT_AUTHOR
    MAX_MESSAGE_LENGTH = Defaults.MAX_MESSAGE_LENGTH
    CACHE_TTL = Defaults.CACHE_TTL
    SESSION_STRING = Environment.SESSION_STRING

    @classmethod
    def validate(cls):
        errors = []
        if not cls.API_ID:
            errors.append("API_ID is not set or invalid")
        if not cls.API_HASH:
            errors.append("API_HASH is not set")
        if not cls.PHONE_NUMBER:
            errors.append("PHONE_NUMBER is not set")

        if errors:
            msg = "\n".join(f"  ❌ {e}" for e in errors)
            raise ValueError(
                f"\n⚠️ Configuration Errors:\n{msg}\n\n"
                "Please check your .env file!"
            )

        if not cls.DATABASE_URL.startswith("sqlite+aiosqlite://"):
            raise ValueError(
                "DATABASE_URL must use the async SQLite driver: "
                "sqlite+aiosqlite://..."
            )

        Environment.create_directories()
        return True

    @classmethod
    def get_info(cls):
        return {
            "version": cls.VERSION,
            "name": cls.NAME,
            "prefix": cls.CMD_PREFIX,
            "debug": cls.DEBUG_MODE,
            "sudo_users": len(cls.SUDO_USERS),
            "controller_enabled": bool(cls.CONTROL_BOT_TOKEN),
        }
