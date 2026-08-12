from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.query_execution import QueryExecutionStatus


class QueryRequest(BaseModel):
    sql: str


class QueryValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    referenced_tables: list[str] = Field(default_factory=list)
    statement_type: str | None = None


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
    execution_time_ms: float


class QueryExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID | None
    database_connection_id: UUID
    sql: str
    status: QueryExecutionStatus
    row_count: int
    truncated: bool
    execution_time_ms: float
    error_code: str | None
    error_message: str | None
    created_at: datetime
