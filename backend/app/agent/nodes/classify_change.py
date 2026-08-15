from app.agent.models import ChangeClassification, DashboardOperationType
from app.agent.state import AgentState


def affected_query_ids(state: AgentState) -> list[str]:
    plan = state["modification_plan"]
    ids: list[str] = []
    for operation in plan.operations:
        requires_data = operation.requires_new_query or operation.operation in {
            DashboardOperationType.UPDATE_QUERY,
        }
        if requires_data and operation.target_query_id and operation.target_query_id not in ids:
            ids.append(operation.target_query_id)
        if (
            requires_data
            and operation.target_widget_id
            and operation.target_query_id is None
        ):
            patch = next(
                (
                    item
                    for item in plan.widget_patches
                    if item.widget_id == operation.target_widget_id
                ),
                None,
            )
            if patch and patch.query_id and patch.query_id not in ids:
                ids.append(patch.query_id)
    return ids


async def classify_change(state: AgentState) -> dict[str, object]:
    plan = state["modification_plan"]
    if plan.needs_clarification:
        return {
            "needs_clarification": True,
            "clarification_question": plan.clarification_question,
        }

    has_data = bool(affected_query_ids(state))
    has_ui = any(
        operation.operation != DashboardOperationType.UPDATE_QUERY
        for operation in plan.operations
    ) or bool(plan.dashboard_title or plan.layout_patches or plan.widget_patches)
    if has_data and has_ui:
        classification = ChangeClassification.MIXED
    elif has_data:
        classification = ChangeClassification.DATA_QUERY_REQUIRED
    else:
        classification = ChangeClassification.UI_ONLY
    return {"change_classification": classification, "needs_clarification": False}


async def request_clarification(state: AgentState) -> dict[str, object]:
    return {
        "dashboard_config": None,
        "dashboard_changed": False,
        "affected_widget_ids": [],
        "final_response": state.get("clarification_question")
        or "Which dashboard item would you like me to change?",
        "error": None,
    }
