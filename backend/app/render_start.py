"""Single-process Render entry point; no shell or proxy subprocess is required."""

import os
import subprocess
from collections.abc import MutableMapping

from sqlalchemy.engine import make_url


def configure_environment(env: MutableMapping[str, str]) -> int:
    for key, value in {
        "APP_ENV": "production",
        "ACCESS_MODE": "public",
        "DEPLOYMENT_MODE": "render",
    }.items():
        if env.get(key, value) != value:
            raise ValueError(f"{key} is not valid for the Render image")
        env[key] = value
    origin = env.get("PUBLIC_ORIGIN") or env.get("RENDER_EXTERNAL_URL")
    if not origin:
        raise ValueError("PUBLIC_ORIGIN or RENDER_EXTERNAL_URL is required")
    env["PUBLIC_ORIGIN"] = origin.rstrip("/")
    raw_url = env.get("APP_DATABASE_URL", "")
    if raw_url.startswith("postgres://"):
        raw_url = "postgresql://" + raw_url.removeprefix("postgres://")
    try:
        url = make_url(raw_url)
        if url.drivername not in {"postgresql", "postgresql+psycopg"} or not url.host:
            raise ValueError("Unsupported database URL")
        url = url.set(drivername="postgresql+psycopg").update_query_dict(
            {"sslmode": "verify-full", "sslrootcert": url.query.get("sslrootcert", "system")}
        )
        env["APP_DATABASE_URL"] = url.render_as_string(hide_password=False)
    except Exception as exc:
        raise ValueError("APP_DATABASE_URL must be a valid Neon PostgreSQL connection URL") from exc
    try:
        port = int(env.get("PORT", "10000"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError as exc:
        raise ValueError("PORT must be between 1 and 65535") from exc
    return port


def main() -> None:
    try:
        port = configure_environment(os.environ)
        from app.config import get_settings

        get_settings()  # Fail closed before migrations or binding a port.
        # Migration failures may contain a full DSN in a driver/ConfigParser traceback.
        # Keep that output out of the hosting provider's logs.
        subprocess.run(
            ["alembic", "upgrade", "head"], check=True, capture_output=True, timeout=120
        )
    except Exception as exc:
        # Avoid traceback/driver text containing a database URL or password.
        raise SystemExit(
            f"Startup failed ({type(exc).__name__}); check the deployment settings"
        ) from None
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        workers=1,
        proxy_headers=True,
        forwarded_allow_ips="*",
        server_header=False,
    )


if __name__ == "__main__":
    main()
