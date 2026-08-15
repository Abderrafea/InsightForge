import json

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.agent.models import DashboardPlan, GeneratedQuery
from app.query.models import QueryResult

SYSTEM_PROMPT = """You build a structured dashboard configuration, never UI code. Use every
validated query exactly as supplied and do not alter SQL. Create unique widget IDs and one layout
entry per widget. KPI widgets need value_field. Chart widgets need x_field and y_fields. Reference
only columns present in the supplied result metadata. Return only the requested structured
output."""


def build_dashboard_messages(
    plan: DashboardPlan,
    queries: list[GeneratedQuery],
    results: dict[str, QueryResult],
    sample_rows: int,
) -> list[BaseMessage]:
    result_context = {
        query_id: {
            "columns": result.columns,
            "sample_rows": result.rows[:sample_rows],
            "row_count": result.row_count,
            "truncated": result.truncated,
        }
        for query_id, result in results.items()
    }
    payload = {
        "dashboard_plan": plan.model_dump(mode="json"),
        "validated_queries": [query.model_dump(mode="json") for query in queries],
        "query_results": result_context,
    }
    return [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(payload, ensure_ascii=True)),
    ]
