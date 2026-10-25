"""Deterministic synthetic seed for a Korean liquor wholesaler.

The same seed value always yields the same dataset, which keeps demo runs,
tests, and screenshots reproducible.
"""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.store.object_store import ObjectStore

#: Seoul-ish bounding boxes per depot region.
DEPOT_AREAS = [
    ("D-SEOUL", "서울창고", "수도권", 37.50, 126.98, 37.62, 127.10),
    ("D-GYEONG", "경기남부창고", "수도권", 37.20, 126.90, 37.35, 127.10),
    ("D-BUSAN", "부산창고", "영남", 35.10, 128.98, 35.24, 129.14),
]

OUTLET_TYPES = ["소매점"] * 5 + ["일반음식점"] * 4 + ["편의점"] * 2 + ["마트", "유흥주점"]
OUTLET_PREFIX = ["행복", "새벽", "하나", "대성", "한빛", "우리", "청솔", "동네", "별빛", "정다운"]
OUTLET_SUFFIX = ["식당", "마트", "주점", "분식", "상회", "집", "가게"]

PRODUCTS = [
    ("참이슬 후레쉬 360ml", "소주", "하이트진로", 360, 30, 1150),
    ("처음처럼 360ml", "소주", "롯데주류", 360, 30, 1120),
    ("한소주 360ml", "소주", "무학", 360, 30, 1100),
    ("카스 500ml", "맥주", "오비맥주", 500, 20, 1450),
    ("하이트 500ml", "맥주", "하이트진로", 500, 20, 1400),
    ("테라 500ml", "맥주", "오비맥주", 500, 20, 1500),
    ("클라우드 500ml", "맥주", "롯데주류", 500, 20, 1480),
    ("장수생막걸리 750ml", "탁주", "국순당", 750, 12, 1300),
    ("국순당 쌀막걸리 750ml", "탁주", "국순당", 750, 12, 1350),
    ("청하 400ml", "청주", "롯데주류", 400, 20, 2100),
    ("백세주 375ml", "청주", "국순당", 375, 20, 3900),
    ("발렌타인 17년 700ml", "양주", "발렌타인", 700, 6, 128000),
    ("조니워커 블루 750ml", "양주", "조니워커", 750, 6, 320000),
    ("산토리 하이볼 340ml", "양주", "산토리", 340, 24, 2600),
    ("몬테스 알파 카베르네 750ml", "와인", "몬테스", 750, 6, 21000),
    ("장미소주 360ml", "소주", "보해양조", 360, 30, 1080),
]

NAMES_FAMILY = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신"]
NAMES_GIVEN = [
    "민수",
    "영희",
    "철수",
    "지훈",
    "수진",
    "현우",
    "미정",
    "동건",
    "서연",
    "재원",
    "하늘",
    "지우",
]

TAX_RATE_NUMERATOR = 10
TAX_RATE_DENOMINATOR = 100
DAYS_OF_HISTORY = 56  # 8 weeks
DELIVERY_WEEKDAYS = [0, 1, 2, 3, 4, 5]
#: Days left unplanned so the demo has real work to do.
UNPLANNED_TRAILING_DAYS = 3
#: Share of stops that fail for a realistic exception population.
FAILURE_RATE = 0.07


