from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CredentialCipher
from app.models.database_connection import DatabaseConnection

TEST_KEY = "7B1wI_gfTi94x_6crw4VBbg4FPVkudmkx5zeO0oBHho="


def connection_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "host": "demo-db",
        "port": 5432,
        "database_name": "demo_ecommerce",
        "username": "dashboard_reader",
        "password": "dashboard_reader_dev",
        "ssl_mode": "disable",
    }
    payload.update(overrides)
    return payload


async def save_connection(client: AsyncClient) -> dict:
    response = await client.post(
        "/api/database-connections",
        json={"name": "Ecommerce DB", **connection_payload()},
    )
    assert response.status_code == 201
    return response.json()


async def test_external_connection_success(client: AsyncClient) -> None:
    response = await client.post("/api/database-connections/test", json=connection_payload())

    assert response.status_code == 200
    assert response.json() == {"success": True}


async def test_incorrect_password_is_sanitized(client: AsyncClient) -> None:
    response = await client.post(
        "/api/database-connections/test",
        json=connection_payload(password="incorrect"),
    )

    assert response.status_code == 400
    assert "incorrect" not in response.text
    assert response.json()["error"]["code"] == "external_database_connection_failed"


async def test_unreachable_host_is_sanitized(client: AsyncClient) -> None:
    response = await client.post(
        "/api/database-connections/test",
        json=connection_payload(host="unreachable.invalid"),
    )

    assert response.status_code == 400
    assert "unreachable.invalid" not in response.text


async def test_invalid_port_does_not_echo_password(client: AsyncClient) -> None:
    secret = "never-echo-this"
    response = await client.post(
        "/api/database-connections/test",
        json=connection_payload(port=70_000, password=secret),
    )

    assert response.status_code == 422
    assert secret not in response.text


async def test_saved_credentials_are_encrypted_and_never_returned(
    client: AsyncClient, database_session: AsyncSession
) -> None:
    created = await save_connection(client)

    assert "password" not in created
    assert "encrypted_password" not in created
    assert "host" not in created
    assert "username" not in created
    record = (
        await database_session.scalars(
            select(DatabaseConnection).where(DatabaseConnection.id == UUID(created["id"]))
        )
    ).one()
    assert record.encrypted_password != "dashboard_reader_dev"
    assert CredentialCipher(TEST_KEY).decrypt_secret(record.encrypted_password) == (
        "dashboard_reader_dev"
    )


async def test_attached_connection_is_safe_in_session_response(
    client: AsyncClient,
) -> None:
    session_response = await client.post("/api/sessions", json={"title": "Ecommerce analysis"})
    connection = await save_connection(client)

    response = await client.put(
        f"/api/sessions/{session_response.json()['id']}/database-connection/{connection['id']}"
    )

    assert response.status_code == 200
    assert response.json()["database_connection"]["name"] == "Ecommerce DB"
    assert "password" not in response.text
    assert "encrypted_password" not in response.text
