from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.query.models import QueryResult


class WidgetType(StrEnum):
    KPI = "kpi"
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    AREA_CHART = "area_chart"
    TABLE = "table"


class QueryDefinition(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    sql: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class WidgetConfig(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    type: WidgetType
    title: str = Field(min_length=1, max_length=255)
    query_id: str | None = None
    x_field: str | None = None
    y_fields: list[str] = Field(default_factory=list)
    value_field: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class LayoutConfig(BaseModel):
    widget_id: str
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class DashboardConfig(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    queries: list[QueryDefinition] = Field(default_factory=list)
    widgets: list[WidgetConfig] = Field(default_factory=list)
    layout: list[LayoutConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "DashboardConfig":
        query_ids = [query.id for query in self.queries]
        widget_ids = [widget.id for widget in self.widgets]
        layout_widget_ids = [item.widget_id for item in self.layout]
        if len(query_ids) != len(set(query_ids)):
            raise ValueError("Dashboard query IDs must be unique")
        if len(widget_ids) != len(set(widget_ids)):
            raise ValueError("Dashboard widget IDs must be unique")
        if len(layout_widget_ids) != len(set(layout_widget_ids)):
            raise ValueError("Each widget may appear in the layout only once")

        known_queries = set(query_ids)
        known_widgets = set(widget_ids)
        for widget in self.widgets:
            if not widget.query_id or widget.query_id not in known_queries:
                raise ValueError(f"Widget '{widget.id}' references an unknown query")
            if widget.type == WidgetType.KPI and not widget.value_field:
                raise ValueError(f"KPI widget '{widget.id}' requires value_field")
            if widget.type in {
                WidgetType.LINE_CHART,
                WidgetType.BAR_CHART,
                WidgetType.PIE_CHART,
                WidgetType.AREA_CHART,
            } and (not widget.x_field or not widget.y_fields):
                raise ValueError(f"Chart widget '{widget.id}' requires x_field and y_fields")

        unknown_layout_widgets = set(layout_widget_ids) - known_widgets
        if unknown_layout_widgets:
            raise ValueError("Dashboard layout references an unknown widget")
        if known_widgets != set(layout_widget_ids):
            raise ValueError("Every dashboard widget must have one layout entry")

        for item in self.layout:
            if item.x + item.width > 12:
                raise ValueError("Dashboard layout items must fit within a 12-column grid")
        for index, left in enumerate(self.layout):
            for right in self.layout[index + 1 :]:
                separated = (
                    left.x + left.width <= right.x
                    or right.x + right.width <= left.x
                    or left.y + left.height <= right.y
                    or right.y + right.height <= left.y
                )
                if not separated:
                    raise ValueError("Dashboard layout items may not overlap")
        return self


class DashboardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    title: str
    config_json: DashboardConfig
    current_version: int
    last_modified_by_message_id: UUID | None
    created_at: datetime
    updated_at: datetime


class DashboardVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dashboard_id: UUID
    version_number: int
    config_json: DashboardConfig
    created_at: datetime
    created_by_message_id: UUID | None


class DashboardDataRead(BaseModel):
    dashboard: DashboardRead
    query_results: dict[str, QueryResult]
