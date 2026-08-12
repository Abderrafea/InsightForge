import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("APP_DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("SECRET_ENCRYPTION_KEY", "7B1wI_gfTi94x_6crw4VBbg4FPVkudmkx5zeO0oBHho=")

from app.core.exceptions import ExternalDatabaseConnectionError  # noqa: E402
from app.database.app_database import get_db_session  # noqa: E402
from app.database.external_database import ExternalDatabaseCredentials  # noqa: E402
from app.dependencies import (  # noqa: E402
    get_external_database_manager,
    get_safe_query_executor,
    get_schema_inspector,
)
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.query.models import QueryResult  # noqa: E402
from app.schemas.schema_inspection import (  # noqa: E402
    ColumnMetadata,
    DatabaseSchemaMetadata,
    ForeignKeyMetadata,
    TableMetadata,
)


class FakeExternalDatabaseManager:
    @staticmethod
    def _validate(credentials: ExternalDatabaseCredentials) -> None:
        if credentials.password == "incorrect":
            raise ExternalDatabaseConnectionError(
                "Authentication failed. Check the database username and password."
            )
        if credentials.host == "unreachable.invalid":
            raise ExternalDatabaseConnectionError(
                "The database could not be reached. Check the host, port, SSL mode, "
                "and network access."
            )

    async def test_connection(self, credentials: ExternalDatabaseCredentials) -> None:
        self._validate(credentials)

    @asynccontextmanager
    async def connection(self, credentials: ExternalDatabaseCredentials) -> AsyncIterator[object]:
        self._validate(credentials)
        yield object()


class FakeSchemaInspector:
    def __init__(self) -> None:
        self.call_count = 0

    async def inspect(self, connection: Any) -> DatabaseSchemaMetadata:
        self.call_count += 1
        return DatabaseSchemaMetadata(
            database="demo_ecommerce",
            schemas=["public"],
            tables=[
                TableMetadata(
                    **{
                        "schema": "public",
                        "name": "customers",
                        "columns": [
                            ColumnMetadata(
                                name="id",
                                type="bigint",
                                nullable=False,
                                primary_key=True,
                            ),
                            ColumnMetadata(
                                name="name",
                                type="character varying(150)",
                                nullable=False,
                                primary_key=False,
                            ),
                        ],
                        "foreign_keys": [],
                    }
                ),
                TableMetadata(
                    **{
                        "schema": "public",
                        "name": "orders",
                        "columns": [
                            ColumnMetadata(
                                name="id",
                                type="bigint",
                                nullable=False,
                                primary_key=True,
                            ),
                            ColumnMetadata(
                                name="customer_id",
                                type="bigint",
                                nullable=False,
                                primary_key=False,
                            ),
                            ColumnMetadata(
                                name="total_amount",
                                type="numeric(12,2)",
                                nullable=False,
                                primary_key=False,
                            ),
                            ColumnMetadata(
                                name="status",
                                type="character varying(30)",
                                nullable=False,
                                primary_key=False,
                            ),
                            ColumnMetadata(
                                name="created_at",
                                type="timestamp with time zone",
                                nullable=False,
                                primary_key=False,
                            ),
                        ],
                        "foreign_keys": [
                            ForeignKeyMetadata(
                                column="customer_id",
                                references_schema="public",
                                references_table="customers",
                                references_column="id",
                            )
                        ],
                    }
                ),
            ],
        )


class FakeSafeQueryExecutor:
    def __init__(self) -> None:
        self.call_count = 0

    async def execute(self, connection_record: Any, sql: str) -> QueryResult:
        self.call_count += 1
        return QueryResult(
            columns=["status", "count"],
            rows=[{"status": "paid", "count": 42}],
            row_count=1,
            truncated=False,
            execution_time_ms=1.25,
        )


@pytest_asyncio.fixture
async def database_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def fake_manager() -> FakeExternalDatabaseManager:
    return FakeExternalDatabaseManager()


@pytest_asyncio.fixture
async def fake_inspector() -> FakeSchemaInspector:
    return FakeSchemaInspector()


@pytest_asyncio.fixture
async def fake_query_executor() -> FakeSafeQueryExecutor:
    return FakeSafeQueryExecutor()


@pytest_asyncio.fixture
async def client(
    database_session: AsyncSession,
    fake_manager: FakeExternalDatabaseManager,
    fake_inspector: FakeSchemaInspector,
    fake_query_executor: FakeSafeQueryExecutor,
) -> AsyncIterator[AsyncClient]:
    async def override_database_session() -> AsyncIterator[AsyncSession]:
        yield database_session

    app.dependency_overrides[get_db_session] = override_database_session
    app.dependency_overrides[get_external_database_manager] = lambda: fake_manager
    app.dependency_overrides[get_schema_inspector] = lambda: fake_inspector
    app.dependency_overrides[get_safe_query_executor] = lambda: fake_query_executor

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()
