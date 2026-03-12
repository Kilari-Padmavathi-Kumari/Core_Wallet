import logging
from typing import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import DATABASE_URL, DB_POOL_MAX_SIZE
from models import Base

logger = logging.getLogger("wallet.db")


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


engine = create_async_engine(
    _normalize_database_url(DATABASE_URL),
    pool_size=DB_POOL_MAX_SIZE,
    max_overflow=0,
    pool_pre_ping=True,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """
    Create tables and index needed for wallet operations.
    Safe to run multiple times (idempotent).
    """
    logger.info("db_init_started")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("db_init_completed")


async def db_healthcheck() -> bool:
    """Return True if DB can be queried, else False."""
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
        return True
    except Exception:
        logger.exception("db_healthcheck_failed")
        return False


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
