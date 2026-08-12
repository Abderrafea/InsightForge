from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ExternalDatabaseConnectionError
from app.core.security import CredentialCipher
from app.database.connection_manager import ExternalDatabaseConnectionManager
from app.database.external_database import ExternalDatabaseCredentials
from app.models.database_connection import DatabaseConnection
from app.repositories.database_connection_repository import DatabaseConnectionRepository
from app.schemas.database_connection import (
    DatabaseConnectionCreate,
    DatabaseConnectionParameters,
)


def credentials_from_request(
    request: DatabaseConnectionParameters,
) -> ExternalDatabaseCredentials:
    return ExternalDatabaseCredentials(
        host=request.host,
        port=request.port,
        database_name=request.database_name,
        username=request.username,
        password=request.password.get_secret_value(),
        ssl_mode=request.ssl_mode.value,
    )


class DatabaseConnectionService:
    def __init__(
        self,
        db: AsyncSession,
        repository: DatabaseConnectionRepository,
        manager: ExternalDatabaseConnectionManager,
        cipher: CredentialCipher,
    ) -> None:
        self._db = db
        self._repository = repository
        self._manager = manager
        self._cipher = cipher

    async def test(self, request: DatabaseConnectionParameters) -> None:
        try:
            await self._manager.test_connection(credentials_from_request(request))
        except ExternalDatabaseConnectionError as exc:
            raise BadRequestError(
                exc.user_message, code="external_database_connection_failed"
            ) from exc

    async def create(self, request: DatabaseConnectionCreate) -> DatabaseConnection:
        await self.test(request)
        encrypted_password = self._cipher.encrypt_secret(request.password.get_secret_value())
        connection = await self._repository.create(
            name=request.name,
            host=request.host,
            port=request.port,
            database_name=request.database_name,
            username=request.username,
            encrypted_password=encrypted_password,
            ssl_mode=request.ssl_mode.value,
        )
        await self._db.commit()
        await self._db.refresh(connection)
        return connection
