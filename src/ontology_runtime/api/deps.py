"""Request dependencies: session, runtime, actor, and role enforcement."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.db.engine import get_session_factory
from ontology_runtime.errors import PolicyViolation
from ontology_runtime.runtime import Runtime

#: Header the client uses to declare the acting principal and its role.
ACTOR_HEADER = "X-Actor"
ROLE_HEADER = "X-Role"


@asynccontextmanager
async def session_context() -> AsyncIterator[AsyncSession]:
    """One session per request, committed on success and rolled back on error."""
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def runtime_dependency(request: Request) -> AsyncIterator[Runtime]:
    async with session_context() as session:
        yield Runtime(request.app.state.registry, session)


def actor_of(x_actor: Annotated[str | None, Header()] = None) -> str:
    return x_actor or "anonymous"


def role_of(x_role: Annotated[str | None, Header()] = None) -> str:
    return x_role or "manager"


def require_role(action_roles: list[str], role: str) -> None:
    """Static role check; v1 has no identity provider."""
    if not action_roles:
        return
    if role not in action_roles:
        raise PolicyViolation(
            f"role {role!r} may not run this action",
            allowedRoles=action_roles,
        )


def http_error(exc: Exception) -> HTTPException:
    from ontology_runtime.errors import OntologyError

    if isinstance(exc, OntologyError):
        return HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "details": exc.details},
        )
    return HTTPException(status_code=500, detail={"code": "internal_error", "message": str(exc)})
