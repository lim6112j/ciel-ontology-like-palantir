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
from ontology_runtime.config import SCHEMA_DIR
from ontology_runtime.db.engine import dispose_engine
from ontology_runtime.registry import SchemaRegistry


def create_app(schema_dir: Path | None = None) -> FastAPI:
    registry = SchemaRegistry.from_directory(schema_dir or SCHEMA_DIR)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        await dispose_engine()

    app = FastAPI(
        title="주류 도매 온톨로지 런타임",
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

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, Any]:
        return envelope(
            {
                "status": "ok",
                "objectTypes": len(registry.bundle.object_types),
                "actionTypes": len(registry.bundle.action_types),
                "agents": len(registry.bundle.agents),
            }
        )

    app.include_router(ontology.router)
    app.include_router(objects.router)
    app.include_router(actions.router)
    app.include_router(functions.router)
    app.include_router(agents.router)
    return app


app = create_app()
