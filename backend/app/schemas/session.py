from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.dashboard import DashboardRead
from app.schemas.database_connection import DatabaseConnectionRead
from app.schemas.message import MessageRead


class SessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Session title must not be blank")
        return cleaned


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    title: str
    database_connection_id: UUID | None
    ai_provider: str | None
    ai_model: str | None
    created_at: datetime
    updated_at: datetime


class SessionDetails(SessionRead):
    messages: list[MessageRead]
    database_connection: DatabaseConnectionRead | None
    dashboard: DashboardRead | None
