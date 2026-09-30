"""Database management"""
import aiosqlite
from Config.settings import Config
from core.logger import setup_logger

logger = setup_logger(__name__)

class Database:
    def __init__(self):
        self.db_path = Config.DATA_DIR / "userbot.db"
        self.connection = None

    async def connect(self):
        Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.connection = await aiosqlite.connect(self.db_path)
        await self.connection.execute(
            "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        await self.connection.execute(
            "CREATE TABLE IF NOT EXISTS user_data (user_id INTEGER PRIMARY KEY, data TEXT)")
        await self.connection.commit()
        logger.info("✅ Database connected")

    async def get(self, key, default=None):
        async with self.connection.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

    async def set(self, key, value):
        await self.connection.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        await self.connection.commit()

    async def close(self):
        if self.connection:
            await self.connection.close()
            logger.info("✅ Database closed")
