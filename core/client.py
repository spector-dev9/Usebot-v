"""Telegram client wrapper — StringSession for deployment, file for local."""
from telethon import TelegramClient
from telethon.sessions import StringSession
from Config.settings import Config
from core.logger import setup_logger

logger = setup_logger(__name__)


class UserbotClient:
    def __init__(self):
        session_string = (Config.SESSION_STRING or "").strip()

        if session_string:
            # Railway / deployment mode — no login prompt
            self.client = TelegramClient(
                StringSession(session_string),
                Config.API_ID,
                Config.API_HASH,
                device_model=f"{Config.NAME} v{Config.VERSION}",
                system_version="Linux",
                app_version=Config.VERSION,
            )
            self._use_string = True
            logger.info("🔑 Using StringSession from env")
        else:
            # Local mode — file session + interactive login
            self.client = TelegramClient(
                Config.SESSION_NAME,
                Config.API_ID,
                Config.API_HASH,
                device_model=f"{Config.NAME} v{Config.VERSION}",
                system_version="Linux",
                app_version=Config.VERSION,
            )
            self._use_string = False
            logger.info("📁 Using file session (interactive)")

        self.plugin_registry = None
        self.bot_state = None
        self._me = None

    async def start(self):
        try:
            if self._use_string:
                await self.client.connect()
                if not await self.client.is_user_authorized():
                    raise RuntimeError(
                        "SESSION_STRING is invalid or expired. "
                        "Regenerate with `python login.py`."
                    )
            else:
                await self.client.start(phone=Config.PHONE_NUMBER)

            self._me = await self.client.get_me()
            logger.info(f"✅ Logged in as: {self._me.first_name}")
            if self._me.username:
                logger.info(f"   Username: @{self._me.username}")
            logger.info(f"   User ID: {self._me.id}")
        except Exception as e:
            logger.error(f"❌ Failed to start: {e}")
            raise

    async def stop(self):
        try:
            await self.client.disconnect()
            logger.info("✅ Client disconnected")
        except Exception as e:
            logger.error(f"❌ Error stopping: {e}")

    @property
    def me(self):
        return self._me
