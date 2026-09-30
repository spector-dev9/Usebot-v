"""SQLAlchemy async engine and session factory for ZEROX."""
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from Config.settings import Config
from core.logger import setup_logger

logger = setup_logger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all ZEROX ORM models."""
    pass


# Ensure data directory exists before engine touches the file
_db_path = Path(Config.DATA_DIR) / "zerox.db"
_db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    Config.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def get_session() -> AsyncSession:
    """Yield an async DB session; commit on success, rollback on error."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Dispose the connection pool on shutdown."""
    await engine.dispose()
    logger.info("✅ Database engine disposed")