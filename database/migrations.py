"""Schema creation for ZEROX."""
from core.logger import setup_logger
from .connection import Base, engine
# Import models so they register with Base.metadata before create_all
from . import models  # noqa: F401

logger = setup_logger(__name__)


async def run() -> None:
    """Create all tables if they don't exist. Idempotent."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database migrations applied")