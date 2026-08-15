import json

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.schemas.dashboard import DashboardConfig

SYSTEM_PROMPT = """You are an analytics dashboard planner. Plan focused business metrics using
only the supplied PostgreSQL schema. Do not write SQL. Choose supported visualizations: kpi,
line_chart, bar_chart, pie_chart, area_chart, or table. Use stable snake_case metric IDs. Prefer
4-6 useful widgets for broad requests and return only the requested structured output."""


def build_planner_messages(
    normalized_request: str,
    schema_text: str,
    current_dashboard: DashboardConfig | None,
    min_widgets: int,
    max_widgets: int,
) -> list[BaseMessage]:
    payload = {
        "request": normalized_request,
        "schema": schema_text,
        "widget_bounds": {"minimum": min_widgets, "maximum": max_widgets},
        "current_dashboard": current_dashboard.model_dump(mode="json")
        if current_dashboard
        else None,
    }
    return [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=json.dumps(payload))]
