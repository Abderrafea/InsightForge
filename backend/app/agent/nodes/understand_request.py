from langgraph.runtime import Runtime

from app.agent.models import IntentResult
from app.agent.prompts.understand_request import build_understand_messages
from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState


async def understand_request(
    state: AgentState, runtime: Runtime[AgentRuntime]
) -> dict[str, object]:
    result = await runtime.context.provider.structured_output(
        build_understand_messages(
            state["user_request"],
            state.get("messages", []),
            state.get("current_dashboard"),
        ),
        IntentResult,
    )
    return {
        "intent": result.intent,
        "normalized_request": result.normalized_request,
    }
