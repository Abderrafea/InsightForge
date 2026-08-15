import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.exceptions import AgentExecutionError, NoDatabaseConnectedError
from app.agent.graph import AgentWorkflow
from app.agent.models import (
    AgentMessageRequest,
    AgentResult,
    ConversationMessage,
    DashboardChange,
)
from app.agent.state import AgentState
from app.core.exceptions import ApplicationError, NotFoundError
from app.models.agent_run import AgentRun, AgentRunStatus
from app.models.message import Message, MessageRole
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.dashboard import DashboardConfig

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(
        self,
        db: AsyncSession,
        sessions: SessionRepository,
        messages: MessageRepository,
        dashboards: DashboardRepository,
        agent_runs: AgentRunRepository,
        workflow: AgentWorkflow,
        max_context_messages: int,
    ) -> None:
        self._db = db
        self._sessions = sessions
        self._messages = messages
        self._dashboards = dashboards
        self._agent_runs = agent_runs
        self._workflow = workflow
        self._max_context_messages = max_context_messages

    async def send_message(
        self, session_id: UUID, request: AgentMessageRequest
    ) -> tuple[Message, DashboardConfig | None, int | None, DashboardChange | None]:
        session = await self._sessions.get(session_id)
        if session is None:
            raise NotFoundError("Session")

        user_message = await self._messages.create(session_id, MessageRole.USER, request.content)
        run = await self._agent_runs.create(
            session_id,
            self._workflow.provider_name,
            self._workflow.model_name,
        )
        session.ai_provider = self._workflow.provider_name
        session.ai_model = self._workflow.model_name
        session.updated_at = datetime.now(UTC)
        await self._db.commit()

        if session.database_connection_id is None:
            error = NoDatabaseConnectedError()
            await self._finish_with_error(run.id, session_id, error)
            raise error

        history = await self._messages.list_for_session(session_id)
        current_dashboard_record = await self._dashboards.get_for_session(session_id)
        current_dashboard = (
            DashboardConfig.model_validate(current_dashboard_record.config_json)
            if current_dashboard_record
            else None
        )
        recent_history = [
            ConversationMessage(role=message.role.value, content=message.content)
            for message in history[:-1][-self._max_context_messages :]
        ]
        initial_state = AgentState(
            session_id=str(session_id),
            connection_id=str(session.database_connection_id),
            user_request=user_message.content,
            messages=recent_history,
            current_dashboard=current_dashboard,
            retry_count=0,
            validation_errors=[],
            query_results={},
        )

        try:
            state = await self._workflow.run(initial_state)
            result = AgentResult(
                final_response=state["final_response"]
                or "I couldn't complete the dashboard request.",
                dashboard_config=state.get("dashboard_config"),
                retry_count=state.get("retry_count", 0),
                dashboard_changed=state.get("dashboard_changed", False),
                affected_widget_ids=state.get("affected_widget_ids", []),
                change_summary=(
                    state.get("modification_plan").summary
                    if state.get("modification_plan") is not None
                    else None
                ),
            )
        except ApplicationError as exc:
            await self._finish_with_error(run.id, session_id, exc)
            raise
        except Exception as exc:
            error = AgentExecutionError()
            await self._finish_with_error(run.id, session_id, error)
            raise error from exc

        assistant_message = await self._messages.create(
            session_id,
            MessageRole.ASSISTANT,
            result.final_response,
        )
        dashboard_version: int | None = None
        if result.dashboard_config is not None and result.dashboard_changed:
            dashboard, _ = await self._dashboards.upsert_versioned(
                session_id,
                result.dashboard_config,
                created_by_message_id=assistant_message.id,
            )
            dashboard_version = dashboard.current_version

        run.status = AgentRunStatus.FAILED if state.get("error") else AgentRunStatus.SUCCESS
        run.error_message = str(state.get("error"))[:500] if state.get("error") else None
        run.retry_count = result.retry_count
        run.finished_at = datetime.now(UTC)
        session.updated_at = datetime.now(UTC)
        await self._db.commit()
        await self._db.refresh(assistant_message)
        self._log_run(run)
        change = (
            DashboardChange(
                type=state["intent"],
                affected_widgets=result.affected_widget_ids,
                summary=result.change_summary,
            )
            if result.dashboard_changed
            else None
        )
        return assistant_message, result.dashboard_config, dashboard_version, change

    async def _finish_with_error(
        self,
        run_id: UUID,
        session_id: UUID,
        error: ApplicationError,
    ) -> None:
        run = await self._agent_runs.get(run_id)
        if run is not None:
            run.status = AgentRunStatus.FAILED
            run.error_message = error.message[:500]
            run.finished_at = datetime.now(UTC)
        await self._messages.create(session_id, MessageRole.ASSISTANT, error.message)
        await self._db.commit()
        if run is not None:
            self._log_run(run)

    @staticmethod
    def _log_run(run: AgentRun) -> None:
        logger.info(
            "Dashboard agent run completed",
            extra={
                "agent_run_id": str(run.id),
                "session_id": str(run.session_id),
                "provider": run.provider,
                "model": run.model,
                "status": run.status.value,
                "retry_count": run.retry_count,
            },
        )
