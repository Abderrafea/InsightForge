from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import (
    get_database_connection_service,
    get_schema_inspection_service,
)
from app.schemas.database_connection import (
    ConnectionTestResult,
    DatabaseConnectionCreate,
    DatabaseConnectionRead,
    DatabaseConnectionTest,
)
from app.schemas.schema_inspection import DatabaseSchemaMetadata
from app.services.database_connection_service import DatabaseConnectionService
from app.services.schema_inspection_service import SchemaInspectionService

router = APIRouter(prefix="/database-connections", tags=["database connections"])
ConnectionServiceDependency = Annotated[
    DatabaseConnectionService, Depends(get_database_connection_service)
]
SchemaServiceDependency = Annotated[SchemaInspectionService, Depends(get_schema_inspection_service)]


@router.post("/test", response_model=ConnectionTestResult)
async def test_database_connection(
    request: DatabaseConnectionTest, service: ConnectionServiceDependency
) -> ConnectionTestResult:
    await service.test(request)
    return ConnectionTestResult()


@router.post("", response_model=DatabaseConnectionRead, status_code=status.HTTP_201_CREATED)
async def create_database_connection(
    request: DatabaseConnectionCreate, service: ConnectionServiceDependency
) -> DatabaseConnectionRead:
    connection = await service.create(request)
    return DatabaseConnectionRead.model_validate(connection)


@router.get("/{connection_id}/schema", response_model=DatabaseSchemaMetadata)
async def inspect_database_schema(
    connection_id: UUID,
    service: SchemaServiceDependency,
    refresh: bool = Query(default=False),
) -> DatabaseSchemaMetadata:
    return await service.get_schema(connection_id, refresh=refresh)
