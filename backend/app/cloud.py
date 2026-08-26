"""FastAPI Cloud entry point; migrate separately before deploying new code."""

import os

from app.hosted import configure_cloud_environment

configure_cloud_environment(os.environ)

from app.main import app  # noqa: E402, F401
