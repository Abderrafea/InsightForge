from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.query_execution import QueryExecution, QueryExecutionStatus


class QueryExecutionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        database_connection_id: UUID,
        sql: str,
        status: QueryExecutionStatus,
        execution_time_ms: float,
        session_id: UUID | None = None,
        row_count: int = 0,
        truncated: bool = False,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> QueryExecution:
        execution = QueryExecution(
            session_id=session_id,
            database_connection_id=database_connection_id,
            sql=sql,
            status=status,
            row_count=row_count,
            truncated=truncated,
            execution_time_ms=execution_time_ms,
            error_code=error_code,
            error_message=error_message,
        )
        self._db.add(execution)
        await self._db.flush()
        await self._db.refresh(execution)
        return execution

    async def list_for_session(self, session_id: UUID) -> list[QueryExecution]:
        result = await self._db.scalars(
            select(QueryExecution)
            .where(QueryExecution.session_id == session_id)
            .order_by(QueryExecution.created_at.desc(), QueryExecution.id.desc())
        )
        return list(result)
