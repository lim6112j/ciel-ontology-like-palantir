"""Object store integration tests against PostgreSQL."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.errors import NotFoundError, ValidationFailed, VersionConflict
from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.store.object_store import ObjectStore, new_rid


@pytest.fixture
def store(demo_registry: SchemaRegistry, session: AsyncSession) -> ObjectStore:
    return ObjectStore(demo_registry, session)


async def _outlet(store: ObjectStore, name: str = "행복식당", **props):
    return await store.create(
        "Outlet",
        {"name": name, "outletType": "음식점", "status": "active", **props},
    )


async def test_create_and_get(store: ObjectStore) -> None:
    created = await _outlet(store)
    assert created.rid.startswith("ri.phonebook.object.outlet.")
    assert created.version == 1

    fetched = await store.get(created.rid)
    assert fetched.properties["name"] == "행복식당"
    assert fetched.properties["status"] == "active"


async def test_rid_is_unique_per_object(store: ObjectStore) -> None:
    first = await _outlet(store, "A")
    second = await _outlet(store, "B")
    assert first.rid != second.rid


async def test_new_rid_shape() -> None:
    rid = new_rid("SalesOrder", "acme")
    assert rid.startswith("ri.acme.object.salesorder.")


async def test_unknown_property_rejected(store: ObjectStore) -> None:
    with pytest.raises(ValidationFailed) as exc:
        await store.create(
            "Outlet",
            {"name": "X", "outletType": "음식점", "status": "active", "ghost": 1},
        )
    assert exc.value.violations[0]["code"] == "unknown_property"


async def test_required_property_enforced(store: ObjectStore) -> None:
    # `name` has no default; `status` does, so only `name` can be omitted here.
    with pytest.raises(ValidationFailed) as exc:
        await store.create("Outlet", {"outletType": "음식점"})
    assert any(v["path"] == "name" for v in exc.value.violations)


async def test_default_value_applied(store: ObjectStore) -> None:
    created = await store.create("Outlet", {"name": "기본값식당", "outletType": "음식점"})
    assert created.properties["status"] == "active"


async def test_enum_value_enforced(store: ObjectStore) -> None:
    with pytest.raises(ValidationFailed):
        await _outlet(store, status="unknown")


async def test_primary_key_uniqueness(store: ObjectStore) -> None:
    await _outlet(store, "같은이름")
    with pytest.raises(ValidationFailed) as exc:
        await _outlet(store, "같은이름")
    assert exc.value.violations[0]["code"] == "duplicate_value"


async def test_update_patches_and_bumps_version(store: ObjectStore) -> None:
    created = await _outlet(store)
    updated = await store.update(created.rid, {"deliveryWeekday": 2})
    assert updated.version == 2
    assert updated.properties["deliveryWeekday"] == 2
    # untouched properties survive
    assert updated.properties["name"] == "행복식당"


async def test_update_rejects_unknown_property(store: ObjectStore) -> None:
    created = await _outlet(store)
    with pytest.raises(ValidationFailed):
        await store.update(created.rid, {"ghost": 1})


async def test_optimistic_concurrency_conflict(store: ObjectStore) -> None:
    created = await _outlet(store)
    await store.update(created.rid, {"deliveryWeekday": 1}, expected_version=1)
    with pytest.raises(VersionConflict):
        await store.update(created.rid, {"deliveryWeekday": 3}, expected_version=1)


async def test_soft_delete_hides_object(store: ObjectStore) -> None:
    created = await _outlet(store)
    await store.soft_delete(created.rid)
    with pytest.raises(NotFoundError):
        await store.get(created.rid)
    deleted = await store.get(created.rid, include_deleted=True)
    assert deleted.deleted_at is not None


async def test_restore_returns_object(store: ObjectStore) -> None:
    created = await _outlet(store)
    await store.soft_delete(created.rid)
    restored = await store.restore(created.rid)
    assert restored.deleted_at is None
    assert (await store.get(created.rid)).rid == created.rid


async def test_get_many_preserves_request_order(store: ObjectStore) -> None:
    first = await _outlet(store, "A")
    second = await _outlet(store, "B")
    found = await store.get_many([second.rid, first.rid, "ri.phonebook.object.outlet.missing"])
    assert [obj.rid for obj in found] == [second.rid, first.rid]


async def test_properties_are_immutable_copies(store: ObjectStore) -> None:
    created = await _outlet(store)
    created.properties["name"] = "조작"
    assert (await store.get(created.rid)).properties["name"] == "행복식당"
