from langgraph.runtime import Runtime

from app.agent.dashboard_validation import validate_generated_dashboard
from app.agent.prompts.dashboard_builder import build_dashboard_messages
from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState
from app.schemas.dashboard import DashboardConfig


async def build_dashboard(state: AgentState, runtime: Runtime[AgentRuntime]) -> dict[str, object]:
    dashboard = await runtime.context.provider.structured_output(
        build_dashboard_messages(
            state["dashboard_plan"],
            state["generated_queries"],
            state["query_results"],
            runtime.context.settings.agent_result_sample_rows,
        ),
        DashboardConfig,
    )
    validate_generated_dashboard(dashboard, state["generated_queries"], state["query_results"])
    return {
        "dashboard_config": dashboard,
        "dashboard_changed": True,
        "affected_widget_ids": [widget.id for widget in dashboard.widgets],
        "final_response": (
            f"I created {dashboard.title} with {len(dashboard.widgets)} focused visualizations."
        ),
        "error": None,
    }
