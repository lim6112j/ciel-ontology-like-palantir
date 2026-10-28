"""Deterministic synthetic seed for the bakery domain."""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.store.object_store import ObjectStore

PRODUCTS = [
    ("우유식빵", "식빵", 5, 3500),
    ("통밀식빵", "식빵", 4, 4200),
    ("크루아상", "페이스트리", 2, 2800),
    ("소보로빵", "단과자", 3, 2200),
    ("딸기케이크", "케이크", 2, 22000),
]

STORE_NAMES = ["강남점", "판교점", "홍대점", "잠실점"]


@dataclass
class SeedSummary:
    stores: int = 0
    products: int = 0
    batches: int = 0
    extra: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, int]:
        return {"stores": self.stores, "products": self.products, "batches": self.batches}


class SeedGenerator:
    def __init__(
        self,
        registry: SchemaRegistry,
        session: AsyncSession,
        *,
        seed: int = 42,
        today: dt.date | None = None,
    ) -> None:
        self.registry = registry
        self.session = session
        self.store = ObjectStore(registry, session)
        self.random = random.Random(seed)
        self.today = today or dt.date.today()
        self.summary = SeedSummary()

    async def reset(self) -> None:
        await self.session.execute(
            text(
                "TRUNCATE objects, links, action_runs, action_edits, agent_runs "
                "RESTART IDENTITY CASCADE"
            )
        )

    async def run(self) -> SeedSummary:
        products = await self._products()
        stores = await self._stores()
        await self._batches(products, stores)
        return self.summary

    async def _products(self) -> list[Any]:
        created = []
        for sku, (name, category, shelf_life, price) in enumerate(PRODUCTS, start=1):
            created.append(
                await self.store.create(
                    "Product",
                    {
                        "sku": f"B{sku:04d}",
                        "name": name,
                        "category": category,
                        "shelfLifeDays": shelf_life,
                        "unitPrice": price,
                        "active": True,
                    },
                )
            )
        self.summary.products = len(created)
        return created

    async def _stores(self) -> list[Any]:
        created = [
            await self.store.create(
                "Store",
                {
                    "storeNo": f"S{index:03d}",
                    "name": name,
                    "status": "active",
                    "openedOn": (self.today - dt.timedelta(days=90 * index)).isoformat(),
                },
            )
            for index, name in enumerate(STORE_NAMES, start=1)
        ]
        self.summary.stores = len(created)
        return created

    async def _batches(self, products: list[Any], stores: list[Any]) -> None:
        links = self._links()
        count = 0
        for offset, product in enumerate(products):
            produced_on = self.today - dt.timedelta(days=offset % 3)
            expires_on = produced_on + dt.timedelta(days=int(product.properties["shelfLifeDays"]))
            batch = await self.store.create(
                "Batch",
                {
                    "batchNo": f"B-{offset + 1:05d}",
                    "productRid": product.rid,
                    "producedOn": produced_on.isoformat(),
                    "expiresOn": expires_on.isoformat(),
                    "quantity": 20 + offset * 5,
                    "status": "baked" if offset % 2 == 0 else "planned",
                },
            )
            await links.create("productBatches", product.rid, batch.rid)
            await links.create("storeBatches", stores[offset % len(stores)].rid, batch.rid)
            count += 1
        self.summary.batches = count

    def _links(self) -> Any:
        from ontology_runtime.store.link_store import LinkStore

        return LinkStore(self.registry, self.session)
