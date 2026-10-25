"""Error envelope: one shape for every failure."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ontology_runtime.errors import OntologyError


def envelope(
    data: Any = None,
    *,
    error: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {"success": error is None, "data": data, "error": error, "meta": meta or {}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(OntologyError)
    async def handle_ontology_error(_request: Request, exc: OntologyError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope(error=exc.to_dict()),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=envelope(error={"code": "internal_error", "message": str(exc)}),
        )
