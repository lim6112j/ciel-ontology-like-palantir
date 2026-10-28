"""Runtime facade: one object that wires the registry to all services."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.actions.service import ActionRequest, ActionResult, ActionService
from ontology_runtime.config import settings
from ontology_runtime.functions.executor import FunctionExecutor
from ontology_runtime.query.object_set import ObjectSetService, Page
from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.store.index_sync import IndexSync, SyncResult
from ontology_runtime.store.link_store import LinkStore
from ontology_runtime.store.object_store import ObjectStore


@dataclass
class Runtime:
    registry: SchemaRegistry
    session: AsyncSession

    def __post_init__(self) -> None:
        self._load_domain_invariants()
        self.functions = FunctionExecutor(self.registry)
        self.actions = ActionService(self.registry, self.session, function_executor=self.functions)
        self.objects = ObjectStore(self.registry, self.session)
        self.links = LinkStore(self.registry, self.session)
        self.sets = ObjectSetService(self.registry, self.session)

    def _load_domain_invariants(self) -> None:
        """Import the domain's invariant module so `register()` runs, if it ships one.

        Platform invariants live in `validation.invariants`; a domain can add
        its own without the platform knowing about it.
        """
        manifest = self.registry.domain
        if manifest is None or not manifest.pythonPackage:
            return
        try:
            importlib.import_module(f"{manifest.pythonPackage}.invariants")
        except ModuleNotFoundError as exc:
            if not (exc.name or "").startswith(manifest.pythonPackage):
                raise

    @classmethod
    def for_domain(cls, session: AsyncSession, domain: str | None = None) -> Runtime:
        """Build a runtime for a named domain with platform definitions merged in."""
        return cls(SchemaRegistry.from_domain(domain or settings.domain), session)

    async def sync_indexes(self) -> SyncResult:
        return await IndexSync(self.registry, self.session).sync()

    async def apply(self, action: str, params: dict[str, Any], **kwargs: Any) -> ActionResult:
        return await self.actions.apply(ActionRequest(action, params, **kwargs))

    async def validate(self, action: str, params: dict[str, Any], **kwargs: Any) -> ActionResult:
        return await self.actions.validate(ActionRequest(action, params, **kwargs))

    async def run_function(
        self, name: str, params: dict[str, Any], *, actor: str = "function"
    ) -> Any:
        """Run a read function through the function registry."""
        from ontology_runtime.actions.context import EditContext

        context = EditContext(self.registry, self.session, actor=actor, params=params)
        return await self.functions.execute_read(name, context, params)

    async def search(self, object_type: str, **kwargs: Any) -> Page:
        return await self.sets.search(object_type, **kwargs)
