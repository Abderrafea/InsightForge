from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies import get_safe_query_service
from app.query.models import (
    QueryExecutionRead,
    QueryRequest,
    QueryResult,
    QueryValidationResult,
)
from app.query.service import SafeQueryService

router = APIRouter(tags=["queries"])
QueryServiceDependency = Annotated[SafeQueryService, Depends(get_safe_query_service)]


@router.post(
    "/database-connections/{connection_id}/queries/validate",
    response_model=QueryValidationResult,
)
async def validate_query(
    connection_id: UUID,
    request: QueryRequest,
    service: QueryServiceDependency,
) -> QueryValidationResult:
    return await service.validate(connection_id, request.sql)


@router.post(
    "/database-connections/{connection_id}/queries/execute",
    response_model=QueryResult,
)
async def execute_query(
    connection_id: UUID,
    request: QueryRequest,
    service: QueryServiceDependency,
) -> QueryResult:
    return await service.execute(connection_id, request.sql)


@router.post("/sessions/{session_id}/queries/execute", response_model=QueryResult)
async def execute_session_query(
    session_id: UUID,
    request: QueryRequest,
    service: QueryServiceDependency,
) -> QueryResult:
    return await service.execute_for_session(session_id, request.sql)


@router.get("/sessions/{session_id}/queries", response_model=list[QueryExecutionRead])
async def list_session_query_history(
    session_id: UUID, service: QueryServiceDependency
) -> list[QueryExecutionRead]:
    history = await service.list_session_history(session_id)
    return [QueryExecutionRead.model_validate(execution) for execution in history]
