from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.models import (
    DashboardModificationPlan,
    DashboardOperation,
    DashboardOperationType,
    LayoutPatch,
    SQLGenerationResult,
    UserIntent,
    WidgetPatch,
)
from app.models.dashboard import Dashboard, DashboardVersion
from app.schemas.dashboard import WidgetType
from tests.conftest import FakeLLMProvider, FakeSafeQueryExecutor


async def create_attached_session(client: AsyncClient, title: str = "AI dashboard") -> str:
    session_response = await client.post("/api/sessions", json={"title": title})
    connection_response = await client.post(
        "/api/database-connections",
        json={
            "name": f"{title} database",
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


async def create_dashboard(client: AsyncClient, session_id: str) -> dict:
    response = await client.post(
        f"/api/sessions/{session_id}/agent/messages",
        json={"content": "Build me a sales dashboard"},
    )
    assert response.status_code == 200
    return response.json()


async def modify_dashboard(
    client: AsyncClient,
    provider: FakeLLMProvider,
    session_id: str,
    plan: DashboardModificationPlan,
    request: str,
) -> dict:
    provider.intent = UserIntent.MODIFY_DASHBOARD
    provider.modification_plan = plan
    response = await client.post(
        f"/api/sessions/{session_id}/agent/messages",
        json={"content": request},
    )
    assert response.status_code == 200, response.text
    return response.json()


def visual_type_plan(widget_type: WidgetType) -> DashboardModificationPlan:
    return DashboardModificationPlan(
        summary=f"Changed Orders by Status to a {widget_type.value}.",
        operations=[
            DashboardOperation(
                operation=DashboardOperationType.UPDATE_WIDGET,
                target_widget_id="orders_by_status_widget",
                description="Change only the visualization type.",
            )
        ],
        widget_patches=[
            WidgetPatch(widget_id="orders_by_status_widget", type=widget_type)
        ],
    )


async def test_line_to_bar_is_ui_only_and_runs_no_sql(
    client: AsyncClient,
    fake_llm_provider: FakeLLMProvider,
    fake_query_executor: FakeSafeQueryExecutor,
) -> None:
    session_id = await create_attached_session(client)
    await create_dashboard(client, session_id)
    await modify_dashboard(
        client,
        fake_llm_provider,
        session_id,
        visual_type_plan(WidgetType.LINE_CHART),
        "Make the status chart a line chart",
    )
    sql_calls = fake_llm_provider.sql_call_count
    execution_calls = fake_query_executor.call_count

    payload = await modify_dashboard(
        client,
        fake_llm_provider,
        session_id,
        visual_type_plan(WidgetType.BAR_CHART),
        "Make this a bar chart",
    )

    assert payload["dashboard"]["widgets"][0]["type"] == "bar_chart"
    assert fake_llm_provider.sql_call_count == sql_calls
    assert fake_query_executor.call_count == execution_calls
    assert payload["change"]["affected_widgets"] == ["orders_by_status_widget"]


async def test_monthly_to_weekly_updates_only_affected_query(
    client: AsyncClient,
    fake_llm_provider: FakeLLMProvider,
    fake_query_executor: FakeSafeQueryExecutor,
) -> None:
    session_id = await create_attached_session(client)
    initial = await create_dashboard(client, session_id)
    unchanged_query = initial["dashboard"]["queries"][1]
    unchanged_widget = initial["dashboard"]["widgets"][1]
    fake_llm_provider.sql_responses = [
        SQLGenerationResult(
            queries=[
                {
                    "id": "orders_by_status",
                    "name": "Weekly Revenue",
                    "sql": (
                        "SELECT DATE_TRUNC('week', created_at) AS week, "
                        "SUM(total_amount) AS revenue FROM orders GROUP BY 1 ORDER BY 1"
                    ),
                }
            ]
        )
    ]
    plan = DashboardModificationPlan(
        summary="Changed the revenue trend from monthly to weekly.",
        operations=[
            DashboardOperation(
                operation=DashboardOperationType.UPDATE_QUERY,
                target_widget_id="orders_by_status_widget",
                target_query_id="orders_by_status",
                description="Aggregate revenue by week.",
                requires_new_query=True,
            ),
            DashboardOperation(
                operation=DashboardOperationType.UPDATE_WIDGET,
                target_widget_id="orders_by_status_widget",
                description="Use weekly revenue fields.",
            ),
        ],
        widget_patches=[
            WidgetPatch(
                widget_id="orders_by_status_widget",
                title="Weekly Revenue",
                x_field="week",
                y_fields=["revenue"],
            )
        ],
    )
    execution_calls = fake_query_executor.call_count

    payload = await modify_dashboard(
        client, fake_llm_provider, session_id, plan, "Make monthly revenue weekly"
    )

    assert fake_query_executor.call_count == execution_calls + 1
    assert "DATE_TRUNC('week'" in payload["dashboard"]["queries"][0]["sql"]
    assert payload["dashboard"]["queries"][1] == unchanged_query
    assert payload["dashboard"]["widgets"][1] == unchanged_widget


async def test_add_kpi_generates_only_its_query(
    client: AsyncClient,
    fake_llm_provider: FakeLLMProvider,
    fake_query_executor: FakeSafeQueryExecutor,
) -> None:
    session_id = await create_attached_session(client)
    await create_dashboard(client, session_id)
    fake_llm_provider.sql_responses = [
        SQLGenerationResult(
            queries=[
                {
                    "id": "average_order_value",
                    "name": "Average Order Value",
                    "sql": (
                        "SELECT AVG(total_amount) AS average_order_value FROM orders"
                    ),
                }
            ]
        )
    ]
    plan = DashboardModificationPlan(
        summary="Added average order value.",
        operations=[
            DashboardOperation(
                operation=DashboardOperationType.ADD_WIDGET,
                target_widget_id="average_order_value_widget",
                target_query_id="average_order_value",
                description="Add an average order value KPI.",
                requires_new_query=True,
            )
        ],
        widget_patches=[
            WidgetPatch(
                widget_id="average_order_value_widget",
                title="Average Order Value",
                type=WidgetType.KPI,
                query_id="average_order_value",
                value_field="average_order_value",
            )
        ],
        layout_patches=[
            LayoutPatch(widget_id="average_order_value_widget", width=3, height=2)
        ],
    )
    execution_calls = fake_query_executor.call_count

    payload = await modify_dashboard(
        client, fake_llm_provider, session_id, plan, "Add average order value"
    )

    assert fake_query_executor.call_count == execution_calls + 1
    assert len(payload["dashboard"]["queries"]) == 3
    assert payload["dashboard"]["widgets"][-1]["id"] == "average_order_value_widget"


async def test_remove_widget_also_removes_layout_and_unused_query(
    client: AsyncClient,
    fake_llm_provider: FakeLLMProvider,
    fake_query_executor: FakeSafeQueryExecutor,
) -> None:
    session_id = await create_attached_session(client)
    await create_dashboard(client, session_id)
    execution_calls = fake_query_executor.call_count
    plan = DashboardModificationPlan(
        summary="Removed the orders by status chart.",
        operations=[
            DashboardOperation(
                operation=DashboardOperationType.REMOVE_WIDGET,
                target_widget_id="orders_by_status_widget",
                target_query_id="orders_by_status",
                description="Remove the requested chart.",
            )
        ],
    )

    payload = await modify_dashboard(
        client, fake_llm_provider, session_id, plan, "Remove orders by status"
    )

    assert fake_query_executor.call_count == execution_calls
    assert {item["id"] for item in payload["dashboard"]["widgets"]} == {
        "total_orders_widget"
    }
    assert {item["id"] for item in payload["dashboard"]["queries"]} == {"total_orders"}
    assert {item["widget_id"] for item in payload["dashboard"]["layout"]} == {
        "total_orders_widget"
    }


async def test_top_ten_to_top_five_regenerates_one_query(
    client: AsyncClient,
    fake_llm_provider: FakeLLMProvider,
    fake_query_executor: FakeSafeQueryExecutor,
) -> None:
    session_id = await create_attached_session(client)
    await create_dashboard(client, session_id)
    fake_llm_provider.sql_responses = [
        SQLGenerationResult(
            queries=[
                {
                    "id": "orders_by_status",
                    "name": "Top 5 Order Statuses",
                    "sql": (
                        "SELECT status, COUNT(*) AS count FROM orders "
                        "GROUP BY status ORDER BY count DESC LIMIT 5"
                    ),
                }
            ]
        )
    ]
    plan = DashboardModificationPlan(
        summary="Limited the chart to the top 5 values.",
        operations=[
            DashboardOperation(
                operation=DashboardOperationType.UPDATE_QUERY,
                target_widget_id="orders_by_status_widget",
                target_query_id="orders_by_status",
                description="Change the limit from 10 to 5.",
                requires_new_query=True,
            )
        ],
    )
    execution_calls = fake_query_executor.call_count

    payload = await modify_dashboard(
        client, fake_llm_provider, session_id, plan, "Show only the top 5"
    )

    assert fake_query_executor.call_count == execution_calls + 1
    assert payload["dashboard"]["queries"][0]["sql"].endswith("LIMIT 5")


async def test_rename_dashboard_creates_version_without_sql(
    client: AsyncClient,
    database_session: AsyncSession,
    fake_llm_provider: FakeLLMProvider,
    fake_query_executor: FakeSafeQueryExecutor,
) -> None:
    session_id = await create_attached_session(client)
    await create_dashboard(client, session_id)
    execution_calls = fake_query_executor.call_count
    plan = DashboardModificationPlan(
        summary="Renamed the dashboard to Executive Sales.",
        operations=[
            DashboardOperation(
                operation=DashboardOperationType.UPDATE_DASHBOARD_METADATA,
                description="Rename the dashboard.",
            )
        ],
        dashboard_title="Executive Sales",
    )

    payload = await modify_dashboard(
        client, fake_llm_provider, session_id, plan, "Rename it Executive Sales"
    )

    assert payload["dashboard"]["title"] == "Executive Sales"
    assert payload["dashboard_version"] == 2
    assert fake_query_executor.call_count == execution_calls
    dashboard = await database_session.scalar(
        select(Dashboard).where(Dashboard.session_id == UUID(session_id))
    )
    assert dashboard is not None
    versions = list(
        await database_session.scalars(
            select(DashboardVersion)
            .where(DashboardVersion.dashboard_id == dashboard.id)
            .order_by(DashboardVersion.version_number)
        )
    )
    assert [version.version_number for version in versions] == [1, 2]
    assert versions[-1].created_by_message_id is not None


async def test_ambiguous_reference_asks_and_does_not_mutate(
    client: AsyncClient,
    database_session: AsyncSession,
    fake_llm_provider: FakeLLMProvider,
    fake_query_executor: FakeSafeQueryExecutor,
) -> None:
    session_id = await create_attached_session(client)
    initial = await create_dashboard(client, session_id)
    execution_calls = fake_query_executor.call_count
    sql_calls = fake_llm_provider.sql_call_count
    plan = DashboardModificationPlan(
        summary="Clarify the requested revenue chart.",
        needs_clarification=True,
        clarification_question=(
            "Which revenue chart should I remove: Monthly Revenue or Revenue by Product?"
        ),
    )

    payload = await modify_dashboard(
        client, fake_llm_provider, session_id, plan, "Remove the revenue chart"
    )

    assert payload["dashboard"] is None
    assert payload["change"] is None
    assert "Which revenue chart" in payload["message"]["content"]
    assert fake_query_executor.call_count == execution_calls
    assert fake_llm_provider.sql_call_count == sql_calls
    dashboard = await database_session.scalar(
        select(Dashboard).where(Dashboard.session_id == UUID(session_id))
    )
    assert dashboard is not None
    assert dashboard.config_json == initial["dashboard"]
    assert dashboard.current_version == 1


async def test_modifications_are_isolated_per_session(
    client: AsyncClient,
    fake_llm_provider: FakeLLMProvider,
) -> None:
    session_a = await create_attached_session(client, "Session A")
    await create_dashboard(client, session_a)
    session_b = await create_attached_session(client, "Session B")
    dashboard_b = await create_dashboard(client, session_b)
    plan = DashboardModificationPlan(
        summary="Renamed only this dashboard.",
        operations=[
            DashboardOperation(
                operation=DashboardOperationType.UPDATE_DASHBOARD_METADATA,
                description="Rename this dashboard.",
            )
        ],
        dashboard_title="Session A Executive View",
    )

    await modify_dashboard(client, fake_llm_provider, session_a, plan, "Rename this dashboard")
    session_b_details = await client.get(f"/api/sessions/{session_b}")

    assert session_b_details.json()["dashboard"]["config_json"] == dashboard_b["dashboard"]


async def test_modify_without_dashboard_returns_clean_response(
    client: AsyncClient,
    fake_llm_provider: FakeLLMProvider,
) -> None:
    session_id = await create_attached_session(client)
    fake_llm_provider.intent = UserIntent.MODIFY_DASHBOARD

    response = await client.post(
        f"/api/sessions/{session_id}/agent/messages",
        json={"content": "Make the chart weekly"},
    )

    assert response.status_code == 200
    assert response.json()["message"]["content"] == "There is no dashboard in this session yet."


async def test_dashboard_endpoint_refreshes_queries_through_safe_service(
    client: AsyncClient,
    fake_llm_provider: FakeLLMProvider,
    fake_query_executor: FakeSafeQueryExecutor,
) -> None:
    session_id = await create_attached_session(client)
    await create_dashboard(client, session_id)
    execution_calls = fake_query_executor.call_count

    response = await client.get(f"/api/sessions/{session_id}/dashboard")

    assert response.status_code == 200
    assert response.json()["dashboard"]["current_version"] == 1
    assert set(response.json()["query_results"]) == {"orders_by_status", "total_orders"}
    assert fake_query_executor.call_count == execution_calls + 2
