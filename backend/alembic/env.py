"""Alembic migration environment for Rebookly.

Reads DATABASE_URL from backend/.env through our settings, so no password is ever
stored in alembic.ini. Uses the same tables (Base.metadata) as the app.
"""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.config import get_settings
from app.db import Base, to_async_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    url = get_settings().database_url.get_secret_value()
    if not url:
        raise RuntimeError("DATABASE_URL is not set in backend/.env")
    return to_async_url(url)


def run_migrations_offline() -> None:
    """Generate SQL without connecting (alembic upgrade head --sql)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Connect to Supabase and apply migrations."""
    engine = create_async_engine(
        _database_url(),
        poolclass=pool.NullPool,  # one short-lived connection, closed when done
        connect_args={"ssl": "require", "statement_cache_size": 0},
    )
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())