"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ontology_runtime.api.errors import envelope, install_error_handlers
from ontology_runtime.api.routes import actions, agents, functions, objects, ontology
from ontology_runtime.config import settings
from ontology_runtime.db.engine import dispose_engine
from ontology_runtime.registry import SchemaRegistry


def create_app(
    schema_dir: Path | None = None,
    *,
    domain: str | None = None,
) -> FastAPI:
    """Build the API for one domain.

    Passing `schema_dir` loads a bare directory (tests, ad-hoc schemas). Passing
    `domain` (or nothing) loads that domain with the shared platform definitions.
    """
    if schema_dir is not None:
        registry = SchemaRegistry.from_directory(schema_dir)
    else:
        registry = SchemaRegistry.from_domain(domain or settings.domain)

    manifest = registry.domain
    domain_label = manifest.displayName if manifest else "온톨로지"

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        await dispose_engine()

    app = FastAPI(
        title=f"{domain_label} 온톨로지 런타임",
        version="0.1.0",
        description=(
            "Palantir Foundry 스타일 온톨로지(object/link/action/function)와 "
            "제안-승인 방식 AI 에이전트를 로컬에서 구현한 런타임."
        ),
        lifespan=lifespan,
    )
    app.state.registry = registry

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)

    def _health_payload() -> dict[str, Any]:
        return {
            "status": "ok",
            "domain": registry.domain_name,
            "objectTypes": len(registry.bundle.object_types),
            "actionTypes": len(registry.bundle.action_types),
            "agents": len(registry.bundle.agents),
        }

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, Any]:
        return envelope(_health_payload())

    # Alias so a generated client whose base is `/api/<domain>` can reach health
    # without a path trick; each domain instance answers for itself.
    @app.get("/api/health", tags=["ops"])
    async def api_health() -> dict[str, Any]:
        return envelope(_health_payload())

    app.include_router(ontology.router)
    app.include_router(objects.router)
    app.include_router(actions.router)
    app.include_router(functions.router)
    app.include_router(agents.router)
    return app


app = create_app()
