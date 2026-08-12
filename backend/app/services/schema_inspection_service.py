from uuid import UUID

import psycopg
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ExternalDatabaseConnectionError, NotFoundError
from app.core.security import CredentialCipher
from app.database.connection_manager import ExternalDatabaseConnectionManager
from app.database.external_database import ExternalDatabaseCredentials
from app.database.schema_inspector import PostgreSQLSchemaInspector
from app.repositories.database_connection_repository import DatabaseConnectionRepository
from app.repositories.schema_cache_repository import SchemaCacheRepository
from app.schemas.schema_inspection import DatabaseSchemaMetadata


class SchemaInspectionService:
    def __init__(
        self,
        db: AsyncSession,
        connections: DatabaseConnectionRepository,
        cache: SchemaCacheRepository,
        manager: ExternalDatabaseConnectionManager,
        inspector: PostgreSQLSchemaInspector,
        cipher: CredentialCipher,
    ) -> None:
        self._db = db
        self._connections = connections
        self._cache = cache
        self._manager = manager
        self._inspector = inspector
        self._cipher = cipher

    async def get_schema(
        self, connection_id: UUID, *, refresh: bool = False
    ) -> DatabaseSchemaMetadata:
        connection_record = await self._connections.get(connection_id)
        if connection_record is None:
            raise NotFoundError("Database connection")

        if not refresh:
            cached = await self._cache.get(connection_id)
            if cached is not None:
                return DatabaseSchemaMetadata.model_validate(cached.schema_json)

        credentials = ExternalDatabaseCredentials(
            host=connection_record.host,
            port=connection_record.port,
            database_name=connection_record.database_name,
            username=connection_record.username,
            password=self._cipher.decrypt_secret(connection_record.encrypted_password),
            ssl_mode=connection_record.ssl_mode,
        )
        try:
            async with self._manager.connection(credentials) as external_connection:
                schema = await self._inspector.inspect(external_connection)
        except ExternalDatabaseConnectionError as exc:
            raise BadRequestError(
                exc.user_message, code="external_database_connection_failed"
            ) from exc
        except psycopg.DatabaseError as exc:
            raise BadRequestError(
                "Schema metadata could not be inspected",
                code="schema_inspection_failed",
            ) from exc

        await self._cache.upsert(connection_id, schema.model_dump(mode="json", by_alias=True))
        await self._db.commit()
        return schema
