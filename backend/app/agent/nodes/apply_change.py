from collections.abc import Iterable
from typing import Any

from app.agent.exceptions import DashboardValidationError
from app.agent.models import DashboardOperationType
from app.agent.state import AgentState
from app.schemas.dashboard import DashboardConfig, WidgetType


def _overlaps(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return not (
        left["x"] + left["width"] <= right["x"]
        or right["x"] + right["width"] <= left["x"]
        or left["y"] + left["height"] <= right["y"]
        or right["y"] + right["height"] <= left["y"]
    )


def normalize_layout(
    widget_ids: Iterable[str], layout: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    source = {item["widget_id"]: item for item in layout}
    normalized: list[dict[str, Any]] = []
    for widget_id in widget_ids:
        candidate = dict(
            source.get(
                widget_id,
                {"widget_id": widget_id, "x": 0, "y": 0, "width": 6, "height": 3},
            )
        )
        candidate["widget_id"] = widget_id
        candidate["width"] = min(max(int(candidate.get("width", 6)), 1), 12)
        candidate["height"] = max(int(candidate.get("height", 3)), 1)
        candidate["x"] = min(max(int(candidate.get("x", 0)), 0), 12 - candidate["width"])
        candidate["y"] = max(int(candidate.get("y", 0)), 0)
        if any(_overlaps(candidate, placed) for placed in normalized):
            candidate["x"] = 0
            candidate["y"] = max(
                (placed["y"] + placed["height"] for placed in normalized), default=0
            )
        normalized.append(candidate)
    return normalized


def _required_fields(widget: dict[str, Any]) -> set[str]:
    fields = set(widget.get("y_fields") or [])
    if widget.get("x_field"):
        fields.add(widget["x_field"])
    if widget.get("value_field"):
        fields.add(widget["value_field"])
    return fields


async def apply_change(state: AgentState) -> dict[str, object]:
    current = state.get("current_dashboard")
    if current is None:
        return {
            "dashboard_config": None,
            "dashboard_changed": False,
            "final_response": "There is no dashboard in this session yet.",
        }
    plan = state["modification_plan"]
    config = current.model_dump(mode="python")
    queries = {query["id"]: query for query in config["queries"]}
    widgets = {widget["id"]: widget for widget in config["widgets"]}
    layout = {item["widget_id"]: item for item in config["layout"]}
    affected_widgets = {
        operation.target_widget_id
        for operation in plan.operations
        if operation.target_widget_id is not None
    }
    add_widget_ids = {
        operation.target_widget_id
        for operation in plan.operations
        if operation.operation == DashboardOperationType.ADD_WIDGET
        and operation.target_widget_id
    }

    for operation in plan.operations:
        if operation.operation == DashboardOperationType.REMOVE_WIDGET:
            widget_id = operation.target_widget_id
            if not widget_id or widget_id not in widgets:
                raise DashboardValidationError("The widget selected for removal does not exist")
            widgets.pop(widget_id)
            layout.pop(widget_id, None)
            affected_widgets.add(widget_id)

    for generated in state.get("generated_queries", []):
        existing = queries.get(generated.id, {})
        queries[generated.id] = {
            "id": generated.id,
            "name": generated.name,
            "sql": generated.sql,
            "parameters": existing.get("parameters", {}),
        }

    for patch in plan.query_patches:
        query = queries.get(patch.query_id)
        generated_ids = {item.id for item in state.get("generated_queries", [])}
        if query is None and patch.query_id not in generated_ids:
            raise DashboardValidationError("A query patch references an unknown query")
        if query is not None and patch.name is not None:
            query["name"] = patch.name

    for patch in plan.widget_patches:
        widget = widgets.get(patch.widget_id)
        if widget is None:
            if patch.widget_id not in add_widget_ids:
                raise DashboardValidationError("A widget patch references an unknown widget")
            widget = {
                "id": patch.widget_id,
                "type": patch.type.value if patch.type else None,
                "title": patch.title,
                "query_id": patch.query_id,
                "x_field": patch.x_field,
                "y_fields": patch.y_fields or [],
                "value_field": patch.value_field,
                "options": patch.options or {},
            }
            widgets[patch.widget_id] = widget
        else:
            for field in (
                "title",
                "query_id",
                "x_field",
                "y_fields",
                "value_field",
                "options",
            ):
                value = getattr(patch, field)
                if value is not None:
                    widget[field] = value
            if patch.type is not None:
                widget["type"] = patch.type.value

        widget_type = WidgetType(widget["type"]) if widget.get("type") else None
        if widget_type == WidgetType.KPI:
            widget["x_field"] = None
            widget["y_fields"] = []
        elif widget_type in {
            WidgetType.LINE_CHART,
            WidgetType.BAR_CHART,
            WidgetType.PIE_CHART,
            WidgetType.AREA_CHART,
        }:
            widget["value_field"] = None
        elif widget_type == WidgetType.TABLE:
            widget["x_field"] = None
            widget["y_fields"] = []
            widget["value_field"] = None
        affected_widgets.add(patch.widget_id)

    for patch in plan.layout_patches:
        if patch.widget_id not in widgets:
            raise DashboardValidationError("A layout patch references an unknown widget")
        item = layout.setdefault(
            patch.widget_id,
            {"widget_id": patch.widget_id, "x": 0, "y": 0, "width": 6, "height": 3},
        )
        for field in ("x", "y", "width", "height"):
            value = getattr(patch, field)
            if value is not None:
                item[field] = value
        affected_widgets.add(patch.widget_id)

    if plan.dashboard_title is not None:
        config["title"] = plan.dashboard_title

    referenced_queries = {widget.get("query_id") for widget in widgets.values()}
    queries = {
        query_id: query
        for query_id, query in queries.items()
        if query_id in referenced_queries
    }
    widget_ids = list(widgets)
    normalized_layout = normalize_layout(widget_ids, list(layout.values()))
    candidate = DashboardConfig.model_validate(
        {
            "title": config["title"],
            "queries": list(queries.values()),
            "widgets": list(widgets.values()),
            "layout": normalized_layout,
        }
    )

    for widget_id in affected_widgets:
        widget = widgets.get(widget_id)
        if widget is None or not widget.get("query_id"):
            continue
        result = state.get("query_results", {}).get(widget["query_id"])
        if result is not None and not _required_fields(widget).issubset(result.columns):
            raise DashboardValidationError(
                f"Widget '{widget_id}' references unavailable result fields"
            )

    return {
        "dashboard_config": candidate,
        "dashboard_changed": True,
        "affected_widget_ids": sorted(affected_widgets),
        "final_response": plan.summary,
        "error": None,
    }


async def validate_modified_dashboard(state: AgentState) -> dict[str, object]:
    dashboard = state.get("dashboard_config")
    if dashboard is None:
        raise DashboardValidationError("The dashboard change produced no dashboard config")
    return {"dashboard_config": DashboardConfig.model_validate(dashboard.model_dump())}
