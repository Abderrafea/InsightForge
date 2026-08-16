import json

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.models import SQLGenerationResult
from app.llm.exceptions import ProviderInvocationError
from app.models.agent_run import AgentRun, AgentRunStatus
from app.schemas.dashboard import (
    DashboardConfig,
    LayoutConfig,
    QueryDefinition,
    WidgetConfig,
    WidgetType,
)
from tests.conftest import FakeLLMProvider, FakeSafeQueryExecutor


async def create_attached_session(client: AsyncClient) -> str:
    session_response = await client.post("/api/sessions", json={"title": "AI dashboard"})
    connection_response = await client.post(
        "/api/database-connections",
        json={
            "name": "Ecommerce DB",
            "host": "demo-db",
            "port": 5432,
            "database_name": "demo_ecommerce",
            "username": "dashboard_reader",
            "password": "dashboard_reader_dev",
            "ssl_mode": "disable",
        },
    )
    session_id = session_response.json()["id"]
    connection_id = connection_response.json()["id"]
    attached = await client.put(f"/api/sessions/{session_id}/database-connection/{connection_id}")
    assert attached.status_code == 200
    return session_id


async def get_single_run(database_session: AsyncSession) -> AgentRun:
    runs = list(await database_session.scalars(select(AgentRun)))
    assert len(runs) == 1
    return runs[0]


