"""Deterministic synthetic seed for the makgeolli domain."""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.store.object_store import ObjectStore

#: Lifecycle offsets (in days) for seeded batches, keyed by product index.
READY_BOTTLED_AGO = {0: 2, 1: 1}
AGING_ELAPSED = {2: 1, 6: 2}
FERMENTING_STARTED_AGO = {3: 1, 7: 2}
SHIPPED_FINISHED_AGO = {4: 3, 5: 5}
WASTED_INDEX = 8
DEVIATION_READING_OFFSETS = {1, 2}
#: Shipment statuses for the four seeded shipments, in order.
SHIPMENT_STATUSES = ["in_transit", "in_transit", "delivered", "cancelled"]
IN_TRANSIT_STATUSES = {"in_transit"}

#: (name, category, 도수, 유통기한, 발효일, 숙성일, 발효온도min/max, 숙성온도min/max, 용량, 단가)
PRODUCTS: list[tuple[str, str, float, int, int, int, float, float, float, float, int, int]] = [
    ("옥산 생막걸리", "생막걸리", 6.0, 7, 5, 3, 10.0, 15.0, 2.0, 5.0, 900, 3500),
    ("밤향 저도수", "생막걸리", 4.0, 7, 4, 2, 12.0, 16.0, 2.0, 5.0, 900, 3000),
    ("하늘아리 탁주", "탁주", 7.0, 10, 7, 5, 12.0, 17.0, 2.0, 6.0, 900, 4200),
    ("월정 스파클링", "스파클링", 5.0, 10, 9, 4, 10.0, 14.0, 0.0, 4.0, 750, 6000),
    ("금강 산미막걸리", "생막걸리", 5.5, 12, 6, 7, 11.0, 16.0, 2.0, 6.0, 900, 4500),
    ("오색 쌀막걸리", "탁주", 8.0, 14, 8, 6, 13.0, 18.0, 2.0, 6.0, 750, 5000),
    ("반석 동동주", "탁주", 6.0, 14, 10, 10, 13.0, 18.0, 2.0, 8.0, 750, 6500),
    ("설한 청주", "청주", 13.0, 21, 12, 21, 15.0, 20.0, 5.0, 12.0, 500, 9500),
    ("두루 유자주", "과실주", 8.0, 30, 10, 20, 14.0, 19.0, 5.0, 12.0, 500, 8000),
    ("솔바람 청명주", "청주", 15.0, 30, 14, 30, 15.0, 20.0, 5.0, 15.0, 500, 12000),
]

CUSTOMERS = [
    ("골목 한잔주점", "유흥주점", "서울"),
    ("한빛마트 대구점", "대형마트", "대구"),
    ("CU 한남점", "편의점", "서울"),
    ("막걸리닷컴", "온라인", None),
    ("양조장 직영점", "직영점", "서울"),
]

TANKS = [
    # (name, kind, capacityL, tempControl, tempMinC, tempMaxC, status)
    ("발효조 1", "발효조", 1000.0, True, -2.0, 10.0, "in_use"),
    ("발효조 2", "발효조", 1000.0, True, 5.0, 25.0, "idle"),
    ("숙성조 1", "숙성조", 1000.0, True, 0.0, 20.0, "aging_use"),
    ("발효조 3", "발효조", 500.0, False, 10.0, 25.0, "idle"),
]

MATERIALS = [
    # (name, unit, unitCost, currentStock, reorderPoint, supplier)
    ("백미", "kg", 3200, 180.0, 300.0, "미곡상회"),
    ("누룩", "kg", 8500, 12.0, 50.0, "전통누룩사"),
    ("정제수", "L", 900, 2400.0, 500.0, "청정수源"),
    ("유자", "kg", 12000, 45.0, 20.0, "고향농원"),
    ("산미균", "g", 15000, 800.0, 200.0, "바이오텍"),
    ("설탕", "kg", 1900, 120.0, 60.0, "설탕공사"),
]


