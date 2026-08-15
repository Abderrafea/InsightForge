from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.dashboard import DashboardConfig, WidgetType
from app.schemas.message import MessageRead


class UserIntent(StrEnum):
    CREATE_DASHBOARD = "CREATE_DASHBOARD"
    MODIFY_DASHBOARD = "MODIFY_DASHBOARD"
    ASK_DATA_QUESTION = "ASK_DATA_QUESTION"


class DashboardOperationType(StrEnum):
    ADD_WIDGET = "ADD_WIDGET"
    REMOVE_WIDGET = "REMOVE_WIDGET"
    UPDATE_WIDGET = "UPDATE_WIDGET"
    UPDATE_QUERY = "UPDATE_QUERY"
    UPDATE_LAYOUT = "UPDATE_LAYOUT"
    UPDATE_DASHBOARD_METADATA = "UPDATE_DASHBOARD_METADATA"


class ChangeClassification(StrEnum):
    UI_ONLY = "UI_ONLY"
    DATA_QUERY_REQUIRED = "DATA_QUERY_REQUIRED"
    MIXED = "MIXED"


class IntentResult(BaseModel):
    intent: UserIntent
    normalized_request: str = Field(min_length=1, max_length=2_000)


class MetricPlan(BaseModel):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1_000)
    visualization: Literal[
        "kpi",
        "line_chart",
        "bar_chart",
        "pie_chart",
        "area_chart",
        "table",
    ]
    business_question: str = Field(min_length=1, max_length=1_000)


class DashboardPlan(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1, max_length=1_000)
    metrics: list[MetricPlan] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def metric_ids_are_unique(self) -> "DashboardPlan":
        metric_ids = [metric.id for metric in self.metrics]
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("Dashboard metric IDs must be unique")
        return self


class GeneratedQuery(BaseModel):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=255)
    sql: str = Field(min_length=1, max_length=100_000)


class SQLGenerationResult(BaseModel):
    queries: list[GeneratedQuery] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def query_ids_are_unique(self) -> "SQLGenerationResult":
        query_ids = [query.id for query in self.queries]
        if len(query_ids) != len(set(query_ids)):
            raise ValueError("Generated query IDs must be unique")
        return self


class SQLValidationFeedback(BaseModel):
    query_id: str
    errors: list[str]


class DashboardOperation(BaseModel):
    operation: DashboardOperationType
    target_widget_id: str | None = Field(default=None, max_length=100)
    target_query_id: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=1, max_length=1_000)
    requires_new_query: bool = False


class WidgetPatch(BaseModel):
    widget_id: str = Field(min_length=1, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    type: WidgetType | None = None
    query_id: str | None = Field(default=None, min_length=1, max_length=100)
    x_field: str | None = Field(default=None, min_length=1, max_length=100)
    y_fields: list[str] | None = None
    value_field: str | None = Field(default=None, min_length=1, max_length=100)
    options: dict[str, object] | None = None


class QueryPatch(BaseModel):
    query_id: str = Field(min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sql: str | None = Field(default=None, min_length=1, max_length=100_000)


class LayoutPatch(BaseModel):
    widget_id: str = Field(min_length=1, max_length=100)
    x: int | None = Field(default=None, ge=0)
    y: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, gt=0, le=12)
    height: int | None = Field(default=None, gt=0)


class DashboardModificationPlan(BaseModel):
    summary: str = Field(min_length=1, max_length=1_000)
    operations: list[DashboardOperation] = Field(default_factory=list, max_length=20)
    widget_patches: list[WidgetPatch] = Field(default_factory=list, max_length=20)
    query_patches: list[QueryPatch] = Field(default_factory=list, max_length=20)
    layout_patches: list[LayoutPatch] = Field(default_factory=list, max_length=20)
    dashboard_title: str | None = Field(default=None, min_length=1, max_length=255)
    needs_clarification: bool = False
    clarification_question: str | None = Field(default=None, min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def clarification_is_complete(self) -> "DashboardModificationPlan":
        if self.needs_clarification and not self.clarification_question:
            raise ValueError("A clarification question is required")
        return self


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class AgentMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message content must not be blank")
        return value


class DashboardChange(BaseModel):
    type: UserIntent
    affected_widgets: list[str] = Field(default_factory=list)
    summary: str | None = None


class AgentMessageResponse(BaseModel):
    message: MessageRead
    dashboard: DashboardConfig | None
    dashboard_version: int | None = None
    change: DashboardChange | None = None


class AgentResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    final_response: str
    dashboard_config: DashboardConfig | None
    retry_count: int
    dashboard_changed: bool = False
    affected_widget_ids: list[str] = Field(default_factory=list)
    change_summary: str | None = None
