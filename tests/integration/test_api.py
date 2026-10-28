"""API contract tests against a real database session."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ontology_runtime.api.app import create_app
from ontology_runtime.db import engine as engine_module
from ontology_runtime.domains.liquor.seed.generator import SeedGenerator

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def client(api_database_url: str):
    """Seed once per module; each test only reads or acts on that dataset."""
    from alembic import command
    from alembic.config import Config

    from ontology_runtime.config import PROJECT_ROOT

    migration_config = Config(str(PROJECT_ROOT / "alembic.ini"))
    migration_config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    migration_config.set_main_option("sqlalchemy.url", api_database_url)
    command.upgrade(migration_config, "head")

    engine = create_async_engine(api_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    # Engines are keyed per domain; point the default (liquor) at the test DB.
    engine_module._session_factories["liquor"] = factory  # noqa: SLF001 - test wiring

    app = create_app()
    async with factory() as setup_session:
        await setup_session.execute(
            text(
                "TRUNCATE objects, links, action_runs, action_edits, agent_runs, ontology_indexes "
                "RESTART IDENTITY CASCADE"
            )
        )
        await setup_session.commit()
        await SeedGenerator(app.state.registry, setup_session, seed=3).run()
        await setup_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http

    import os

    if os.environ.get("ONTOLOGY_KEEP_SEED") != "1":
        async with factory() as cleanup_session:
            await cleanup_session.execute(
                text(
                    "TRUNCATE objects, links, action_runs, action_edits, agent_runs RESTART IDENTITY CASCADE"
                )
            )
            await cleanup_session.commit()
    engine_module._session_factories.pop("liquor", None)  # noqa: SLF001
    await engine.dispose()


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["domain"] == "liquor"
    assert body["data"]["objectTypes"] == 16
    assert body["data"]["agents"] == 4


async def test_health_alias_under_api_prefix(client: AsyncClient) -> None:
    # Generated clients call `/api/<domain>/health`, which the proxy rewrites to
    # `/api/health`; the alias must answer the same payload.
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["data"]["domain"] == "liquor"


async def test_list_object_types(client: AsyncClient) -> None:
    response = await client.get("/api/ontology/objectTypes")
    data = response.json()["data"]
    names = {entry["apiName"] for entry in data}
    assert {"Outlet", "SalesOrder", "DeliveryStop", "ActionProposal"} <= names


async def test_get_object_type_detail(client: AsyncClient) -> None:
    response = await client.get("/api/ontology/objectTypes/SalesOrder")
    body = response.json()["data"]
    assert body["primaryKey"] == "orderNo"
    assert body["stateMachine"]["initial"] == "draft"
    assert {link["apiName"] for link in body["links"]} >= {"lines", "outlet"}


async def test_action_type_detail(client: AsyncClient) -> None:
    response = await client.get("/api/ontology/actionTypes/CompleteStop")
    body = response.json()["data"]
    assert body["functionBacked"] is True
    assert "actualCases" in body["parameters"]


async def test_search_objects(client: AsyncClient) -> None:
    response = await client.post(
        "/api/objectsets/Outlet/search",
        json={"filter": {"field": "status", "op": "eq", "value": "active"}, "pageSize": 5},
    )
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) == 5
    assert body["meta"]["total"] > 5


async def test_search_rejects_unknown_field(client: AsyncClient) -> None:
    response = await client.post(
        "/api/objectsets/Outlet/search",
        json={"filter": {"field": "ghost", "op": "eq", "value": 1}},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


async def test_aggregate(client: AsyncClient) -> None:
    response = await client.post(
        "/api/objectsets/SalesOrder/aggregate",
        json={"groupBy": ["status"], "select": [{"op": "count", "as": "n"}]},
    )
    rows = response.json()["data"]
    assert rows and rows[0]["status"] == "confirmed"


async def test_search_around_link(client: AsyncClient) -> None:
    outlets = (await client.post("/api/objectsets/Outlet/search", json={"pageSize": 1})).json()[
        "data"
    ]
    outlet_rid = outlets[0]["rid"]
    response = await client.get(f"/api/objects/Outlet/{outlet_rid}/links/orders")
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)


async def test_validate_then_apply_action(client: AsyncClient) -> None:
    outlets = (
        await client.post(
            "/api/objectsets/Outlet/search",
            json={"filter": {"field": "status", "op": "eq", "value": "active"}, "pageSize": 1},
        )
    ).json()["data"]
    outlets[0]["rid"]
    orders = (
        await client.post(
            "/api/objectsets/SalesOrder/search",
            json={"filter": {"field": "status", "op": "eq", "value": "confirmed"}, "pageSize": 1},
        )
    ).json()["data"]
    order_rid = orders[0]["rid"]

    validate = await client.post(
        "/api/actions/ConfirmSalesOrder/validate", json={"params": {"order": order_rid}}
    )
    assert validate.status_code == 200
    assert validate.json()["data"]["status"] == "failed"  # already confirmed

    apply = await client.post(
        "/api/actions/CancelSalesOrder/apply",
        json={"params": {"order": order_rid, "reason": "테스트"}},
        headers={"X-Actor": "manager01", "Idempotency-Key": "api-test-1"},
    )
    assert apply.status_code == 200
    assert apply.json()["data"]["status"] == "succeeded"

    replay = await client.post(
        "/api/actions/CancelSalesOrder/apply",
        json={"params": {"order": order_rid, "reason": "테스트"}},
        headers={"X-Actor": "manager01", "Idempotency-Key": "api-test-1"},
    )
    assert replay.json()["data"]["replayed"] is True


async def test_apply_failure_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/actions/CompleteStop/apply",
        json={"params": {"stop": "ri.liquor.object.deliverystop.missing", "actualCases": 1}},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


async def test_write_function_is_not_exposed(client: AsyncClient) -> None:
    response = await client.post("/api/functions/planDeliveries/execute", json={"params": {}})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "policy_violation"


async def test_read_function_executes(client: AsyncClient) -> None:
    response = await client.post(
        "/api/functions/detectDeliveryExceptions/execute",
        json={"params": {"deliveryDate": "2026-10-25"}},
    )
    assert response.status_code == 200
    assert "unassignedOrders" in response.json()["data"]


async def test_proposals_inbox(client: AsyncClient) -> None:
    response = await client.get("/api/proposals")
    assert response.status_code == 200
    assert response.json()["success"] is True


async def test_audit_runs_endpoint(client: AsyncClient) -> None:
    response = await client.get("/api/audit/actionRuns")
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


async def test_openapi_schema_is_served(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/actions/{action_name}/apply" in response.json()["paths"]
