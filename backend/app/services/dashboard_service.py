from uuid import UUID

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.dashboard import Dashboard
from app.query.models import QueryResult
from app.query.service import SafeQueryService
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.dashboard import DashboardConfig


class DashboardService:
    def __init__(
        self,
        sessions: SessionRepository,
        dashboards: DashboardRepository,
        queries: SafeQueryService,
    ) -> None:
        self._sessions = sessions
        self._dashboards = dashboards
        self._queries = queries

    async def get_with_data(
        self, session_id: UUID
    ) -> tuple[Dashboard, dict[str, QueryResult]]:
        session = await self._sessions.get(session_id)
        if session is None:
            raise NotFoundError("Session")
        dashboard = await self._dashboards.get_for_session(session_id)
        if dashboard is None:
            raise NotFoundError("Dashboard")
        if session.database_connection_id is None:
            raise BadRequestError(
                "Session has no database connection attached",
                code="session_database_connection_required",
            )

        config = DashboardConfig.model_validate(dashboard.config_json)
        results: dict[str, QueryResult] = {}
        for query in config.queries:
            results[query.id] = await self._queries.execute(
                session.database_connection_id,
                query.sql,
                session_id=session_id,
            )
        return dashboard, results