async def test_agent_happy_path_persists_chat_dashboard_and_run(
    client: AsyncClient,
    database_session: AsyncSession,
    fake_llm_provider: FakeLLMProvider,
    fake_query_executor: FakeSafeQueryExecutor,
) -> None:
    session_id = await create_attached_session(client)

    response = await client.post(
        f"/api/sessions/{session_id}/agent/messages",
        json={"content": "Build me a sales dashboard"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"]["role"] == "assistant"
    assert payload["dashboard"]["title"] == "Sales Performance"
    assert len(payload["dashboard"]["widgets"]) == 2
    assert fake_query_executor.call_count == 2

    history = await client.get(f"/api/sessions/{session_id}/messages")
    assert [message["role"] for message in history.json()] == ["user", "assistant"]
    session = await client.get(f"/api/sessions/{session_id}")
    assert session.json()["dashboard"]["config_json"] == payload["dashboard"]

    run = await get_single_run(database_session)
    assert run.status == AgentRunStatus.SUCCESS
    assert run.provider == "fake"
    assert run.model == "fake-structured-model"
    assert run.retry_count == 0

    exposed_text = json.dumps(payload) + "\n".join(fake_llm_provider.prompt_payloads)
    assert "dashboard_reader_dev" not in exposed_text
    assert "encrypted_password" not in exposed_text
    assert "postgresql://" not in exposed_text


async def test_agent_retries_invalid_sql_through_graph_edge(
    client: AsyncClient,
    database_session: AsyncSession,
    fake_llm_provider: FakeLLMProvider,
    fake_query_executor: FakeSafeQueryExecutor,
) -> None:
    session_id = await create_attached_session(client)
    fake_llm_provider.sql_responses = [
        SQLGenerationResult(
            queries=[
                {
                    "id": "orders_by_status",
                    "name": "Orders by Status",
                    "sql": (
                        "SELECT o.missing_column AS status, COUNT(*) AS count "
                        "FROM orders o GROUP BY 1"
                    ),
                },
                {
                    "id": "total_orders",
                    "name": "Total Orders",
                    "sql": "SELECT COUNT(*) AS count FROM orders",
                },
            ]
        ),
        fake_llm_provider.valid_sql_response(),
    ]

    response = await client.post(
        f"/api/sessions/{session_id}/agent/messages",
        json={"content": "Build me a sales dashboard"},
    )

    assert response.status_code == 200
    assert response.json()["dashboard"] is not None
    assert fake_llm_provider.sql_call_count == 2
    assert fake_query_executor.call_count == 2
    assert any("Unknown column" in payload for payload in fake_llm_provider.prompt_payloads)
    run = await get_single_run(database_session)
    assert run.retry_count == 1
    assert run.status == AgentRunStatus.SUCCESS


async def test_agent_stops_after_retry_limit_without_execution(
    client: AsyncClient,
    database_session: AsyncSession,
    fake_llm_provider: FakeLLMProvider,
    fake_query_executor: FakeSafeQueryExecutor,
) -> None:
    session_id = await create_attached_session(client)
    invalid = SQLGenerationResult(
        queries=[
            {
                "id": "orders_by_status",
                "name": "Orders by Status",
                "sql": "SELECT * FROM missing_table",
            },
            {
                "id": "total_orders",
                "name": "Total Orders",
                "sql": "SELECT * FROM missing_table",
            },
        ]
    )
    fake_llm_provider.sql_responses = [invalid, invalid, invalid, invalid]

    response = await client.post(
        f"/api/sessions/{session_id}/agent/messages",
        json={"content": "Build me a sales dashboard"},
    )

    assert response.status_code == 200
    assert response.json()["dashboard"] is None
    assert "couldn't generate valid analytical queries" in response.json()["message"]["content"]
    assert fake_llm_provider.sql_call_count == 4
    assert fake_query_executor.call_count == 0
    run = await get_single_run(database_session)
    assert run.retry_count == 3
    assert run.status == AgentRunStatus.FAILED


async def test_agent_without_database_returns_controlled_error_and_persists_messages(
    client: AsyncClient,
    database_session: AsyncSession,
    fake_llm_provider: FakeLLMProvider,
) -> None:
    session = await client.post("/api/sessions", json={"title": "No database"})
    session_id = session.json()["id"]

    response = await client.post(
        f"/api/sessions/{session_id}/agent/messages",
        json={"content": "Build a dashboard"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "session_database_connection_required"
    assert fake_llm_provider.prompt_payloads == []
    history = await client.get(f"/api/sessions/{session_id}/messages")
    assert [message["role"] for message in history.json()] == ["user", "assistant"]
    run = await get_single_run(database_session)
    assert run.status == AgentRunStatus.FAILED


async def test_agent_rejects_dashboard_with_unknown_result_field(
    client: AsyncClient,
    database_session: AsyncSession,
    fake_llm_provider: FakeLLMProvider,
) -> None:
    session_id = await create_attached_session(client)
    queries = fake_llm_provider.valid_sql_response().queries
    fake_llm_provider.dashboard_response = DashboardConfig(
        title="Broken Dashboard",
        queries=[QueryDefinition(id=query.id, name=query.name, sql=query.sql) for query in queries],
        widgets=[
            WidgetConfig(
                id="broken_chart",
                type=WidgetType.BAR_CHART,
                title="Broken",
                query_id="orders_by_status",
                x_field="does_not_exist",
                y_fields=["count"],
            )
        ],
        layout=[LayoutConfig(widget_id="broken_chart", x=0, y=0, width=6, height=3)],
    )

    response = await client.post(
        f"/api/sessions/{session_id}/agent/messages",
        json={"content": "Build me a sales dashboard"},
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "dashboard_validation_error"
    session = await client.get(f"/api/sessions/{session_id}")
    assert session.json()["dashboard"] is None
    run = await get_single_run(database_session)
    assert run.status == AgentRunStatus.FAILED


async def test_provider_failure_is_sanitized_and_persisted(
    client: AsyncClient,
    database_session: AsyncSession,
    fake_llm_provider: FakeLLMProvider,
) -> None:
    session_id = await create_attached_session(client)
    fake_llm_provider.failure = ProviderInvocationError()

    response = await client.post(
        f"/api/sessions/{session_id}/agent/messages",
        json={"content": "Build me a sales dashboard"},
    )

    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": "ai_provider_error",
            "message": "The AI provider is temporarily unavailable",
        }
    }
    history = await client.get(f"/api/sessions/{session_id}/messages")
    assert history.json()[-1]["content"] == "The AI provider is temporarily unavailable"
    run = await get_single_run(database_session)
    assert run.status == AgentRunStatus.FAILED
