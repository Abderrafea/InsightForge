from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database_connection import DatabaseConnection


class DatabaseConnectionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        name: str,
        host: str,
        port: int,
        database_name: str,
        username: str,
        encrypted_password: str,
        ssl_mode: str,
    ) -> DatabaseConnection:
        connection = DatabaseConnection(
            name=name,
            database_type="postgresql",
            host=host,
            port=port,
            database_name=database_name,
            username=username,
            encrypted_password=encrypted_password,
            ssl_mode=ssl_mode,
        )
        self._db.add(connection)
        await self._db.flush()
        return connection

    async def get(self, connection_id: UUID) -> DatabaseConnection | None:
        return await self._db.get(DatabaseConnection, connection_id)
