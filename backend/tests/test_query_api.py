from httpx import AsyncClient

from tests.conftest import FakeSafeQueryExecutor


def connection_payload() -> dict[str, object]:
    return {
        "name": "Ecommerce DB",
        "host": "demo-db",
        "port": 5432,
        "database_name": "demo_ecommerce",
        "username": "dashboard_reader",
        "password": "dashboard_reader_dev",
        "ssl_mode": "disable",
    }


async def create_connection(client: AsyncClient) -> str:
    response = await client.post("/api/database-connections", json=connection_payload())
    assert response.status_code == 201
    return response.json()["id"]


async def create_session(client: AsyncClient) -> str:
    response = await client.post("/api/sessions", json={"title": "Query analysis"})
    assert response.status_code == 201
    return response.json()["id"]


async def test_validate_safe_and_destructive_queries(client: AsyncClient) -> None:
    connection_id = await create_connection(client)

    safe = await client.post(
        f"/api/database-connections/{connection_id}/queries/validate",
        json={"sql": "SELECT COUNT(*) FROM orders"},
    )
    destructive = await client.post(
        f"/api/database-connections/{connection_id}/queries/validate",
        json={"sql": "DELETE FROM orders"},
    )

    assert safe.status_code == 200
    assert safe.json() == {
        "valid": True,
        "errors": [],
        "referenced_tables": ["orders"],
        "statement_type": "SELECT",
    }
    assert destructive.status_code == 200
    assert destructive.json()["valid"] is False
    assert destructive.json()["statement_type"] == "DELETE"


async def test_execute_query_returns_controlled_result(
    client: AsyncClient, fake_query_executor: FakeSafeQueryExecutor
) -> None:
    connection_id = await create_connection(client)

    response = await client.post(
        f"/api/database-connections/{connection_id}/queries/execute",
        json={"sql": "SELECT status, COUNT(*) AS count FROM orders GROUP BY status"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "columns": ["status", "count"],
        "rows": [{"status": "paid", "count": 42}],
        "row_count": 1,
        "truncated": False,
        "execution_time_ms": 1.25,
    }
    assert fake_query_executor.call_count == 1


async def test_session_execution_and_history(client: AsyncClient) -> None:
    session_id = await create_session(client)
    connection_id = await create_connection(client)
    attach = await client.put(f"/api/sessions/{session_id}/database-connection/{connection_id}")
    assert attach.status_code == 200

    success = await client.post(
        f"/api/sessions/{session_id}/queries/execute",
        json={"sql": "SELECT COUNT(*) AS count FROM orders"},
    )
    rejected = await client.post(
        f"/api/sessions/{session_id}/queries/execute",
        json={"sql": "DROP TABLE orders"},
    )
    history = await client.get(f"/api/sessions/{session_id}/queries")

    assert success.status_code == 200
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "QUERY_VALIDATION_FAILED"
    assert history.status_code == 200
    assert [item["status"] for item in history.json()] == [
        "VALIDATION_FAILED",
        "SUCCESS",
    ]
    assert history.json()[0]["error_message"] == "DROP statements are not allowed"
    assert all("rows" not in item for item in history.json())


async def test_session_without_connection_is_rejected(client: AsyncClient) -> None:
    session_id = await create_session(client)

    response = await client.post(
        f"/api/sessions/{session_id}/queries/execute",
        json={"sql": "SELECT 1"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == ("session_database_connection_required")


async def test_multiple_statements_never_reach_executor(
    client: AsyncClient, fake_query_executor: FakeSafeQueryExecutor
) -> None:
    connection_id = await create_connection(client)

    response = await client.post(
        f"/api/database-connections/{connection_id}/queries/execute",
        json={"sql": "SELECT * FROM orders; DROP TABLE orders;"},
    )

    assert response.status_code == 400
    assert fake_query_executor.call_count == 0
