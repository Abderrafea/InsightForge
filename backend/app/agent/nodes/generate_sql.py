from langgraph.runtime import Runtime

from app.agent.models import SQLGenerationResult
from app.agent.prompts.sql_generator import build_sql_messages
from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState


async def generate_sql(state: AgentState, runtime: Runtime[AgentRuntime]) -> dict[str, object]:
    is_retry = bool(state.get("validation_errors"))
    result = await runtime.context.provider.structured_output(
        build_sql_messages(
            state["compact_schema"],
            state["dashboard_plan"],
            state.get("validation_errors", []),
        ),
        SQLGenerationResult,
    )
    return {
        "generated_queries": result.queries,
        "retry_count": state.get("retry_count", 0) + (1 if is_retry else 0),
        "validation_errors": [],
        "all_queries_valid": False,
        "query_results": {},
    }
