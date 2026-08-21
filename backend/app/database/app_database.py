from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings, get_settings
from app.core.visitors import scope_visitor

settings = get_settings()
pool_options = {}
if settings.database_url.startswith("postgresql"):
    pool_options = {
        "pool_size": settings.app_db_pool_size,
        "max_overflow": 0,
        "pool_timeout": 10,
        "pool_recycle": 300,
        "connect_args": {"connect_timeout": 10},
    }
engine = create_async_engine(settings.database_url, pool_pre_ping=True, **pool_options)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_access_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_db_session(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_access_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[AsyncSession]:
    await scope_visitor(session, request, settings)
    try:
        yield session
    finally:
        session.info.pop("visitor_id", None)
