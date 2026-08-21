import asyncio
import subprocess
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.config import Settings
from app.frontend import mount_frontend
from app.render_start import configure_environment


def render_settings(**overrides):
    values = dict(
        _env_file=None,
        app_env="production",
        deployment_mode="render",
        access_mode="public",
        public_origin="https://test.onrender.com",
        app_database_url="postgresql+psycopg://app:unique@app-db/app?sslmode=verify-full",
        secret_encryption_key=Fernet.generate_key().decode(),
    )
    values.update(overrides)
    return Settings(**values)


def test_render_start_normalizes_neon_url_and_preserves_password():
    env = {
        "APP_DATABASE_URL": "postgresql://app:encoded%40password@ep-example.neon.tech/neondb?sslmode=require&channel_binding=require",
        "RENDER_EXTERNAL_URL": "https://test.onrender.com",
        "PORT": "10000",
    }
    assert configure_environment(env) == 10000
    url = make_url(env["APP_DATABASE_URL"])
    assert url.drivername == "postgresql+psycopg"
    assert url.password == "encoded@password"
    assert url.query["sslmode"] == "verify-full"
    assert url.query["sslrootcert"] == "system"
    assert url.query["channel_binding"] == "require"
    assert env["PUBLIC_ORIGIN"] == "https://test.onrender.com"
    assert env["ACCESS_MODE"] == "public"


@pytest.mark.parametrize(
    "change",
    [
        {"ACCESS_MODE": "owner"},
        {"APP_ENV": "development"},
        {"APP_DATABASE_URL": "sqlite://"},
        {"PORT": "0"},
        {"PORT": "not-a-port"},
    ],
)
def test_render_start_rejects_unsafe_launch_settings(change):
    env = {
        "APP_DATABASE_URL": "postgresql://app:secret@db.example.com/app",
        "RENDER_EXTERNAL_URL": "https://test.onrender.com",
    }
    env.update(change)
    with pytest.raises(ValueError):
        configure_environment(env)


def test_render_requires_public_mode_but_no_gateway_secret():
    assert render_settings().access_proxy_token is None
    with pytest.raises(ValidationError, match="public visitor"):
        render_settings(access_mode="owner")
    with pytest.raises(ValidationError, match="ACCESS_PROXY_TOKEN"):
        render_settings(deployment_mode="gateway")


async def test_single_server_serves_spa_assets_and_preserves_api_404s(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "main.js").write_text("console.log('bundle')")
    (tmp_path / "index.html").write_text("<html>InsightForge SPA</html>")
    (tmp_path / "private.txt").write_text("must-not-leak")
    app = FastAPI()
    mount_frontend(app, str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        for path in ["/", f"/sessions/{uuid4()}", f"/sessions/{uuid4()}/dashboard"]:
            response = await client.get(path)
            assert response.status_code == 200 and "InsightForge SPA" in response.text
            assert response.headers["cache-control"] == "no-cache"
        assert (await client.get("/assets/main.js")).status_code == 200
        for path in [
            "/api/not-a-route",
            "/assets/missing.js",
            "/assets/%2e%2e/private.txt",
            "/private.txt",
        ]:
            response = await client.get(path)
            assert response.status_code == 404
            assert "must-not-leak" not in response.text


async def test_render_maintenance_runs_and_stops_with_app(monkeypatch):
    from app import maintenance

    calls = []
    started = asyncio.Event()

    async def clean():
        calls.append("cleanup")

    async def loop(interval):
        calls.append(interval)
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(
        maintenance,
        "get_settings",
        lambda: SimpleNamespace(
            deployment_mode="render", public_visitors=True, visitor_cleanup_interval_seconds=3600
        ),
    )
    monkeypatch.setattr(maintenance, "cleanup", clean)
    monkeypatch.setattr(maintenance, "cleanup_loop", loop)
    async with maintenance.lifespan(FastAPI()):
        await asyncio.wait_for(started.wait(), timeout=2)
        assert calls == ["cleanup", 3600]
def test_failed_migration_does_not_publish_driver_output(monkeypatch, capsys):
    from app import config, render_start

    captured = {}

    def fail(command, **kwargs):
        captured.update(kwargs)
        raise subprocess.CalledProcessError(1, command, stderr=b"sensitive-database-password")

    monkeypatch.setattr(render_start, "configure_environment", lambda env: 10000)
    monkeypatch.setattr(config, "get_settings", lambda: None)
    monkeypatch.setattr(render_start.subprocess, "run", fail)
    with pytest.raises(SystemExit, match="Startup failed") as error:
        render_start.main()
    assert captured["capture_output"] is True
    assert captured["timeout"] == 120
    assert "sensitive-database-password" not in str(error.value)
    assert "sensitive-database-password" not in capsys.readouterr().err


