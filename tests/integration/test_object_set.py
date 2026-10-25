"""Filter DSL and object set behaviour against PostgreSQL."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.errors import ValidationFailed
from ontology_runtime.query import AggregateSpec, ObjectSetService, OrderBy, compile_filter
from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.store.link_store import LinkStore
from ontology_runtime.store.object_store import ObjectStore

OUTLETS = [
    ("가나식당", "음식점", "active", 1),
    ("나나마트", "소매점", "active", 2),
    ("다다집", "음식점", "closed", 1),
    ("라라상회", "소매점", "active", 3),
    ("마마분식", "음식점", "active", 2),
]


@pytest.fixture
def services(demo_registry: SchemaRegistry, session: AsyncSession):
    return (
        ObjectStore(demo_registry, session),
        ObjectSetService(demo_registry, session),
        demo_registry,
    )


@pytest.fixture
async def seeded(services):
    objects, sets, registry = services
    created = []
    for name, outlet_type, status, weekday in OUTLETS:
        created.append(
            await objects.create(
                "Outlet",
                {
                    "name": name,
                    "outletType": outlet_type,
                    "status": status,
                    "deliveryWeekday": weekday,
                },
            )
        )
    return objects, sets, registry, created


async def test_search_returns_all(seeded) -> None:
    _, sets, _, _ = seeded
    page = await sets.search("Outlet")
    assert page.total == len(OUTLETS)


async def test_eq_filter(seeded) -> None:
    _, sets, _, _ = seeded
    page = await sets.search(
        "Outlet", filter={"field": "outletType", "op": "eq", "value": "음식점"}
    )
    assert page.total == 3


async def test_ne_filter(seeded) -> None:
    _, sets, _, _ = seeded
    page = await sets.search("Outlet", filter={"field": "status", "op": "ne", "value": "active"})
    assert [o.properties["name"] for o in page.objects] == ["다다집"]


async def test_numeric_comparison(seeded) -> None:
    _, sets, _, _ = seeded
    page = await sets.search("Outlet", filter={"field": "deliveryWeekday", "op": "gte", "value": 2})
    assert page.total == 3  # weekdays 2, 2, 3


async def test_in_filter(seeded) -> None:
    _, sets, _, _ = seeded
    page = await sets.search(
        "Outlet", filter={"field": "name", "op": "in", "value": ["가나식당", "다다집"]}
    )
    assert page.total == 2


async def test_startswith_filter(seeded) -> None:
    _, sets, _, _ = seeded
    page = await sets.search("Outlet", filter={"field": "name", "op": "startswith", "value": "나"})
    assert [o.properties["name"] for o in page.objects] == ["나나마트"]


async def test_contains_filter(seeded) -> None:
    _, sets, _, _ = seeded
    page = await sets.search("Outlet", filter={"field": "name", "op": "contains", "value": "식당"})
    assert [o.properties["name"] for o in page.objects] == ["가나식당"]


async def test_is_null_filter(seeded) -> None:
    _, sets, _, _ = seeded
    page = await sets.search("Outlet", filter={"field": "deliveryWeekday", "op": "isNull"})
    assert page.total == 0
    page = await sets.search(
        "Outlet", filter={"field": "deliveryWeekday", "op": "isNull", "value": False}
    )
    assert page.total == len(OUTLETS)


async def test_and_or_filters(seeded) -> None:
    _, sets, _, _ = seeded
    page = await sets.search(
        "Outlet",
        filter={
            "and": [
                {"field": "status", "op": "eq", "value": "active"},
                {"field": "outletType", "op": "eq", "value": "음식점"},
            ]
        },
    )
    assert page.total == 2

    page = await sets.search(
        "Outlet",
        filter={
            "or": [
                {"field": "deliveryWeekday", "op": "eq", "value": 3},
                {"field": "status", "op": "eq", "value": "closed"},
            ]
        },
    )
    assert page.total == 2


async def test_not_filter(seeded) -> None:
    _, sets, _, _ = seeded
    page = await sets.search(
        "Outlet", filter={"not": {"field": "status", "op": "eq", "value": "active"}}
    )
    assert page.total == 1


async def test_unknown_field_rejected(seeded) -> None:
    _, sets, _, _ = seeded
    with pytest.raises(ValidationFailed) as exc:
        await sets.search("Outlet", filter={"field": "ghost", "op": "eq", "value": 1})
    assert exc.value.violations[0]["path"] == "filter.field"


async def test_unknown_operator_rejected(seeded) -> None:
    _, sets, _, _ = seeded
    with pytest.raises(ValidationFailed) as exc:
        await sets.search("Outlet", filter={"field": "name", "op": "matches", "value": "x"})
    assert "unknown operator" in exc.value.violations[0]["message"]


async def test_field_name_cannot_inject_sql(seeded) -> None:
    _, sets, _, _ = seeded
    with pytest.raises(ValidationFailed):
        await sets.search(
            "Outlet",
            filter={"field": "name') OR 1=1--", "op": "eq", "value": "x"},
        )


async def test_type_mismatch_rejected(seeded) -> None:
    _, sets, _, _ = seeded
    with pytest.raises(ValidationFailed) as exc:
        await sets.search("Outlet", filter={"field": "deliveryWeekday", "op": "eq", "value": "two"})
    assert "expected integer" in exc.value.violations[0]["message"]


async def test_order_by_and_paging(seeded) -> None:
    _, sets, _, _ = seeded
    # Numeric ordering avoids collation-dependent Korean string ordering.
    page = await sets.search(
        "Outlet",
        order_by=[OrderBy("deliveryWeekday", "desc"), OrderBy("name", "asc")],
        page_size=2,
        page_token=0,
    )
    assert [o.properties["deliveryWeekday"] for o in page.objects] == [3, 2]
    assert page.total == 5
    assert page.to_dict()["meta"]["nextPageToken"] == 1

    second = await sets.search(
        "Outlet",
        order_by=[OrderBy("deliveryWeekday", "desc"), OrderBy("name", "asc")],
        page_size=2,
        page_token=1,
    )
    assert [o.properties["deliveryWeekday"] for o in second.objects] == [2, 1]


async def test_order_by_unknown_field_rejected(seeded) -> None:
    _, sets, _, _ = seeded
    with pytest.raises(ValidationFailed):
        await sets.search("Outlet", order_by=[OrderBy("ghost")])


async def test_aggregate_group_by(seeded) -> None:
    _, sets, _, _ = seeded
    rows = await sets.aggregate(
        "Outlet",
        AggregateSpec(
            groupBy=["outletType"],
            select=[{"op": "count", "as": "outletCount"}],
        ),
    )
    counts = {row["outletType"]: row["outletCount"] for row in rows}
    assert counts == {"음식점": 3, "소매점": 2}


async def test_aggregate_sum_with_filter(seeded) -> None:
    _, sets, _, _ = seeded
    rows = await sets.aggregate(
        "Outlet",
        AggregateSpec(
            groupBy=[],
            select=[{"op": "sum", "field": "deliveryWeekday", "as": "totalWeekday"}],
            filter={"field": "status", "op": "eq", "value": "active"},
        ),
    )
    assert rows[0]["totalWeekday"] == 8  # 1 + 2 + 3 + 2


async def test_aggregate_rejects_non_numeric_sum(seeded) -> None:
    _, sets, _, _ = seeded
    with pytest.raises(ValidationFailed) as exc:
        await sets.aggregate("Outlet", AggregateSpec(select=[{"op": "sum", "field": "name"}]))
    assert "requires a numeric property" in exc.value.violations[0]["message"]


async def test_search_around_link(seeded) -> None:
    objects, sets, _, created = seeded
    links = LinkStore(objects.registry, objects.session)
    outlet = created[0]
    order = await objects.create("Order", {"orderNo": "SO-100", "status": "draft"})
    await links.create("orders", outlet.rid, order.rid)

    page = await sets.search_around(outlet.rid, "orders")
    assert [o.properties["orderNo"] for o in page.objects] == ["SO-100"]

    inverse = await sets.search_around(order.rid, "outlet")
    assert [o.rid for o in inverse.objects] == [outlet.rid]


async def test_compile_filter_returns_none_for_empty() -> None:
    assert compile_filter("Outlet", {}, None) is None
