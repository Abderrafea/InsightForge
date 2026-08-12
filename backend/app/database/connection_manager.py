from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import psycopg
from psycopg import AsyncConnection

from app.core.exceptions import ExternalDatabaseConnectionError
from app.database.external_database import ExternalDatabaseCredentials


class ExternalDatabaseConnectionManager:
    def __init__(self, connect_timeout_seconds: int = 5) -> None:
        self._connect_timeout_seconds = connect_timeout_seconds

    @asynccontextmanager
    async def connection(
        self, credentials: ExternalDatabaseCredentials
    ) -> AsyncIterator[AsyncConnection[tuple[object, ...]]]:
        try:
            connection = await AsyncConnection.connect(
                host=credentials.host,
                port=credentials.port,
                dbname=credentials.database_name,
                user=credentials.username,
                password=credentials.password,
                sslmode=credentials.ssl_mode,
                connect_timeout=self._connect_timeout_seconds,
                autocommit=True,
            )
        except psycopg.errors.InvalidPassword as exc:
            raise ExternalDatabaseConnectionError(
                "Authentication failed. Check the database username and password."
            ) from exc
        except psycopg.errors.InvalidCatalogName as exc:
            raise ExternalDatabaseConnectionError(
                "The requested database does not exist or is not accessible."
            ) from exc
        except (psycopg.OperationalError, OSError, TimeoutError) as exc:
            raise ExternalDatabaseConnectionError(
                "The database could not be reached. Check the host, port, SSL mode, "
                "and network access."
            ) from exc
        except psycopg.DatabaseError as exc:
            raise ExternalDatabaseConnectionError(
                "The database rejected the connection request."
            ) from exc

        try:
            yield connection
        finally:
            if not connection.closed:
                await connection.close()

    async def test_connection(self, credentials: ExternalDatabaseCredentials) -> None:
        try:
            async with self.connection(credentials) as connection:
                await connection.execute("SELECT 1")
        except ExternalDatabaseConnectionError:
            raise
        except psycopg.DatabaseError as exc:
            raise ExternalDatabaseConnectionError(
                "The database rejected the connection request."
            ) from exc
