import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.config import get_settings
from app.database.app_database import AsyncSessionFactory
from app.services.visitor_service import purge_expired_visitors

logger = logging.getLogger(__name__)


async def cleanup() -> None:
    try:
        async with AsyncSessionFactory() as db:
            for _ in range(50):
                if not await purge_expired_visitors(db, get_settings()):
                    break
    except Exception as exc:
        # DB transport errors can include connection details; never log the payload.
        logger.warning("Visitor cleanup failed (%s)", type(exc).__name__)


async def cleanup_loop(interval: int) -> None:
    while True:
        await asyncio.sleep(interval)
        await cleanup()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    task = None
    if settings.deployment_mode in {"render", "direct"} and settings.public_visitors:
        await cleanup()
        task = asyncio.create_task(cleanup_loop(settings.visitor_cleanup_interval_seconds))
    try:
        yield
    finally:
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
