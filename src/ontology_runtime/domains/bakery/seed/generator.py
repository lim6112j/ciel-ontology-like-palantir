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
    plans: int = 0
    shipments: int = 0
    waste_records: int = 0
    stocks: int = 0
    extra: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, int]:
        return {
            "stores": self.stores,
            "products": self.products,
            "batches": self.batches,
            "plans": self.plans,
            "shipments": self.shipments,
            "wasteRecords": self.waste_records,
            "stocks": self.stocks,
        }


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
        #: (store_rid, product_rid, quantity) rows already stocked by shipments.
        self._stock_rows: list[tuple[str, str, int]] = []

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
        batches = await self._batches(products, stores)
        await self._plans(products)
        await self._shipments(batches, stores)
        await self._stocks(products, stores)
        await self._waste(batches)
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

    async def _batches(self, products: list[Any], stores: list[Any]) -> list[Any]:
        links = self._links()
        created = []
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
            created.append(batch)
        self.summary.batches = len(created)
        return created

    async def _plans(self, products: list[Any]) -> None:
        """One completed plan (with its own batch), one planned, one in progress."""
        links = self._links()
        yesterday = self.today - dt.timedelta(days=1)
        product = products[0]

        batch = await self.store.create(
            "Batch",
            {
                "batchNo": "B-00006",
                "productRid": product.rid,
                "producedOn": yesterday.isoformat(),
                "expiresOn": (
                    yesterday + dt.timedelta(days=int(product.properties["shelfLifeDays"]))
                ).isoformat(),
                "quantity": 24,
                "status": "baked",
            },
        )
        plan = await self.store.create(
            "ProductionPlan",
            {
                "planNo": "PLAN-00001",
                "planDate": yesterday.isoformat(),
                "productRid": product.rid,
                "plannedQty": 24,
                "producedQty": 24,
                "status": "completed",
            },
        )
        await links.create("planProduct", plan.rid, product.rid)
        await links.create("planBatches", plan.rid, batch.rid)
        await links.create("productBatches", product.rid, batch.rid)
        self.summary.batches += 1

        for index, (offset, status) in enumerate([(1, "planned"), (2, "in_progress")], start=2):
            await self.store.create(
                "ProductionPlan",
                {
                    "planNo": f"PLAN-{index:05d}",
                    "planDate": self.today.isoformat(),
                    "productRid": products[offset].rid,
                    "plannedQty": 18 if status == "planned" else 12,
                    "producedQty": 0,
                    "status": status,
                },
            )
        self.summary.plans = 3

    async def _shipments(self, batches: list[Any], stores: list[Any]) -> None:
        """Ship the first baked batch fully (delivered), the second partially (in transit)."""
        links = self._links()
        baked = [batch for batch in batches if batch.properties["status"] == "baked"][:2]
        created = 0
        for index, batch in enumerate(baked):
            quantity = int(batch.properties["quantity"]) if index == 0 else 10
            status = "delivered" if index == 0 else "in_transit"
            store = stores[index]
            shipment = await self.store.create(
                "Shipment",
                {
                    "shipmentNo": f"SHP-{index + 1:05d}",
                    "shipDate": self.today.isoformat(),
                    "batchRid": batch.rid,
                    "storeRid": store.rid,
                    "quantity": quantity,
                    "status": status,
                    "deliveredOn": self.today.isoformat() if status == "delivered" else None,
                },
            )
            await links.create("batchShipments", batch.rid, shipment.rid)
            await links.create("storeShipments", store.rid, shipment.rid)
            if index == 0:
                await self.store.update(batch.rid, {"status": "shipped"})
            created += 1
            self._stock_rows.append((store.rid, batch.properties["productRid"], quantity))
        self.summary.shipments = created

    async def _stocks(self, products: list[Any], stores: list[Any]) -> None:
        """Fill stock rows for store×product pairs not already stocked by shipments."""
        links = self._links()
        shipped = {(store_rid, product_rid) for store_rid, product_rid, _ in self._stock_rows}
        created = 0
        for store in stores:
            for product in products[:3]:
                if (store.rid, product.rid) in shipped:
                    continue
                quantity = self.random.randint(5, 30)
                stock = await self.store.create(
                    "StoreStock",
                    {
                        "stockNo": f"STK-{created + 1:05d}",
                        "storeRid": store.rid,
                        "productRid": product.rid,
                        "quantity": quantity,
                        "updatedOn": self.today.isoformat(),
                    },
                )
                await links.create("storeStocks", store.rid, stock.rid)
                await links.create("productStocks", product.rid, stock.rid)
                created += 1
        self.summary.stocks = created

    async def _waste(self, batches: list[Any]) -> None:
        """Waste the last planned batch (소보로빵, planned) for expiry."""
        links = self._links()
        target = next(batch for batch in batches if batch.properties["status"] == "planned")
        record = await self.store.create(
            "WasteRecord",
            {
                "wasteNo": "WST-00001",
                "wastedOn": self.today.isoformat(),
                "batchRid": target.rid,
                "quantity": int(target.properties["quantity"]),
                "reason": "expiry",
            },
        )
        await links.create("batchWaste", target.rid, record.rid)
        await self.store.update(target.rid, {"status": "wasted"})
        self.summary.waste_records = 1

    def _links(self) -> Any:
        from ontology_runtime.store.link_store import LinkStore

        return LinkStore(self.registry, self.session)
