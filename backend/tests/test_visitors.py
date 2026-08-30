import asyncio
import socket
from unittest.mock import AsyncMock
from uuid import uuid4

import certifi
import psycopg
import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from starlette.requests import Request

from app.config import Settings, get_settings
from app.core.exceptions import ExternalDatabaseConnectionError
from app.core.visitors import read_visitor_cookie, visitor_cookie
from app.database.app_database import get_access_session
from app.database.connection_manager import ExternalDatabaseConnectionManager
from app.database.external_database import ExternalDatabaseCredentials
from app.dependencies import (
    get_external_database_manager,
    get_llm_provider,
    get_safe_query_executor,
    get_schema_inspector,
)
from app.llm.exceptions import ProviderConfigurationError
from app.llm.factory import LLMFactory
from app.main import app
from app.models.user import User


def public_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="testing",
        app_database_url="sqlite+aiosqlite://",
        secret_encryption_key=Fernet.generate_key().decode(),
        access_mode="public",
        groq_api_key="server-key-must-not-be-used",
        ai_model="server-model",
    )


@pytest.fixture
async def visitors(
    database_session, fake_manager, fake_inspector, fake_query_executor, fake_llm_provider
):
    settings = public_settings()

    async def raw_db():
        yield database_session

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_access_session] = raw_db
    app.dependency_overrides[get_external_database_manager] = lambda: fake_manager
    app.dependency_overrides[get_schema_inspector] = lambda: fake_inspector
    app.dependency_overrides[get_safe_query_executor] = lambda: fake_query_executor
    app.dependency_overrides[get_llm_provider] = lambda: fake_llm_provider
    transport = ASGITransport(app=app)
    try:
        async with (
            AsyncClient(
                transport=transport,
                base_url="http://test",
                headers={"X-Requested-With": "InsightForge"},
            ) as a,
            AsyncClient(
                transport=transport,
                base_url="http://test",
                headers={"X-Requested-With": "InsightForge"},
            ) as b,
        ):
            yield a, b, settings
    finally:
        app.dependency_overrides.clear()


async def test_visitors_cannot_access_each_others_resources(visitors, database_session):
    a, b, settings = visitors
    assert (await a.get("/api/sessions")).status_code == 401
    start = await a.post("/api/access", json={})
    assert start.status_code == 200
    assert "HttpOnly" in start.headers["set-cookie"]
    assert "SameSite=strict" in start.headers["set-cookie"]
    assert (await b.post("/api/access", json={})).status_code == 200
    session_a = (await a.post("/api/sessions", json={"title": "Private A"})).json()["id"]
    session_b = (await b.post("/api/sessions", json={"title": "Private B"})).json()["id"]
    assert [item["id"] for item in (await a.get("/api/sessions")).json()] == [session_a]
    assert [item["id"] for item in (await b.get("/api/sessions")).json()] == [session_b]
    connection = (
        await a.post(
            "/api/database-connections",
            json={
                "name": "Private database",
                "host": "demo-db",
                "port": 5432,
                "database_name": "demo_ecommerce",
                "username": "reader",
                "password": "secret",
                "ssl_mode": "verify-full",
            },
        )
    ).json()["id"]
    assert (
        await a.put(f"/api/sessions/{session_a}/database-connection/{connection}")
    ).status_code == 200
    assert (
        await a.post(
            f"/api/sessions/{session_a}/agent/messages", json={"content": "Build a dashboard"}
        )
    ).status_code == 200
    for path in [
        f"/api/sessions/{session_a}",
        f"/api/sessions/{session_a}/messages",
        f"/api/sessions/{session_a}/dashboard",
        f"/api/sessions/{session_a}/queries",
        f"/api/database-connections/{connection}/schema",
    ]:
        assert (await b.get(path)).status_code == 404, path
    assert (
        await b.patch(f"/api/sessions/{session_a}", json={"title": "Stolen"})
    ).status_code == 404
    assert (await b.delete(f"/api/sessions/{session_a}")).status_code == 404
    assert (
        await b.put(f"/api/sessions/{session_b}/database-connection/{connection}")
    ).status_code == 404
    for path in [
        f"/api/sessions/{session_a}/queries/execute",
        f"/api/database-connections/{connection}/queries/validate",
        f"/api/database-connections/{connection}/queries/execute",
    ]:
        assert (await b.post(path, json={"sql": "SELECT COUNT(*) FROM orders"})).status_code == 404
    assert (
        await b.post(f"/api/sessions/{session_a}/agent/messages", json={"content": "Modify it"})
    ).status_code == 404
    assert (await a.delete("/api/access")).status_code == 204
    assert (await a.get("/api/sessions")).status_code == 401
    assert (await b.get(f"/api/sessions/{session_b}")).status_code == 200
    assert await database_session.scalar(select(func.count()).select_from(User)) == 1


