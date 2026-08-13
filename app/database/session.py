"""Async SQLAlchemy engine and session factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    poolclass=NullPool if settings.APP_ENV == "test" else None,
    # Fails fast on a misconfigured/unreachable host instead of hanging and
    # tying up a worker until the OS-level TCP timeout kicks in.
    # `statement_cache_size=0` disables asyncpg prepared-statement caching, which
    # is required when connecting through a transaction-mode PgBouncer pooler
    # (e.g. Neon's `-pooler` endpoint). Without this, INSERT-heavy endpoints like
    # /register raise `asyncpg.exceptions.DuplicatePreparedStatementError`.
    connect_args={
        "timeout": 5,
        "statement_cache_size": 0,
        **({"ssl": True} if settings.POSTGRES_SSL_MODE != "disable" else {}),
    },
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def db_session_ctx() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for use outside of FastAPI request scope (Celery tasks, scripts)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
