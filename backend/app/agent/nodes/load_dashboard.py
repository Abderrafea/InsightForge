from app.agent.state import AgentState


async def load_dashboard(state: AgentState) -> dict[str, object]:
    if state.get("current_dashboard") is None:
        return {
            "dashboard_config": None,
            "dashboard_changed": False,
            "final_response": "There is no dashboard in this session yet.",
            "error": None,
        }
    return {"dashboard_config": None, "dashboard_changed": False}
