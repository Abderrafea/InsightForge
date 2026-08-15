from typing import Literal

from langgraph.graph import END, START, StateGraph

from app.agent.models import ChangeClassification, UserIntent
from app.agent.nodes import (
    apply_change,
    build_dashboard,
    classify_change,
    execute_queries,
    generate_modified_sql,
    generate_sql,
    inspect_schema,
    load_dashboard,
    plan_change,
    plan_dashboard,
    request_clarification,
    understand_request,
    validate_modified_dashboard,
    validate_modified_sql,
    validate_sql,
)
from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState
from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.exceptions import ProviderConfigurationError
from app.query.service import SafeQueryService
from app.services.schema_inspection_service import SchemaInspectionService


class AgentWorkflow:
    def __init__(
        self,
        provider: LLMProvider,
        schema_service: SchemaInspectionService,
        query_service: SafeQueryService,
        settings: Settings,
    ) -> None:
        if not provider.capabilities.structured_output:
            raise ProviderConfigurationError(
                f"AI model '{provider.model}' does not support structured output"
            )
        self._runtime = AgentRuntime(provider, schema_service, query_service, settings)
        self._max_sql_retries = settings.agent_max_sql_retries
        builder = StateGraph(AgentState, context_schema=AgentRuntime)
        builder.add_node("understand_request", understand_request)
        builder.add_node("load_dashboard", load_dashboard)
        builder.add_node("inspect_schema", inspect_schema)
        builder.add_node("plan_dashboard", plan_dashboard)
        builder.add_node("plan_change", plan_change)
        builder.add_node("classify_change", classify_change)
        builder.add_node("generate_sql", generate_sql)
        builder.add_node("generate_modified_sql", generate_modified_sql)
        builder.add_node("validate_sql", validate_sql)
        builder.add_node("validate_modified_sql", validate_modified_sql)
        builder.add_node("execute_queries", execute_queries)
        builder.add_node("build_dashboard", build_dashboard)
        builder.add_node("apply_change", apply_change)
        builder.add_node("validate_modified_dashboard", validate_modified_dashboard)
        builder.add_node("request_clarification", request_clarification)
        builder.add_node("no_dashboard", self._no_dashboard)
        builder.add_node("failed", self._failed)

        builder.add_edge(START, "understand_request")
        builder.add_conditional_edges("understand_request", self._route_intent)
        builder.add_conditional_edges("load_dashboard", self._route_loaded_dashboard)
        builder.add_conditional_edges("inspect_schema", self._route_after_schema)
        builder.add_edge("plan_dashboard", "generate_sql")
        builder.add_edge("plan_change", "classify_change")
        builder.add_conditional_edges("classify_change", self._route_classified_change)
        builder.add_edge("generate_sql", "validate_sql")
        builder.add_edge("generate_modified_sql", "validate_modified_sql")
        builder.add_conditional_edges("validate_sql", self._route_after_create_validation)
        builder.add_conditional_edges(
            "validate_modified_sql", self._route_after_modify_validation
        )
        builder.add_conditional_edges("execute_queries", self._route_after_execution)
        builder.add_edge("build_dashboard", END)
        builder.add_edge("apply_change", "validate_modified_dashboard")
        builder.add_edge("validate_modified_dashboard", END)
        builder.add_edge("request_clarification", END)
        builder.add_edge("no_dashboard", END)
        builder.add_edge("failed", END)
        self._graph = builder.compile()

    @property
    def provider_name(self) -> str:
        return self._runtime.provider.name

    @property
    def model_name(self) -> str:
        return self._runtime.provider.model

    async def run(self, initial_state: AgentState) -> AgentState:
        result = await self._graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": initial_state["session_id"]}},
            context=self._runtime,
        )
        return AgentState(**result)

    @staticmethod
    def _route_intent(state: AgentState) -> Literal["load_dashboard", "inspect_schema"]:
        if state.get("intent") == UserIntent.MODIFY_DASHBOARD:
            return "load_dashboard"
        return "inspect_schema"

    @staticmethod
    def _route_loaded_dashboard(
        state: AgentState,
    ) -> Literal["inspect_schema", "no_dashboard"]:
        return "inspect_schema" if state.get("current_dashboard") is not None else "no_dashboard"

    @staticmethod
    def _route_after_schema(state: AgentState) -> Literal["plan_dashboard", "plan_change"]:
        if state.get("intent") == UserIntent.MODIFY_DASHBOARD:
            return "plan_change"
        return "plan_dashboard"

    @staticmethod
    def _route_classified_change(
        state: AgentState,
    ) -> Literal["request_clarification", "apply_change", "generate_modified_sql"]:
        if state.get("needs_clarification"):
            return "request_clarification"
        if state.get("change_classification") == ChangeClassification.UI_ONLY:
            return "apply_change"
        return "generate_modified_sql"

    def _route_after_create_validation(
        self, state: AgentState
    ) -> Literal["execute_queries", "generate_sql", "failed"]:
        if state.get("all_queries_valid"):
            return "execute_queries"
        if state.get("retry_count", 0) < self._max_sql_retries:
            return "generate_sql"
        return "failed"

    def _route_after_modify_validation(
        self, state: AgentState
    ) -> Literal["execute_queries", "generate_modified_sql", "failed"]:
        if state.get("all_queries_valid"):
            return "execute_queries"
        if state.get("retry_count", 0) < self._max_sql_retries:
            return "generate_modified_sql"
        return "failed"

    def _route_after_execution(
        self, state: AgentState
    ) -> Literal[
        "build_dashboard", "apply_change", "generate_sql", "generate_modified_sql", "failed"
    ]:
        is_modify = state.get("intent") == UserIntent.MODIFY_DASHBOARD
        if state.get("all_queries_valid"):
            return "apply_change" if is_modify else "build_dashboard"
        if state.get("retry_count", 0) < self._max_sql_retries:
            return "generate_modified_sql" if is_modify else "generate_sql"
        return "failed"

    @staticmethod
    async def _no_dashboard(state: AgentState) -> dict[str, object]:
        return {
            "dashboard_config": None,
            "dashboard_changed": False,
            "affected_widget_ids": [],
            "final_response": "There is no dashboard in this session yet.",
            "error": None,
        }

    @staticmethod
    async def _failed(state: AgentState) -> dict[str, object]:
        errors = [error for item in state.get("validation_errors", []) for error in item.errors]
        return {
            "dashboard_config": None,
            "dashboard_changed": False,
            "final_response": (
                "I couldn't generate valid analytical queries for this request after multiple "
                "attempts. Please make the request more specific and try again."
            ),
            "error": errors[0] if errors else "SQL retry limit exceeded",
        }