def test_visitor_cookie_rejects_tampering_expiry_and_other_payloads():
    settings = public_settings()
    user = uuid4()
    assert read_visitor_cookie(visitor_cookie(user, settings), settings) == user
    assert read_visitor_cookie("forged-cookie", settings) is None
    cipher = Fernet(settings.secret_encryption_key.get_secret_value())
    assert (
        read_visitor_cookie(
            cipher.encrypt_at_time(f"visitor:v1:{user}".encode(), current_time=1).decode(), settings
        )
        is None
    )
    assert read_visitor_cookie(cipher.encrypt(b"a-database-password").decode(), settings) is None


def test_public_provider_uses_request_key_and_never_server_key(monkeypatch):
    settings = public_settings()
    received = []
    monkeypatch.setattr(LLMFactory, "create", lambda config: received.append(config) or "provider")
    request = Request(
        {
            "type": "http",
            "headers": [
                (b"authorization", b"Bearer visitor-key"),
                (b"x-ai-model", b"openai/gpt-oss-120b"),
            ],
        }
    )
    assert get_llm_provider(request, settings) == "provider"
    assert received[0].groq_api_key.get_secret_value() == "visitor-key"
    assert settings.groq_api_key.get_secret_value() == "server-key-must-not-be-used"
    with pytest.raises(ProviderConfigurationError):
        get_llm_provider(Request({"type": "http", "headers": []}), settings)


@pytest.mark.parametrize(
    "ips",
    [
        ["127.0.0.1"],
        ["169.254.169.254"],
        ["10.0.0.1"],
        ["8.8.8.8", "127.0.0.1"],
        ["64:ff9b::7f00:1"],
        ["64:ff9b::a00:1"],
        ["64:ff9b:1::808:808"],
        ["2002:7f00:1::"],
    ],
)
async def test_public_databases_reject_private_and_mixed_dns(ips, monkeypatch):
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(
        loop,
        "getaddrinfo",
        AsyncMock(
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 5432)) for ip in ips]
        ),
    )
    connect = AsyncMock()
    monkeypatch.setattr("app.database.connection_manager.AsyncConnection.connect", connect)
    manager = ExternalDatabaseConnectionManager(public_only=True, require_tls=True)
    credentials = ExternalDatabaseCredentials(
        host="database.example.com",
        port=5432,
        database_name="db",
        username="reader",
        password="secret",
        ssl_mode="verify-full",
    )
    with pytest.raises(ExternalDatabaseConnectionError):
        async with manager.connection(credentials):
            pytest.fail("Private network must not be reached")
    connect.assert_not_called()


async def test_public_database_pins_the_checked_address(monkeypatch):
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(
        loop,
        "getaddrinfo",
        AsyncMock(return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 5432))]),
    )
    connection = AsyncMock()
    connection.closed = False
    connect = AsyncMock(return_value=connection)
    monkeypatch.setattr("app.database.connection_manager.AsyncConnection.connect", connect)
    manager = ExternalDatabaseConnectionManager(public_only=True, require_tls=True)
    credentials = ExternalDatabaseCredentials(
        host="database.example.com",
        port=5432,
        database_name="db",
        username="reader",
        password="secret",
        ssl_mode="verify-full",
    )
    async with manager.connection(credentials):
        pass
    assert connect.call_args.kwargs["hostaddr"] == "8.8.8.8"
    assert connect.call_args.kwargs["host"] == "database.example.com"
    assert connect.call_args.kwargs["sslmode"] == "verify-full"
    assert connect.call_args.kwargs["sslrootcert"] == certifi.where()


async def test_public_database_tries_an_alternate_checked_address_family(monkeypatch):
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(
        loop,
        "getaddrinfo",
        AsyncMock(
            return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 5432)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.4.4", 5432)),
                (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("64:ff9b::808:808", 5432)),
            ]
        ),
    )
    connection = AsyncMock()
    connection.closed = False
    connect = AsyncMock(
        side_effect=[psycopg.OperationalError("network is unreachable"), connection]
    )
    monkeypatch.setattr("app.database.connection_manager.AsyncConnection.connect", connect)
    manager = ExternalDatabaseConnectionManager(public_only=True, require_tls=True)
    credentials = ExternalDatabaseCredentials(
        host="database.example.com",
        port=5432,
        database_name="db",
        username="reader",
        password="secret",
        ssl_mode="verify-full",
    )
    async with manager.connection(credentials):
        pass
    assert [call.kwargs["hostaddr"] for call in connect.call_args_list] == [
        "8.8.8.8",
        "64:ff9b::808:808",
    ]
    assert all(call.kwargs["host"] == credentials.host for call in connect.call_args_list)
    assert all(call.kwargs["sslmode"] == "verify-full" for call in connect.call_args_list)
