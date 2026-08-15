import json

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.agent.models import DashboardModificationPlan, SQLValidationFeedback
from app.schemas.dashboard import DashboardConfig

SYSTEM_PROMPT = """Generate PostgreSQL SELECT-only analytical SQL for exactly the affected query
IDs listed in the modification plan. Do not return unchanged dashboard queries. Preserve an
existing query ID when modifying it. Use only supplied tables and columns, avoid system schemas
and SELECT *, use explicit visualization-friendly aliases, and correct all validation feedback.
Never modify data. Return only the requested structured output. Validation and read-only database
controls remain authoritative."""


def build_change_sql_messages(
    schema_text: str,
    current_dashboard: DashboardConfig,
    plan: DashboardModificationPlan,
    affected_query_ids: list[str],
    validation_errors: list[SQLValidationFeedback],
) -> list[BaseMessage]:
    current_queries = {
        query.id: query.model_dump(mode="json")
        for query in current_dashboard.queries
        if query.id in affected_query_ids
    }
    payload = {
        "schema": schema_text,
        "modification_plan": plan.model_dump(mode="json"),
        "affected_query_ids": affected_query_ids,
        "current_affected_queries": current_queries,
        "validation_feedback": [error.model_dump(mode="json") for error in validation_errors],
    }
    return [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=json.dumps(payload))]
