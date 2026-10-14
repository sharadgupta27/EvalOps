"""Engine and session factory. One engine per process, created from settings."""

import asyncio
import sys
from collections.abc import AsyncIterator, Coroutine
from typing import Any, TypeVar

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import Settings

# TypeVar instead of PEP 695 syntax: keeps the file parseable by Semgrep (SAST coverage).
T = TypeVar("T")


class Base(DeclarativeBase):
    pass


def make_engine(settings: Settings) -> AsyncEngine:
    kwargs: dict[str, object] = {"echo": settings.sql_echo}
    if not settings.is_sqlite:
        kwargs |= {"pool_pre_ping": True, "pool_size": 10, "max_overflow": 10}
    return create_async_engine(settings.database_url, **kwargs)


@event.listens_for(Engine, "connect")
def _sqlite_foreign_keys(dbapi_connection: object, _record: object) -> None:
    # SQLite ignores ON DELETE CASCADE unless foreign keys are switched on per connection.
    module = type(dbapi_connection).__module__
    if "sqlite" in module:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def session_scope(maker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with maker() as session:
        yield session


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """asyncio.run with an event loop psycopg supports (Windows defaults to Proactor)."""
    if sys.platform == "win32":
        return asyncio.run(coro, loop_factory=asyncio.SelectorEventLoop)
    return asyncio.run(coro)
