from uuid import UUID

from langgraph.runtime import Runtime

from app.agent.models import SQLValidationFeedback
from app.agent.nodes.classify_change import affected_query_ids
from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState


async def validate_modified_sql(
    state: AgentState, runtime: Runtime[AgentRuntime]
) -> dict[str, object]:
    feedback: list[SQLValidationFeedback] = []
    expected_ids = set(affected_query_ids(state))
    generated_ids = {query.id for query in state["generated_queries"]}
    for missing_id in sorted(expected_ids - generated_ids):
        feedback.append(
            SQLValidationFeedback(
                query_id=missing_id,
                errors=["No SQL query was generated for this dashboard change"],
            )
        )
    for unexpected_id in sorted(generated_ids - expected_ids):
        feedback.append(
            SQLValidationFeedback(
                query_id=unexpected_id,
                errors=["This query is not affected by the dashboard change"],
            )
        )

    connection_id = UUID(state["connection_id"])
    for query in state["generated_queries"]:
        validation = await runtime.context.query_service.validate(connection_id, query.sql)
        if not validation.valid:
            feedback.append(SQLValidationFeedback(query_id=query.id, errors=validation.errors))
    return {"validation_errors": feedback, "all_queries_valid": not feedback}
