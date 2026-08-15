import json

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.agent.models import DashboardPlan, SQLValidationFeedback

SYSTEM_PROMPT = """You generate PostgreSQL analytical SQL from a metric plan. Generate exactly one
SELECT-only statement per metric, use only supplied tables and columns, avoid system schemas and
SELECT *, use explicit chart-friendly aliases, and never modify data. Query IDs must match metric
IDs. Correct every supplied validation error. Return only the requested structured output.
Validation and read-only database controls remain authoritative regardless of these instructions."""


def build_sql_messages(
    schema_text: str,
    plan: DashboardPlan,
    validation_errors: list[SQLValidationFeedback],
) -> list[BaseMessage]:
    payload = {
        "schema": schema_text,
        "dashboard_plan": plan.model_dump(mode="json"),
        "validation_feedback": [error.model_dump(mode="json") for error in validation_errors],
    }
    return [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=json.dumps(payload))]
