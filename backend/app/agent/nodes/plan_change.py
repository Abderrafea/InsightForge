from langgraph.runtime import Runtime

from app.agent.models import DashboardModificationPlan
from app.agent.prompts.change_planner import build_change_plan_messages
from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState


async def plan_change(state: AgentState, runtime: Runtime[AgentRuntime]) -> dict[str, object]:
    current_dashboard = state["current_dashboard"]
    if current_dashboard is None:
        return {
            "dashboard_config": None,
            "dashboard_changed": False,
            "final_response": "There is no dashboard in this session yet.",
        }
    plan = await runtime.context.provider.structured_output(
        build_change_plan_messages(
            state["normalized_request"],
            current_dashboard,
            state.get("messages", []),
            state["compact_schema"],
        ),
        DashboardModificationPlan,
    )
    return {
        "modification_plan": plan,
        "needs_clarification": plan.needs_clarification,
        "clarification_question": plan.clarification_question,
    }