@dataclass
class SeedSummary:
    depots: int = 0
    outlets: int = 0
    products: int = 0
    sales_reps: int = 0
    drivers: int = 0
    vehicles: int = 0
    routes: int = 0
    orders: int = 0
    deliveries: int = 0
    stops: int = 0
    invoices: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "depots": self.depots,
            "outlets": self.outlets,
            "products": self.products,
            "salesReps": self.sales_reps,
            "drivers": self.drivers,
            "vehicles": self.vehicles,
            "routes": self.routes,
            "orders": self.orders,
            "deliveries": self.deliveries,
            "stops": self.stops,
            "invoices": self.invoices,
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
        self._order_counter = 0

    async def reset(self) -> None:
        """Remove seeded business objects (keeps the schema and indexes)."""
        await self.session.execute(
            text(
                "TRUNCATE objects, links, action_runs, action_edits, agent_runs "
                "RESTART IDENTITY CASCADE"
            )
        )

    async def run(self) -> SeedSummary:
        depots = await self._depots()
        reps = await self._sales_reps(depots)
        routes = await self._routes(depots, reps)
        outlets = await self._outlets(depots, reps, routes)
        products = await self._products()
        drivers, vehicles = await self._fleet(depots)
        await self._history(outlets, products, reps, depots, drivers, vehicles)
        return self.summary

    # -- master data -------------------------------------------------------
    async def _depots(self) -> list[Any]:
        created = []
        for code, name, region, lat_min, lon_min, lat_max, lon_max in DEPOT_AREAS:
            created.append(
                await self.store.create(
                    "Depot",
                    {
                        "depotNo": code,
                        "name": name,
                        "region": region,
                        "address": f"{name} 소재지",
                        "lat": round(self.random.uniform(lat_min, lat_max), 5),
                        "lon": round(self.random.uniform(lon_min, lon_max), 5),
                        "capacityCases": self.random.choice([3000, 5000, 8000]),
                    },
                )
            )
        self.summary.depots = len(created)
        return created

    async def _sales_reps(self, depots: list[Any]) -> list[Any]:
        created = []
        for index in range(25):
            depot = depots[index % len(depots)]
            name = self._person_name()
            created.append(
                await self.store.create(
                    "SalesRep",
                    {
                        "employeeNo": f"R{index + 1:04d}",
                        "name": name,
                        "phone": self._phone(),
                        "territory": f"{depot.properties['name'][:2]}-{index + 1:02d}구역",
                        "status": "active",
                        "depotRid": depot.rid,
                    },
                )
            )
        self.summary.sales_reps = len(created)
        return created

    async def _routes(self, depots: list[Any], reps: list[Any]) -> list[Any]:
        created = []
        counter = 1
        for depot in depots:
            for weekday in range(6):
                rep = next(r for r in reps if r.properties["depotRid"] == depot.rid)
                created.append(
                    await self.store.create(
                        "DeliveryRoute",
                        {
                            "routeCode": f"RT-{counter:03d}",
                            "name": f"{depot.properties['name'][:2]}-{weekday + 1}구역",
                            "weekday": weekday,
                            "depotRid": depot.rid,
                            "salesRepRid": rep.rid,
                            "active": True,
                        },
                    )
                )
                counter += 1
        self.summary.routes = len(created)
        return created

    async def _outlets(self, depots: list[Any], reps: list[Any], routes: list[Any]) -> list[Any]:
        created = []
        for index in range(120):
            depot = depots[index % len(depots)]
            rep = next(r for r in reps if r.properties["depotRid"] == depot.rid)
            weekday = DELIVERY_WEEKDAYS[index % len(DELIVERY_WEEKDAYS)]
            route = next(
                r
                for r in routes
                if r.properties["depotRid"] == depot.rid and r.properties["weekday"] == weekday
            )
            name = f"{self.random.choice(OUTLET_PREFIX)}{self.random.choice(OUTLET_SUFFIX)}"
            created.append(
                await self.store.create(
                    "Outlet",
                    {
                        "outletNo": f"OUT-{index + 1:05d}",
                        "name": f"{name} {index + 1}호점",
                        "outletType": self.random.choice(OUTLET_TYPES),
                        "bizRegNo": self._biz_reg_no(),
                        "licenseNo": f"제2026-{self.random.randint(1, 9999):04d}호",
                        "licenseType": "일반음식점",
                        "address": (
                            f"{depot.properties['region']} "
                            f"{self.random.randint(1, 99)}로 "
                            f"{self.random.randint(1, 200)}"
                        ),
                        "lat": round(self.random.uniform(35.1, 37.6), 5),
                        "lon": round(self.random.uniform(126.9, 129.1), 5),
                        "deliveryWeekday": weekday,
                        "deliveryWindow": self.random.choice(["오전", "오후", "종일"]),
                        "status": "active" if index % 17 else "suspended",
                        "salesRepRid": rep.rid,
                        "depotRid": depot.rid,
                        "routeRid": route.rid,
                    },
                )
            )
        self.summary.outlets = len(created)
        return created

    async def _products(self) -> list[Any]:
        created = []
        for index, (name, category, maker, volume, units, unit_price) in enumerate(PRODUCTS):
            case_price = unit_price * units
            created.append(
                await self.store.create(
                    "Product",
                    {
                        "sku": f"SKU-{index + 1:04d}",
                        "name": name,
                        "category": category,
                        "manufacturer": maker,
                        "volumeMl": volume,
                        "unitsPerCase": units,
                        "unitPrice": unit_price,
                        "casePrice": case_price,
                        "taxType": "면세" if category == "와인" else "과세",
                        "alcoholPercent": float(self.random.choice([4.5, 5.0, 16.0, 17.0, 40.0])),
                        "active": True,
                    },
                )
            )
        self.summary.products = len(created)
        return created

    async def _fleet(self, depots: list[Any]) -> tuple[list[Any], list[Any]]:
        drivers, vehicles = [], []
        for index in range(30):
            depot = depots[index % len(depots)]
            drivers.append(
                await self.store.create(
                    "Driver",
                    {
                        "employeeNo": f"DR{index + 1:04d}",
                        "name": self._person_name(),
                        "phone": self._phone(),
                        "employmentType": "직영" if index % 3 else "지입",
                        "licenseType": self.random.choice(["1종보통", "1종대형"]),
                        "status": "available" if index % 11 else "on_leave",
                        "depotRid": depot.rid,
                    },
                )
            )
        for index in range(20):
            depot = depots[index % len(depots)]
            vehicle_type, capacity = self.random.choice(
                [("1톤탑차", 120), ("1.4톤탑차", 180), ("2.5톤탑차", 320)]
            )
            vehicles.append(
                await self.store.create(
                    "Vehicle",
                    {
                        "plateNo": (
                            f"{self.random.randint(10, 99)}가{self.random.randint(1000, 9999)}"
                        ),
                        "vehicleType": vehicle_type,
                        "capacityCases": capacity,
                        "capacityWeightKg": capacity * 12,
                        "status": "available" if index % 9 else "maintenance",
                        "depotRid": depot.rid,
                    },
                )
            )
        self.summary.drivers = len(drivers)
        self.summary.vehicles = len(vehicles)
        return drivers, vehicles

    # -- transaction history ----------------------------------------------
    async def _history(
        self,
        outlets: list[Any],
        products: list[Any],
        reps: list[Any],
        depots: list[Any],
        drivers: list[Any],
        vehicles: list[Any],
    ) -> None:
        for day_offset in range(DAYS_OF_HISTORY, 0, -1):
            order_date = self.today - dt.timedelta(days=day_offset)
            delivery_date = order_date + dt.timedelta(days=1)
            weekday = delivery_date.weekday()
            eligible = [o for o in outlets if o.properties.get("deliveryWeekday") == weekday]
            if not eligible:
                continue

            orders_today = []
            for outlet in self.random.sample(
                eligible, k=min(len(eligible), self.random.randint(8, 16))
            ):
                order = await self._order(outlet, products, reps, order_date, delivery_date)
                orders_today.append(order)
                self.summary.orders += 1

            if day_offset <= UNPLANNED_TRAILING_DAYS:
                continue  # recent days stay unplanned so the demo has work to do

            depot = depots[day_offset % len(depots)]
            depot_drivers = [d for d in drivers if d.properties["depotRid"] == depot.rid]
            depot_vehicles = [v for v in vehicles if v.properties["depotRid"] == depot.rid]
            await self._delivery(
                delivery_date, orders_today, products, depot, depot_drivers, depot_vehicles
            )

    async def _order(
        self,
        outlet: Any,
        products: list[Any],
        reps: list[Any],
        order_date: dt.date,
        delivery_date: dt.date,
    ) -> Any:
        line_count = self.random.randint(1, 3)
        chosen = self.random.sample(products, k=line_count)
        lines = []
        subtotal = taxable = total_cases = 0
        for product in chosen:
            cases = self.random.randint(1, 12)
            case_price = int(product.properties["casePrice"])
            amount = case_price * cases
            subtotal += amount
            total_cases += cases
            if product.properties.get("taxType") == "과세":
                taxable += amount
            lines.append((product, cases, case_price, amount))

        self._order_counter += 1
        order_no = f"SO-{order_date.strftime('%Y%m%d')}-{self._order_counter:05d}"

        order = await self.store.create(
            "SalesOrder",
            {
                "orderNo": order_no,
                "outletRid": outlet.rid,
                "salesRepRid": outlet.properties.get("salesRepRid"),
                "orderDate": order_date.isoformat(),
                "requestedDeliveryDate": delivery_date.isoformat(),
                "status": "confirmed",
                "channel": self.random.choice(["phone", "message", "app"]),
                "totalAmount": subtotal,
                "taxAmount": taxable * TAX_RATE_NUMERATOR // TAX_RATE_DENOMINATOR,
                "totalCases": total_cases,
            },
        )
        from ontology_runtime.store.link_store import LinkStore

        links = LinkStore(self.registry, self.session)
        await links.create("outletOrders", outlet.rid, order.rid)
        if outlet.properties.get("salesRepRid"):
            await links.create("orderSalesRep", order.rid, outlet.properties["salesRepRid"])

        for index, (product, cases, case_price, amount) in enumerate(lines, start=1):
            line = await self.store.create(
                "SalesOrderLine",
                {
                    "lineNo": f"{order_no}-{index:02d}",
                    "orderedCases": cases,
                    "unitPrice": case_price,
                    "lineAmount": amount,
                    "productName": product.properties["name"],
                    "productRid": product.rid,
                },
            )
            await links.create("orderLines", order.rid, line.rid)
        return order

    async def _delivery(
        self,
        delivery_date: dt.date,
        orders: list[Any],
        products: list[Any],
        depot: Any,
        drivers: list[Any],
        vehicles: list[Any],
    ) -> None:
        from ontology_runtime.store.link_store import LinkStore

        links = LinkStore(self.registry, self.session)
        if not orders or not drivers or not vehicles:
            return

        groups = min(len(orders), self.random.randint(1, 3))
        max(1, len(orders) // groups)
        delivery_no = f"DL-{delivery_date.strftime('%Y%m%d')}"
        self.summary.deliveries += 1

        delivery = await self.store.create(
            "Delivery",
            {
                "deliveryNo": delivery_no,
                "deliveryDate": delivery_date.isoformat(),
                "depotRid": depot.rid,
                "driverRid": drivers[0].rid,
                "vehicleRid": vehicles[0].rid,
                "status": "completed",
                "totalStops": len(orders),
                "totalCases": sum(int(o.properties["totalCases"]) for o in orders),
                "plannedDistanceKm": round(self.random.uniform(25, 80), 1),
                "plannedDurationMin": self.random.randint(150, 320),
            },
        )
        await links.create("deliveryDepot", delivery.rid, depot.rid)
        await links.create("deliveryDriver", delivery.rid, drivers[0].rid)
        await links.create("deliveryVehicle", delivery.rid, vehicles[0].rid)

        for index, order in enumerate(orders, start=1):
            outlet_rid = order.properties["outletRid"]
            planned_cases = int(order.properties["totalCases"])
            failed = self.random.random() < FAILURE_RATE
            stop = await self.store.create(
                "DeliveryStop",
                {
                    "stopNo": f"{delivery_no}-{index:03d}",
                    "sequence": index,
                    "status": "failed" if failed else "completed",
                    "plannedAt": (
                        dt.datetime.combine(delivery_date, dt.time(9, 0))
                        + dt.timedelta(minutes=25 * index)
                    ).isoformat(),
                    "arrivedAt": (
                        dt.datetime.combine(delivery_date, dt.time(9, 5))
                        + dt.timedelta(minutes=25 * index)
                    ).isoformat(),
                    "completedAt": (
                        dt.datetime.combine(delivery_date, dt.time(9, 15))
                        + dt.timedelta(minutes=25 * index)
                    ).isoformat(),
                    "plannedCases": planned_cases,
                    "actualCases": 0 if failed else planned_cases,
                    "failureReason": "영업중아님" if failed else None,
                    "outletRid": outlet_rid,
                    "deliveryRid": delivery.rid,
                },
            )
            self.summary.stops += 1
            await links.create("deliveryStops", delivery.rid, stop.rid)
            await links.create("outletStops", outlet_rid, stop.rid)
            await links.create("orderStop", order.rid, stop.rid)

            if not failed:
                await self._invoice(order, stop, products, links)
                await self.store.update(order.rid, {"status": "fulfilled"})
            else:
                await self.store.update(order.rid, {"status": "partially_fulfilled"})

    async def _invoice(self, order: Any, stop: Any, products: list[Any], links: Any) -> None:
        invoice_no = f"INV-{self.random.randint(100000, 999999)}"
        lines = await links.targets(self.registry.link_on("SalesOrder", "lines"), order.rid)
        subtotal = sum(int(line.properties["lineAmount"]) for line in lines)
        taxable = 0
        for line in lines:
            product = next(
                (p for p in products if p.rid == line.properties.get("productRid")), None
            )
            if product is None or product.properties.get("taxType") != "면세":
                taxable += int(line.properties["lineAmount"])

        invoice = await self.store.create(
            "SalesInvoice",
            {
                "invoiceNo": invoice_no,
                "issueDate": stop.properties["completedAt"][:10],
                "totalAmount": subtotal,
                "taxAmount": taxable * TAX_RATE_NUMERATOR // TAX_RATE_DENOMINATOR,
                "totalCases": int(order.properties["totalCases"]),
                "status": "issued",
                "outletRid": order.properties["outletRid"],
            },
        )
        self.summary.invoices += 1
        await links.create("orderInvoice", order.rid, invoice.rid)
        await links.create("invoiceStop", invoice.rid, stop.rid)
        for index, line in enumerate(lines, start=1):
            inv_line = await self.store.create(
                "InvoiceLine",
                {
                    "invoiceLineNo": f"{invoice_no}-{index:02d}",
                    "deliveredCases": int(line.properties["orderedCases"]),
                    "unitPrice": int(line.properties["unitPrice"]),
                    "lineAmount": int(line.properties["lineAmount"]),
                    "productRid": line.properties["productRid"],
                    "orderLineRid": line.rid,
                },
            )
            await links.create("invoiceLines", invoice.rid, inv_line.rid)

    # -- helpers -----------------------------------------------------------
    def _person_name(self) -> str:
        return f"{self.random.choice(NAMES_FAMILY)}{self.random.choice(NAMES_GIVEN)}"

    def _biz_reg_no(self) -> str:
        return (
            f"{self.random.randint(100, 999)}-"
            f"{self.random.randint(10, 99)}-"
            f"{self.random.randint(10000, 99999)}"
        )

    def _phone(self) -> str:
        return f"010-{self.random.randint(1000, 9999)}-{self.random.randint(1000, 9999)}"
