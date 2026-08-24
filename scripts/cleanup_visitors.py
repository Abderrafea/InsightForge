"""Erase expired anonymous visitor data. Run hourly on the API host."""

import asyncio

from app.config import get_settings
from app.database.app_database import AsyncSessionFactory
from app.services.visitor_service import purge_expired_visitors


async def main() -> None:
    total = 0
    async with AsyncSessionFactory() as db:
        while count := await purge_expired_visitors(db, get_settings()):
            total += count
    print(f"Erased {total} expired visitor workspaces.")


if __name__ == "__main__":
    asyncio.run(main())
