from httpx import AsyncClient

from tests.conftest import FakeSchemaInspector


async def test_schema_inspection_discovers_metadata_and_uses_cache(
    client: AsyncClient, fake_inspector: FakeSchemaInspector
) -> None:
    create_response = await client.post(
        "/api/database-connections",
        json={
            "name": "Ecommerce DB",
            "host": "demo-db",
            "port": 5432,
            "database_name": "demo_ecommerce",
            "username": "dashboard_reader",
            "password": "dashboard_reader_dev",
            "ssl_mode": "disable",
        },
    )
    connection_id = create_response.json()["id"]

    first = await client.get(f"/api/database-connections/{connection_id}/schema")
    cached = await client.get(f"/api/database-connections/{connection_id}/schema")
    refreshed = await client.get(f"/api/database-connections/{connection_id}/schema?refresh=true")

    assert first.status_code == 200
    assert cached.status_code == 200
    assert refreshed.status_code == 200
    assert fake_inspector.call_count == 2

    schema = first.json()
    orders = next(table for table in schema["tables"] if table["name"] == "orders")
    assert schema["database"] == "demo_ecommerce"
    assert schema["schemas"] == ["public"]
    assert orders["schema"] == "public"
    assert orders["columns"][0]["primary_key"] is True
    assert orders["foreign_keys"][0] == {
        "column": "customer_id",
        "references_schema": "public",
        "references_table": "customers",
        "references_column": "id",
    }