@dataclass
class SeedSummary:
    products: int = 0
    customers: int = 0
    tanks: int = 0
    materials: int = 0
    batches: int = 0
    orders: int = 0
    order_lines: int = 0
    shipments: int = 0
    waste_records: int = 0
    warehouse_stocks: int = 0
    outlet_stocks: int = 0
    temp_readings: int = 0
    extra: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, int]:
        return {
            "products": self.products,
            "customers": self.customers,
            "tanks": self.tanks,
            "materials": self.materials,
            "batches": self.batches,
            "orders": self.orders,
            "orderLines": self.order_lines,
            "shipments": self.shipments,
            "wasteRecords": self.waste_records,
            "warehouseStocks": self.warehouse_stocks,
            "outletStocks": self.outlet_stocks,
            "tempReadings": self.temp_readings,
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

    async def reset(self) -> None:
        await self.session.execute(
            text(
                "TRUNCATE objects, links, action_runs, action_edits, agent_runs "
                "RESTART IDENTITY CASCADE"
            )
        )

    async def run(self) -> SeedSummary:
        products = await self._products()
        customers = await self._customers()
        tanks = await self._tanks()
        await self._materials()
        batches = await self._batches(products, tanks)
        await self._temp_readings(batches)
        orders, line_count = await self._orders(products, customers)
        await self._shipments(batches, customers, orders)
        await self._waste(batches)
        self.summary.orders = len(orders)
        self.summary.order_lines = line_count
        return self.summary

    async def _products(self) -> list[Any]:
        created = []
        for index, row in enumerate(PRODUCTS, start=1):
            (
                name,
                category,
                alcohol,
                shelf_life,
                fermentation_days,
                aging_days,
                f_min,
                f_max,
                a_min,
                a_max,
                volume_ml,
                price,
            ) = row
            product = await self.store.create(
                "Product",
                {
                    "sku": f"M{index:04d}",
                    "name": name,
                    "category": category,
                    "alcoholPercent": alcohol,
                    "shelfLifeDays": shelf_life,
                    "fermentationDays": fermentation_days,
                    "agingDays": aging_days,
                    "fermentationTempMinC": f_min,
                    "fermentationTempMaxC": f_max,
                    "agingTempMinC": a_min,
                    "agingTempMaxC": a_max,
                    "volumeMl": volume_ml,
                    "unitPrice": price,
                    "active": True,
                },
            )
            created.append(product)
        self.summary.products = len(created)
        return created

    async def _customers(self) -> list[Any]:
        created = []
        for index, (name, kind, region) in enumerate(CUSTOMERS, start=1):
            properties: dict[str, Any] = {
                "customerNo": f"C{index:03d}",
                "name": name,
                "type": kind,
                "status": "active",
                "openedOn": (self.today - dt.timedelta(days=180 * index)).isoformat(),
            }
            if region:
                properties["region"] = region
            created.append(await self.store.create("Customer", properties))
        self.summary.customers = len(created)
        return created

    async def _tanks(self) -> list[Any]:
        created = []
        for index, (name, kind, capacity, temp_control, t_min, t_max, status) in enumerate(
            TANKS, start=1
        ):
            # "aging_use" is not a status enum value; map it to in_use for the aging tank.
            mapped_status = "in_use" if status == "aging_use" else status
            created.append(
                await self.store.create(
                    "Tank",
                    {
                        "tankNo": f"T{index:02d}",
                        "name": name,
                        "capacityL": capacity,
                        "kind": kind,
                        "tempControl": temp_control,
                        "tempMinC": t_min,
                        "tempMaxC": t_max,
                        "status": mapped_status,
                    },
                )
            )
        self.summary.tanks = len(created)
        return created

    async def _materials(self) -> list[Any]:
        created = []
        for index, (name, unit, unit_cost, stock, reorder_point, supplier) in enumerate(
            MATERIALS, start=1
        ):
            created.append(
                await self.store.create(
                    "RawMaterial",
                    {
                        "materialNo": f"RM{index:03d}",
                        "name": name,
                        "unit": unit,
                        "unitCost": unit_cost,
                        "currentStock": stock,
                        "reorderPoint": reorder_point,
                        "supplier": supplier,
                    },
                )
            )
        self.summary.materials = len(created)
        return created

    def _batch_lifecycle(self, index: int, product_props: dict[str, Any]) -> dict[str, Any]:
        """Dates/status per product index: ready, aging, fermenting, shipped, wasted…"""
        fermentation_days = int(product_props["fermentationDays"])
        aging_days = int(product_props["agingDays"])
        fermented_on: dt.date | None = None
        bottled_on: dt.date | None = None

        # Lifecycle stage by product index: two ready, two aging, one fermenting,
        # one shipped, one wasted, the rest aging/fermenting filler.
        if index in {0, 1}:
            bottled_on = self.today - dt.timedelta(days=READY_BOTTLED_AGO[index])
            brew_date = bottled_on - dt.timedelta(days=fermentation_days + aging_days)
            fermented_on = brew_date + dt.timedelta(days=fermentation_days)
            status = "ready"
        elif index in {2, 6}:
            fermented_on = self.today - dt.timedelta(days=AGING_ELAPSED[index])
            brew_date = fermented_on - dt.timedelta(days=fermentation_days)
            status = "aging"
        elif index in {3, 7}:
            brew_date = self.today - dt.timedelta(days=FERMENTING_STARTED_AGO[index])
            status = "fermenting"
        elif index in {4, 5}:
            brewed = self.today - dt.timedelta(
                days=fermentation_days + aging_days + SHIPPED_FINISHED_AGO[index]
            )
            fermented_on = brewed + dt.timedelta(days=fermentation_days)
            bottled_on = fermented_on + dt.timedelta(days=aging_days)
            brew_date = brewed
            status = "shipped"
        else:
            brewed = self.today - dt.timedelta(days=fermentation_days + aging_days + 1 + index)
            fermented_on = brewed + dt.timedelta(days=fermentation_days)
            bottled_on = fermented_on + dt.timedelta(days=aging_days)
            brew_date = brewed
            status = "wasted" if index == WASTED_INDEX else "aging"

        fermentation_due = brew_date + dt.timedelta(days=fermentation_days)
        aging_due = fermentation_due + dt.timedelta(days=aging_days)
        return {
            "brewDate": brew_date,
            "fermentationDueOn": fermentation_due,
            "agingDueOn": aging_due,
            "fermentedOn": fermented_on,
            "bottledOn": bottled_on,
            "status": status,
        }

    async def _batches(self, products: list[Any], tanks: list[Any]) -> list[dict[str, Any]]:
        """Batches across the whole lifecycle, derived dates from product properties."""
        links = self._links()
        created: list[dict[str, Any]] = []
        for index, product in enumerate(products):
            product_props = product.properties
            lifecycle = self._batch_lifecycle(index, product_props)
            status = lifecycle["status"]
            brew_date: dt.date = lifecycle["brewDate"]
            fermented_on: dt.date | None = lifecycle["fermentedOn"]
            bottled_on: dt.date | None = lifecycle["bottledOn"]

            fermentation_temp = float(product_props["fermentationTempMinC"]) + 1.0
            aging_temp = float(product_props["agingTempMinC"]) + 1.0

            volume_l = 300.0 + self.random.choice([0.0, 100.0, 200.0])
            batch = await self.store.create(
                "Batch",
                {
                    "batchNo": f"B-{index + 1:05d}",
                    "productRid": product.rid,
                    "brewDate": brew_date.isoformat(),
                    "fermentationDueOn": lifecycle["fermentationDueOn"].isoformat(),
                    "agingDueOn": lifecycle["agingDueOn"].isoformat(),
                    "fermentationTempC": fermentation_temp,
                    "agingTempC": aging_temp,
                    "volumeL": volume_l,
                    "status": status,
                },
            )
            update: dict[str, Any] = {}
            if fermented_on:
                update["fermentedOn"] = fermented_on.isoformat()
            if bottled_on:
                bottled_qty = int(volume_l * 1000 / int(product_props["volumeMl"]))
                update["bottledOn"] = bottled_on.isoformat()
                update["bottledQty"] = bottled_qty
                update["expiresOn"] = (
                    bottled_on + dt.timedelta(days=int(product_props["shelfLifeDays"]))
                ).isoformat()
            if update:
                await self.store.update(batch.rid, update)
                batch = await self.store.get(batch.rid)

            await links.create("productBatches", product.rid, batch.rid)

            tank = tanks[index % len(tanks)]
            if status in {"fermenting", "aging"}:
                await links.create("tankBatches", tank.rid, batch.rid)
                await self.store.update(batch.rid, {"tankRid": tank.rid})

            created.append(
                {
                    "obj": batch,
                    "status": status,
                    "bottledQty": int(update.get("bottledQty") or 0),
                    "expiresOn": update.get("expiresOn"),
                    "productRid": product.rid,
                    "product": product,
                }
            )
        self.summary.batches = len(created)
        return created

    async def _temp_readings(self, batches: list[dict[str, Any]]) -> None:
        """Normal readings for most active batches plus a few deliberate deviations."""
        links = self._links()
        reading_index = 0
        for offset, entry in enumerate(batches):
            status = entry["status"]
            if status not in {"fermenting", "aging"}:
                continue
            obj = entry["obj"]
            if status == "fermenting":
                stage = "fermentation"
                target = float(obj.properties["fermentationTempC"])
            else:
                stage = "aging"
                target = float(obj.properties["agingTempC"])
            # Most readings in range; indices 1 and 2 deviate on purpose so the
            # tempDeviations demo has data.
            deviate = offset in DEVIATION_READING_OFFSETS
            temp = round(target + (4.5 if deviate else 0.4), 1)
            recorded_at = dt.datetime.combine(
                self.today - dt.timedelta(days=1),
                dt.time(9, (offset % 60) // 2, (offset % 2) * 30),
            ).isoformat()
            reading = await self.store.create(
                "TempReading",
                {
                    "readingNo": f"TR-{reading_index + 1:05d}",
                    "batchRid": obj.rid,
                    "recordedAt": recorded_at,
                    "tempC": temp,
                    "stage": stage,
                    "inRange": not deviate,
                },
            )
            await links.create("batchTempReadings", obj.rid, reading.rid)
            reading_index += 1
        self.summary.temp_readings = reading_index

    async def _orders(self, products: list[Any], customers: list[Any]) -> tuple[list[Any], int]:
        links = self._links()
        statuses = [
            "draft",
            "draft",
            "confirmed",
            "confirmed",
            "shipped",
            "shipped",
            "delivered",
            "cancelled",
        ]
        created = []
        line_count = 0
        for index, status in enumerate(statuses):
            customer = customers[index % len(customers)]
            order_date = self.today - dt.timedelta(days=index % 5)
            order = await self.store.create(
                "SalesOrder",
                {
                    "orderNo": f"SO-{index + 1:05d}",
                    "customerRid": customer.rid,
                    "orderDate": order_date.isoformat(),
                    "status": status,
                    "totalAmount": 0,
                },
            )
            await links.create("customerOrders", customer.rid, order.rid)
            total = 0
            line_products = self.random.sample(products, k=min(3, len(products)))
            for line_index, product in enumerate(line_products, start=1):
                cases = 6 + line_index * 4
                unit_price = int(product.properties["unitPrice"])
                line_amount = unit_price * cases
                line = await self.store.create(
                    "SalesOrderLine",
                    {
                        "lineNo": f"SOL-{line_count + 1:05d}",
                        "orderRid": order.rid,
                        "productRid": product.rid,
                        "cases": cases,
                        "unitPrice": unit_price,
                        "lineAmount": line_amount,
                        "productName": product.properties["name"],
                    },
                )
                await links.create("orderLines", order.rid, line.rid)
                await links.create("lineProduct", product.rid, line.rid)
                total += line_amount
                line_count += 1
            await self.store.update(order.rid, {"totalAmount": total})
            created.append(order)
        return created, line_count

    async def _shipments(
        self, batches: list[dict[str, Any]], customers: list[Any], orders: list[Any]
    ) -> None:
        """Two in-transit, one delivered (with outlet stock), one cancelled."""
        links = self._links()
        ready_like = [entry for entry in batches if entry["status"] == "shipped"]
        targets = ready_like[:2] + [entry for entry in batches if entry["status"] == "ready"][:2]
        created = 0
        for index, entry in enumerate(targets[:4]):
            status = SHIPMENT_STATUSES[index]
            batch = entry["obj"]
            customer = customers[index % len(customers)]
            quantity = max(1, entry["bottledQty"] // 2)
            shipment = await self.store.create(
                "Shipment",
                {
                    "shipmentNo": f"SHP-{created + 1:05d}",
                    "shipDate": (self.today - dt.timedelta(days=1)).isoformat(),
                    "batchRid": batch.rid,
                    "customerRid": customer.rid,
                    "quantity": quantity,
                    "status": status,
                    "deliveredOn": self.today.isoformat() if status == "delivered" else None,
                },
            )
            await links.create("batchShipments", batch.rid, shipment.rid)
            await links.create("customerShipments", customer.rid, shipment.rid)
            if index < len(IN_TRANSIT_STATUSES) and index < len(orders):
                order = orders[index]
                await links.create("orderShipments", order.rid, shipment.rid)
            if status == "delivered":
                await self._bump_outlet_stock(
                    customer.rid, entry["productRid"], quantity, self.today
                )
            created += 1
        self.summary.shipments = created

        # Warehouse stock: bottled batches minus shipped quantities.
        warehouse_index = 0
        for entry in batches:
            bottled_qty = entry["bottledQty"]
            if not bottled_qty or entry["status"] in {"shipped", "wasted"}:
                continue
            batch = entry["obj"]
            remaining = bottled_qty
            if entry["status"] == "ready":
                # Half of each ready batch's bottles left in the warehouse.
                remaining = max(0, bottled_qty - bottled_qty // 2)
            stock = await self.store.create(
                "WarehouseStock",
                {
                    "stockNo": f"WSTK-{warehouse_index + 1:05d}",
                    "batchRid": batch.rid,
                    "productRid": entry["productRid"],
                    "quantity": remaining,
                    "updatedOn": self.today.isoformat(),
                },
            )
            await links.create("batchWarehouseStock", batch.rid, stock.rid)
            await links.create("productWarehouseStock", entry["productRid"], stock.rid)
            warehouse_index += 1
        self.summary.warehouse_stocks = warehouse_index

    async def _bump_outlet_stock(
        self, customer_rid: str, product_rid: str, quantity: int, on_date: dt.date
    ) -> None:
        links = self._links()
        stock = await self.store.create(
            "OutletStock",
            {
                "stockNo": f"OSTK-{self.summary.outlet_stocks + 1:05d}",
                "customerRid": customer_rid,
                "productRid": product_rid,
                "quantity": quantity,
                "updatedOn": on_date.isoformat(),
            },
        )
        await links.create("customerOutletStock", customer_rid, stock.rid)
        await links.create("productOutletStock", product_rid, stock.rid)
        self.summary.outlet_stocks += 1

    async def _waste(self, batches: list[dict[str, Any]]) -> None:
        """Waste the marked wasted batch fully for expiry."""
        links = self._links()
        target = next((entry for entry in batches if entry["status"] == "wasted"), None)
        if target is None:
            return
        batch = target["obj"]
        record = await self.store.create(
            "WasteRecord",
            {
                "wasteNo": "WST-00001",
                "wastedOn": self.today.isoformat(),
                "batchRid": batch.rid,
                "quantity": max(1, int(batch.properties.get("bottledQty") or 0) or 12),
                "reason": "expiry",
            },
        )
        await links.create("batchWaste", batch.rid, record.rid)
        self.summary.waste_records = 1

    def _links(self) -> Any:
        from ontology_runtime.store.link_store import LinkStore

        return LinkStore(self.registry, self.session)
