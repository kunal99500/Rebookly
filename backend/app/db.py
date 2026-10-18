"""Database connection to Supabase Postgres (SQLAlchemy 2.0, async, asyncpg driver).

Every route that needs the database asks for a session:
    async def handler(session: AsyncSession = Depends(get_session)): ...
"""
from collections.abc import AsyncIterator

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# Predictable names for indexes and constraints, so Alembic migrations stay clean.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Every database table class inherits from this."""
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def to_async_url(url: str) -> str:
    """Supabase gives postgresql://...; SQLAlchemy's async driver needs postgresql+asyncpg://..."""
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    raise ValueError("DATABASE_URL must start with postgresql://")


def init_db(database_url: str, *, echo: bool = False) -> AsyncEngine:
    """Create the connection pool. Called once when the server starts."""
    global _engine, _sessionmaker
    if not database_url:
        raise ValueError("DATABASE_URL is not set")
    _engine = create_async_engine(
        to_async_url(database_url),
        pool_size=5,          # connections kept open and reused
        max_overflow=5,       # extra connections allowed during busy moments
        pool_pre_ping=True,   # check a connection still works before using it
        pool_recycle=1800,    # replace connections every 30 minutes
        echo=echo,            # True prints every SQL query (debugging only)
        connect_args={
            "ssl": "require",           # always encrypt traffic to Supabase
            "statement_cache_size": 0,  # safe with Supabase's connection pooler
        },
    )
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def close_db() -> None:
    """Close all connections. Called when the server stops."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


def is_db_ready() -> bool:
    return _sessionmaker is not None


async def get_session() -> AsyncIterator[AsyncSession]:
    """Give one request its own database session, closed automatically afterwards."""
    if _sessionmaker is None:
        raise RuntimeError("Database not initialised. Is DATABASE_URL set?")
    async with _sessionmaker() as session:
        yield session


async def check_db() -> str:
    """Run a tiny query to prove the connection works. Returns the Postgres version."""
    if _engine is None:
        raise RuntimeError("Database not initialised")
    async with _engine.connect() as conn:
        result = await conn.execute(text("select version()"))
        return result.scalar_one()