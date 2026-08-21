from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError
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
        owner = self._db.info.get("visitor_id")
        if owner is not None:
            count = await self._db.scalar(
                select(func.count())
                .select_from(DatabaseConnection)
                .where(DatabaseConnection.user_id == owner)
            )
            if count >= 3:
                raise BadRequestError(
                    "A visitor can save up to 3 database connections", code="visitor_limit"
                )
        connection = DatabaseConnection(
            user_id=owner,
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
        statement = select(DatabaseConnection).where(DatabaseConnection.id == connection_id)
        if "visitor_id" in self._db.info:
            statement = statement.where(DatabaseConnection.user_id == self._db.info["visitor_id"])
        return await self._db.scalar(statement)
