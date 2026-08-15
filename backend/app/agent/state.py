from typing import TypedDict

from app.agent.models import (
    ChangeClassification,
    ConversationMessage,
    DashboardModificationPlan,
    DashboardPlan,
    GeneratedQuery,
    SQLValidationFeedback,
    UserIntent,
)
from app.query.models import QueryResult
from app.schemas.dashboard import DashboardConfig
from app.schemas.schema_inspection import DatabaseSchemaMetadata


class AgentState(TypedDict, total=False):
    session_id: str
    messages: list[ConversationMessage]
    user_request: str
    normalized_request: str
    intent: UserIntent
    connection_id: str
    database_schema: DatabaseSchemaMetadata
    compact_schema: str
    current_dashboard: DashboardConfig | None
    modification_plan: DashboardModificationPlan
    change_classification: ChangeClassification
    needs_clarification: bool
    clarification_question: str | None
    affected_widget_ids: list[str]
    dashboard_changed: bool
    dashboard_plan: DashboardPlan
    generated_queries: list[GeneratedQuery]
    validation_errors: list[SQLValidationFeedback]
    query_results: dict[str, QueryResult]
    retry_count: int
    all_queries_valid: bool
    dashboard_config: DashboardConfig | None
    final_response: str | None
    error: str | None
