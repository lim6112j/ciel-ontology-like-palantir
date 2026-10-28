"""Async database engine and session helpers, one engine per domain."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ontology_runtime.config import settings

_engines: dict[str, AsyncEngine] = {}
_session_factories: dict[str, async_sessionmaker[AsyncSession]] = {}


def _domain(domain: str | None) -> str:
    return domain or settings.domain


def get_engine(domain: str | None = None) -> AsyncEngine:
    name = _domain(domain)
    engine = _engines.get(name)
    if engine is None:
        # Per-domain override (`DATABASE_URL_<DOMAIN>`) keeps two domain
        # instances from sharing one database by accident.
        engine = create_async_engine(settings.database_url_for(name), pool_pre_ping=True)
        _engines[name] = engine
    return engine


def get_session_factory(domain: str | None = None) -> async_sessionmaker[AsyncSession]:
    name = _domain(domain)
    factory = _session_factories.get(name)
    if factory is None:
        factory = async_sessionmaker(get_engine(name), expire_on_commit=False)
        _session_factories[name] = factory
    return factory


@asynccontextmanager
async def session_scope(domain: str | None = None) -> AsyncIterator[AsyncSession]:
    """Yield a session, committing on success and rolling back on error."""
    async with get_session_factory(domain)() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine(domain: str | None = None) -> None:
    if domain is None:
        for active in _engines.values():
            await active.dispose()
        _engines.clear()
        _session_factories.clear()
        return
    name = _domain(domain)
    retired: AsyncEngine | None = _engines.pop(name, None)
    _session_factories.pop(name, None)
    if retired is not None:
        await retired.dispose()
