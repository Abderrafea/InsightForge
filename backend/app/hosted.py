"""Production defaults for an ASGI platform that starts the app itself."""

from collections.abc import MutableMapping
from pathlib import Path

from app.render_start import configure_environment


def configure_cloud_environment(env: MutableMapping[str, str]) -> None:
    configure_environment(env, deployment_mode="direct")
    defaults = {
        "FRONTEND_DIST_DIR": str(Path(__file__).resolve().parent.parent / "dist"),
        "MAX_CONCURRENT_REQUESTS": "2",
        "APP_DB_POOL_SIZE": "3",
        "AGENT_RESULT_SAMPLE_ROWS": "0",
    }
    for key, value in defaults.items():
        env.setdefault(key, value)
    # Public deployments exclusively use visitor-supplied keys.
    for key in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        env[key] = ""
