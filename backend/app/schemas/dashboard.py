from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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


class DashboardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    title: str
    config_json: DashboardConfig
    created_at: datetime
    updated_at: datetime
