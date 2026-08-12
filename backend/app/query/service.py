import logging
from time import perf_counter
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.database_connection import DatabaseConnection
from app.models.query_execution import QueryExecution, QueryExecutionStatus
from app.query.exceptions import (
    QueryEngineError,
    QueryErrorCode,
    QueryValidationFailedError,
)
from app.query.executor import SafeQueryExecutor
from app.query.models import QueryResult, QueryValidationResult
from app.query.validator import SQLValidator
from app.repositories.database_connection_repository import DatabaseConnectionRepository
from app.repositories.query_execution_repository import QueryExecutionRepository
from app.repositories.session_repository import SessionRepository
from app.services.schema_inspection_service import SchemaInspectionService

logger = logging.getLogger(__name__)


class SafeQueryService:
    def __init__(
        self,
        db: AsyncSession,
        connections: DatabaseConnectionRepository,
        sessions: SessionRepository,
        executions: QueryExecutionRepository,
        schema_service: SchemaInspectionService,
        validator: SQLValidator,
        executor: SafeQueryExecutor,
    ) -> None:
        self._db = db
        self._connections = connections
        self._sessions = sessions
        self._executions = executions
        self._schema_service = schema_service
        self._validator = validator
        self._executor = executor

    async def validate(self, connection_id: UUID, sql: str) -> QueryValidationResult:
        await self._get_connection(connection_id)
        local_validation = self._validator.validate(sql)
        if not local_validation.valid:
            return local_validation
        schema = await self._schema_service.get_schema(connection_id)
        return self._validator.validate(sql, schema)

    async def execute(
        self,
        connection_id: UUID,
        sql: str,
        *,
        session_id: UUID | None = None,
    ) -> QueryResult:
        connection = await self._get_connection(connection_id)
        started_at = perf_counter()

        local_validation = self._validator.validate(sql)
        if not local_validation.valid:
            await self._record_failure(
                connection_id=connection_id,
                session_id=session_id,
                sql=sql,
                status=QueryExecutionStatus.VALIDATION_FAILED,
                error=QueryValidationFailedError(local_validation.errors),
                started_at=started_at,
            )
            raise QueryValidationFailedError(local_validation.errors)

        try:
            schema = await self._schema_service.get_schema(connection_id)
        except BadRequestError as exc:
            query_error = QueryEngineError(QueryErrorCode.DATABASE_CONNECTION_FAILED, exc.message)
            await self._record_failure(
                connection_id=connection_id,
                session_id=session_id,
                sql=sql,
                status=QueryExecutionStatus.EXECUTION_FAILED,
                error=query_error,
                started_at=started_at,
            )
            raise query_error from exc

        validation = self._validator.validate(sql, schema)
        if not validation.valid:
            await self._record_failure(
                connection_id=connection_id,
                session_id=session_id,
                sql=sql,
                status=QueryExecutionStatus.VALIDATION_FAILED,
                error=QueryValidationFailedError(validation.errors),
                started_at=started_at,
            )
            raise QueryValidationFailedError(validation.errors)

        try:
            result = await self._executor.execute(connection, sql)
        except QueryEngineError as exc:
            status = (
                QueryExecutionStatus.TIMEOUT
                if exc.query_code == QueryErrorCode.QUERY_TIMEOUT
                else QueryExecutionStatus.EXECUTION_FAILED
            )
            await self._record_failure(
                connection_id=connection_id,
                session_id=session_id,
                sql=sql,
                status=status,
                error=exc,
                started_at=started_at,
            )
            raise
        except Exception as exc:
            query_error = QueryEngineError(
                QueryErrorCode.QUERY_EXECUTION_FAILED,
                "The analytical query could not be executed.",
            )
            await self._record_failure(
                connection_id=connection_id,
                session_id=session_id,
                sql=sql,
                status=QueryExecutionStatus.EXECUTION_FAILED,
                error=query_error,
                started_at=started_at,
            )
            raise query_error from exc

        execution = await self._executions.create(
            session_id=session_id,
            database_connection_id=connection_id,
            sql=sql,
            status=QueryExecutionStatus.SUCCESS,
            row_count=result.row_count,
            truncated=result.truncated,
            execution_time_ms=result.execution_time_ms,
        )
        await self._db.commit()
        self._log_execution(execution)
        return result

    async def execute_for_session(self, session_id: UUID, sql: str) -> QueryResult:
        session = await self._sessions.get(session_id)
        if session is None:
            raise NotFoundError("Session")
        if session.database_connection_id is None:
            raise BadRequestError(
                "Session has no database connection attached",
                code="session_database_connection_required",
            )
        return await self.execute(session.database_connection_id, sql, session_id=session_id)

    async def list_session_history(self, session_id: UUID) -> list[QueryExecution]:
        if await self._sessions.get(session_id) is None:
            raise NotFoundError("Session")
        return await self._executions.list_for_session(session_id)

    async def _get_connection(self, connection_id: UUID) -> DatabaseConnection:
        connection = await self._connections.get(connection_id)
        if connection is None:
            raise NotFoundError("Database connection")
        return connection

    async def _record_failure(
        self,
        *,
        connection_id: UUID,
        session_id: UUID | None,
        sql: str,
        status: QueryExecutionStatus,
        error: QueryEngineError,
        started_at: float,
    ) -> None:
        execution_time_ms = round((perf_counter() - started_at) * 1_000, 3)
        execution = await self._executions.create(
            session_id=session_id,
            database_connection_id=connection_id,
            sql=sql,
            status=status,
            execution_time_ms=execution_time_ms,
            error_code=error.query_code.value,
            error_message=error.message[:500],
        )
        await self._db.commit()
        self._log_execution(execution)

    @staticmethod
    def _log_execution(execution: QueryExecution) -> None:
        logger.info(
            "Analytical query execution completed",
            extra={
                "query_execution_id": str(execution.id),
                "session_id": str(execution.session_id) if execution.session_id else None,
                "connection_id": str(execution.database_connection_id),
                "status": execution.status.value,
                "execution_time_ms": execution.execution_time_ms,
                "row_count": execution.row_count,
                "truncated": execution.truncated,
            },
        )
