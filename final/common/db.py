import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from typing import TYPE_CHECKING, AsyncGenerator

if TYPE_CHECKING:
    from logging import Logger

DATABASE_URL = os.getenv("DATABASE_URL")
# Pool: 500 max_connections / ~20 pods ≈ 25 per pod. Env để tune khi scale.
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "15"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "5"))

if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Replace sync driver with async driver for psycopg
if DATABASE_URL and DATABASE_URL.startswith("postgresql+psycopg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql+psycopg_async://", 1)

engine = create_async_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=30,
    pool_recycle=600,
)
SessionLocal = async_sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an AsyncSession and closes it after the request."""
    async with SessionLocal() as session:
        yield session


def log_db_pool_status(logger: "Logger | None" = None) -> None:
    """Log DB pool status at startup."""
    if not logger or not DATABASE_URL:
        return
    try:
        from common.logging_utils import log_event
        log_event(logger, "db_pool_ready", pool_size=POOL_SIZE, max_overflow=MAX_OVERFLOW)
    except Exception:
        pass


class Base(DeclarativeBase):
    pass
