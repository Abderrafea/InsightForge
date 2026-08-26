from types import SimpleNamespace

import certifi
from sqlalchemy.engine import make_url
from starlette.requests import Request

from app.hosted import configure_cloud_environment


def test_cloud_launch_uses_neon_tls_and_exclusively_visitor_ai_keys():
    env = {
        "APP_DATABASE_URL": "postgresql://owner:encoded%40password@db.neon.tech/neondb?sslmode=require",
        "PUBLIC_ORIGIN": "https://insightforge.fastapicloud.dev",
        "GROQ_API_KEY": "owner-key-that-must-not-be-used",
        "OPENAI_API_KEY": "owner-key-that-must-not-be-used",
        "ANTHROPIC_API_KEY": "owner-key-that-must-not-be-used",
    }
    configure_cloud_environment(env)
    assert env["DEPLOYMENT_MODE"] == "direct"
    assert env["ACCESS_MODE"] == "public"
    assert env["APP_ENV"] == "production"
    assert "sslmode=verify-full" in env["APP_DATABASE_URL"]
    assert make_url(env["APP_DATABASE_URL"]).query["sslrootcert"] == certifi.where()
    assert env["MAX_CONCURRENT_REQUESTS"] == "2"
    assert env["AGENT_RESULT_SAMPLE_ROWS"] == "0"
    assert env["FRONTEND_DIST_DIR"].endswith("dist")
    assert not any(env[key] for key in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"))


async def test_production_error_logs_omit_sensitive_exception_payload(monkeypatch, caplog):
    from app import main

    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(production=True))
    request = Request({"type": "http", "method": "GET", "path": "/api/sessions"})
    response = await main.unexpected_error_handler(
        request, RuntimeError("sensitive-driver-connection-password")
    )
    assert response.status_code == 500
    assert "RuntimeError" in caplog.text
    assert "sensitive-driver-connection-password" not in caplog.text
