import asyncio
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("APP_DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("SECRET_ENCRYPTION_KEY", "7B1wI_gfTi94x_6crw4VBbg4FPVkudmkx5zeO0oBHho=")

from app.agent.models import (  # noqa: E402
    DashboardModificationPlan,
    DashboardPlan,
    IntentResult,
    MetricPlan,
    SQLGenerationResult,
    UserIntent,
)
from app.core.exceptions import ExternalDatabaseConnectionError  # noqa: E402
from app.database.app_database import get_db_session  # noqa: E402
from app.database.external_database import ExternalDatabaseCredentials  # noqa: E402
from app.dependencies import (  # noqa: E402
    get_external_database_manager,
    get_llm_provider,
    get_safe_query_executor,
    get_schema_inspector,
)
from app.llm.capabilities import LLMCapabilities  # noqa: E402
from app.llm.exceptions import ProviderInvocationError  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.query.models import QueryResult  # noqa: E402
from app.schemas.dashboard import (  # noqa: E402
    DashboardConfig,
    LayoutConfig,
    QueryDefinition,
    WidgetConfig,
    WidgetType,
)
from app.schemas.schema_inspection import (  # noqa: E402
    ColumnMetadata,
    DatabaseSchemaMetadata,
    ForeignKeyMetadata,
    TableMetadata,
)


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    # Psycopg async connections require a selector loop on Windows.
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


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
        lowered = sql.lower()
        if "average_order_value" in lowered:
            return QueryResult(
                columns=["average_order_value"],
                rows=[{"average_order_value": 84.5}],
                row_count=1,
                truncated=False,
                execution_time_ms=1.25,
            )
        if "date_trunc('week'" in lowered:
            return QueryResult(
                columns=["week", "revenue"],
                rows=[{"week": "2026-08-10", "revenue": 840.0}],
                row_count=1,
                truncated=False,
                execution_time_ms=1.25,
            )
        return QueryResult(
            columns=["status", "count"],
            rows=[{"status": "paid", "count": 42}],
            row_count=1,
            truncated=False,
            execution_time_ms=1.25,
        )


class FakeLLMProvider:
    name = "fake"
    model = "fake-structured-model"
    capabilities = LLMCapabilities(
        structured_output=True,
        tool_calling=True,
        json_mode=True,
    )

    def __init__(self) -> None:
        self.prompt_payloads: list[str] = []
        self.sql_responses: list[SQLGenerationResult] = []
        self.sql_call_count = 0
        self.dashboard_response: DashboardConfig | None = None
        self.failure: ProviderInvocationError | None = None
        self.intent = UserIntent.CREATE_DASHBOARD
        self.modification_plan: DashboardModificationPlan | None = None

    async def invoke(self, messages: Any) -> Any:
        raise AssertionError("The Phase 3 graph should use structured outputs")

    async def structured_output(self, messages: Any, schema: type[Any]) -> Any:
        self.prompt_payloads.extend(str(message.content) for message in messages)
        if self.failure is not None:
            raise self.failure
        if schema is IntentResult:
            return IntentResult(
                intent=self.intent,
                normalized_request=(
                    "Modify the current dashboard"
                    if self.intent == UserIntent.MODIFY_DASHBOARD
                    else "Build a sales performance dashboard"
                ),
            )
        if schema is DashboardModificationPlan:
            if self.modification_plan is None:
                raise AssertionError("A modification plan was not configured for this test")
            return self.modification_plan
        if schema is DashboardPlan:
            return DashboardPlan(
                title="Sales Performance",
                summary="Order volume and status overview",
                metrics=[
                    MetricPlan(
                        id="orders_by_status",
                        title="Orders by Status",
                        visualization="bar_chart",
                        business_question="How many orders are in each status?",
                    ),
                    MetricPlan(
                        id="total_orders",
                        title="Total Orders",
                        visualization="kpi",
                        business_question="How many orders are there?",
                    ),
                ],
            )
        if schema is SQLGenerationResult:
            self.sql_call_count += 1
            if self.sql_responses:
                return self.sql_responses.pop(0)
            return self.valid_sql_response()
        if schema is DashboardConfig:
            if self.dashboard_response is not None:
                return self.dashboard_response
            queries = self.valid_sql_response().queries
            return DashboardConfig(
                title="Sales Performance",
                queries=[
                    QueryDefinition(id=query.id, name=query.name, sql=query.sql)
                    for query in queries
                ],
                widgets=[
                    WidgetConfig(
                        id="orders_by_status_widget",
                        type=WidgetType.BAR_CHART,
                        title="Orders by Status",
                        query_id="orders_by_status",
                        x_field="status",
                        y_fields=["count"],
                    ),
                    WidgetConfig(
                        id="total_orders_widget",
                        type=WidgetType.KPI,
                        title="Total Orders",
                        query_id="total_orders",
                        value_field="count",
                    ),
                ],
                layout=[
                    LayoutConfig(widget_id="orders_by_status_widget", x=0, y=0, width=6, height=3),
                    LayoutConfig(widget_id="total_orders_widget", x=6, y=0, width=3, height=2),
                ],
            )
        raise AssertionError(f"Unexpected structured schema: {schema}")

    @staticmethod
    def valid_sql_response() -> SQLGenerationResult:
        return SQLGenerationResult(
            queries=[
                {
                    "id": "orders_by_status",
                    "name": "Orders by Status",
                    "sql": (
                        "SELECT status, COUNT(*) AS count FROM orders "
                        "GROUP BY status ORDER BY status"
                    ),
                },
                {
                    "id": "total_orders",
                    "name": "Total Orders",
                    "sql": "SELECT COUNT(*) AS count FROM orders",
                },
            ]
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
async def fake_llm_provider() -> FakeLLMProvider:
    return FakeLLMProvider()


@pytest_asyncio.fixture
async def client(
    database_session: AsyncSession,
    fake_manager: FakeExternalDatabaseManager,
    fake_inspector: FakeSchemaInspector,
    fake_query_executor: FakeSafeQueryExecutor,
    fake_llm_provider: FakeLLMProvider,
) -> AsyncIterator[AsyncClient]:
    async def override_database_session() -> AsyncIterator[AsyncSession]:
        yield database_session

    app.dependency_overrides[get_db_session] = override_database_session
    app.dependency_overrides[get_external_database_manager] = lambda: fake_manager
    app.dependency_overrides[get_schema_inspector] = lambda: fake_inspector
    app.dependency_overrides[get_safe_query_executor] = lambda: fake_query_executor
    app.dependency_overrides[get_llm_provider] = lambda: fake_llm_provider

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()
