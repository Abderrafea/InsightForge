from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schema_cache import DatabaseSchemaCache


class SchemaCacheRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, connection_id: UUID) -> DatabaseSchemaCache | None:
        result = await self._db.scalars(
            select(DatabaseSchemaCache).where(
                DatabaseSchemaCache.database_connection_id == connection_id
            )
        )
        return result.one_or_none()

    async def upsert(self, connection_id: UUID, schema_json: dict[str, Any]) -> DatabaseSchemaCache:
        cache = await self.get(connection_id)
        if cache is None:
            cache = DatabaseSchemaCache(
                database_connection_id=connection_id, schema_json=schema_json
            )
            self._db.add(cache)
        else:
            cache.schema_json = schema_json
            cache.updated_at = datetime.now(UTC)
        await self._db.flush()
        return cache
