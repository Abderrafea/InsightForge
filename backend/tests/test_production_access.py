import asyncio

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.config import Settings
from app.core.access import ProductionAccessMiddleware
from app.core.exceptions import ExternalDatabaseConnectionError
from app.database.connection_manager import ExternalDatabaseConnectionManager
from app.database.external_database import ExternalDatabaseCredentials

TOKEN = "test-proxy-token-which-is-long-enough-123456"


def production_settings(**overrides: object) -> Settings:
    values = {
        "_env_file": None,
        "app_env": "production",
        "app_database_url": "postgresql+psycopg://app:random-password@app-db/insightforge",
        "secret_encryption_key": Fernet.generate_key().decode(),
        "access_proxy_token": TOKEN,
        "public_origin": "https://analytics.example.com",
        "external_db_allowed_targets": "analytics-db.example.com:5432",
        "ai_model": "test-model",
        "groq_api_key": "test-key",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize(
    "overrides",
    [
        {"access_proxy_token": None},
        {"access_proxy_token": "short"},
        {"public_origin": "http://analytics.example.com"},
        {"public_origin": "https://analytics.example.com/path"},
        {"secret_encryption_key": "7B1wI_gfTi94x_6crw4VBbg4FPVkudmkx5zeO0oBHho="},
        {"secret_encryption_key": "invalid"},
        {"external_db_allowed_targets": ""},
        {"app_database_url": "sqlite+aiosqlite://"},
        {"app_database_url": "postgresql+psycopg://app:insightforge_dev@app-db/db"},
        {"ai_model": None},
        {"groq_api_key": None},
        {"app_env": "prodution"},
    ],
)
def test_production_rejects_unsafe_configuration(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        production_settings(**overrides)


async def test_production_access_and_csrf_boundary() -> None:
    app = FastAPI()
    app.add_middleware(ProductionAccessMiddleware, settings=production_settings())

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/sessions")
    async def sessions() -> list:
        return []

    @app.post("/api/sessions")
    async def create(request: Request) -> dict:
        return await request.json()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        assert (await client.get("/health")).status_code == 200
        assert (await client.get("/api/sessions")).status_code == 401
        assert (
            await client.get(
                "/api/sessions",
                headers={
                    "X-InsightForge-Proxy-Token": "forged",
                },
            )
        ).status_code == 401
        headers = {"X-InsightForge-Proxy-Token": TOKEN}
        response = await client.get("/api/sessions", headers=headers)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert (await client.post("/api/sessions", headers=headers, json={})).status_code == 403
        headers["X-Requested-With"] = "InsightForge"
        headers["Origin"] = "https://attacker.example.com"
        assert (await client.post("/api/sessions", headers=headers, json={})).status_code == 403
        headers["Origin"] = "https://analytics.example.com"
        response = await client.post("/api/sessions", headers=headers, json={"title": "Allowed"})
        assert response.status_code == 200
        assert response.json() == {"title": "Allowed"}
        response = await client.post("/api/sessions", headers=headers, content=b"x" * 65_537)
        assert response.status_code == 413


async def test_concurrency_limit_releases_after_request() -> None:
    app = FastAPI()
    app.add_middleware(
        ProductionAccessMiddleware,
        settings=production_settings(max_concurrent_requests=1),
    )
    started, finish = asyncio.Event(), asyncio.Event()

    @app.get("/api/slow")
    async def slow() -> dict:
        started.set()
        await finish.wait()
        return {"ok": True}

    headers = {"X-InsightForge-Proxy-Token": TOKEN}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        first = asyncio.create_task(client.get("/api/slow", headers=headers))
        try:
            await asyncio.wait_for(started.wait(), timeout=2)
            assert (await client.get("/api/slow", headers=headers)).status_code == 429
        finally:
            finish.set()
        assert (await first).status_code == 200
        assert (await client.get("/api/slow", headers=headers)).status_code == 200


@pytest.mark.parametrize(
    ("host", "ssl_mode"),
    [
        ("169.254.169.254", "verify-full"),
        ("app-db", "verify-full"),
        ("analytics-db.example.com", "disable"),
    ],
)
async def test_external_connection_policy_blocks_before_network(host: str, ssl_mode: str) -> None:
    manager = ExternalDatabaseConnectionManager(
        allowed_targets={"analytics-db.example.com:5432"},
        require_tls=True,
    )
    credentials = ExternalDatabaseCredentials(
        host=host,
        port=5432,
        database_name="analytics",
        username="reader",
        password="not-used",
        ssl_mode=ssl_mode,
    )
    with pytest.raises(ExternalDatabaseConnectionError):
        async with manager.connection(credentials):
            pytest.fail("A blocked connection must not reach the database")
