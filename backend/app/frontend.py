from pathlib import Path
from uuid import UUID

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles


def mount_frontend(app: FastAPI, directory: str) -> None:
    root = Path(directory).resolve()
    index = root / "index.html"
    if not index.is_file() or not (root / "assets").is_dir():
        raise RuntimeError("Built frontend files are missing")
    app.mount("/assets", StaticFiles(directory=root / "assets"), name="frontend-assets")

    async def home() -> FileResponse:
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    async def session_page(session_id: UUID) -> FileResponse:
        return await home()

    # Only known browser routes get the SPA shell. Unknown API/assets stay 404.
    app.add_api_route("/", home, methods=["GET", "HEAD"], include_in_schema=False)
    app.add_api_route(
        "/sessions/{session_id}", session_page, methods=["GET", "HEAD"], include_in_schema=False
    )
    app.add_api_route(
        "/sessions/{session_id}/dashboard",
        session_page,
        methods=["GET", "HEAD"],
        include_in_schema=False,
    )
