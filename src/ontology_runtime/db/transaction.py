"""Small async SQLAlchemy helpers: savepoints and advisory locking."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def savepoint(session: AsyncSession) -> AsyncIterator[None]:
    """Run a block inside a SAVEPOINT so a dry run can be rolled back.

    On exception the savepoint is rolled back and the error re-raised, leaving
    the outer transaction usable.
    """
    async with session.begin_nested():
        yield
