from langgraph.runtime import Runtime

from app.agent.exceptions import DashboardValidationError
from app.agent.models import DashboardPlan
from app.agent.prompts.dashboard_planner import build_planner_messages
from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState


async def plan_dashboard(state: AgentState, runtime: Runtime[AgentRuntime]) -> dict[str, object]:
    result = await runtime.context.provider.structured_output(
        build_planner_messages(
            state["normalized_request"],
            state["compact_schema"],
            state.get("current_dashboard"),
            runtime.context.settings.agent_min_widgets,
            runtime.context.settings.agent_max_widgets,
        ),
        DashboardPlan,
    )
    if not (
        runtime.context.settings.agent_min_widgets
        <= len(result.metrics)
        <= runtime.context.settings.agent_max_widgets
    ):
        raise DashboardValidationError(
            "The dashboard plan did not respect the configured widget limits"
        )
    return {"dashboard_plan": result}
