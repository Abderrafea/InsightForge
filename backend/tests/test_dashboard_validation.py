import pytest
from pydantic import ValidationError

from app.agent.dashboard_validation import validate_generated_dashboard
from app.agent.exceptions import DashboardValidationError
from app.agent.models import GeneratedQuery
from app.query.models import QueryResult
from app.schemas.dashboard import (
    DashboardConfig,
    LayoutConfig,
    QueryDefinition,
    WidgetConfig,
    WidgetType,
)


def test_dashboard_model_rejects_unsupported_widget_type() -> None:
    with pytest.raises(ValidationError):
        WidgetConfig(id="map", type="map", title="Map", query_id="q")  # type: ignore[arg-type]


def test_dashboard_model_rejects_duplicate_widget_ids() -> None:
    with pytest.raises(ValidationError, match="widget IDs must be unique"):
        DashboardConfig(
            title="Invalid",
            queries=[QueryDefinition(id="q", name="Query", sql="SELECT 1 AS value")],
            widgets=[
                WidgetConfig(
                    id="duplicate",
                    type=WidgetType.KPI,
                    title="One",
                    query_id="q",
                    value_field="value",
                ),
                WidgetConfig(
                    id="duplicate",
                    type=WidgetType.KPI,
                    title="Two",
                    query_id="q",
                    value_field="value",
                ),
            ],
            layout=[LayoutConfig(widget_id="duplicate", x=0, y=0, width=3, height=2)],
        )


def test_dashboard_model_rejects_missing_query_reference() -> None:
    with pytest.raises(ValidationError, match="unknown query"):
        DashboardConfig(
            title="Invalid",
            widgets=[
                WidgetConfig(
                    id="kpi",
                    type=WidgetType.KPI,
                    title="KPI",
                    query_id="missing",
                    value_field="value",
                )
            ],
            layout=[LayoutConfig(widget_id="kpi", x=0, y=0, width=3, height=2)],
        )


def test_generated_dashboard_rejects_unknown_result_fields() -> None:
    query = GeneratedQuery(id="q", name="Query", sql="SELECT 1 AS value")
    dashboard = DashboardConfig(
        title="Invalid Fields",
        queries=[QueryDefinition(id="q", name="Query", sql=query.sql)],
        widgets=[
            WidgetConfig(
                id="chart",
                type=WidgetType.BAR_CHART,
                title="Chart",
                query_id="q",
                x_field="missing",
                y_fields=["value"],
            )
        ],
        layout=[LayoutConfig(widget_id="chart", x=0, y=0, width=6, height=3)],
    )
    result = QueryResult(
        columns=["value"],
        rows=[{"value": 1}],
        row_count=1,
        truncated=False,
        execution_time_ms=1,
    )

    with pytest.raises(DashboardValidationError, match="unavailable result fields"):
        validate_generated_dashboard(dashboard, [query], {"q": result})
