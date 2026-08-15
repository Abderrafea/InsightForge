from uuid import UUID

from langgraph.runtime import Runtime

from app.agent.models import SQLValidationFeedback
from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState
from app.core.exceptions import ApplicationError


async def execute_queries(state: AgentState, runtime: Runtime[AgentRuntime]) -> dict[str, object]:
    results = {}
    feedback: list[SQLValidationFeedback] = []
    connection_id = UUID(state["connection_id"])
    session_id = UUID(state["session_id"])

    for query in state["generated_queries"]:
        try:
            results[query.id] = await runtime.context.query_service.execute(
                connection_id,
                query.sql,
                session_id=session_id,
            )
        except ApplicationError as exc:
            feedback.append(SQLValidationFeedback(query_id=query.id, errors=[exc.message]))
            break

    return {
        "query_results": results if not feedback else {},
        "validation_errors": feedback,
        "all_queries_valid": not feedback,
    }
