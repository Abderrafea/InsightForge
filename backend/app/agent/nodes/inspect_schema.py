from uuid import UUID

from langgraph.runtime import Runtime

from app.agent.runtime import AgentRuntime
from app.agent.schema_context import compact_schema
from app.agent.state import AgentState


async def inspect_schema(state: AgentState, runtime: Runtime[AgentRuntime]) -> dict[str, object]:
    schema = await runtime.context.schema_service.get_schema(UUID(state["connection_id"]))
    return {"database_schema": schema, "compact_schema": compact_schema(schema)}
