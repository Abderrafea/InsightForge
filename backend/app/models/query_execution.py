from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.database_connection import DatabaseConnection
    from app.models.session import Session


class QueryExecutionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    TIMEOUT = "TIMEOUT"


class QueryExecution(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "query_executions"

    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), index=True, nullable=True
    )
    database_connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("database_connections.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    sql: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[QueryExecutionStatus] = mapped_column(
        Enum(
            QueryExecutionStatus,
            name="query_execution_status_enum",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )

    session: Mapped[Session | None] = relationship(back_populates="query_executions", lazy="raise")
    database_connection: Mapped[DatabaseConnection] = relationship(
        back_populates="query_executions", lazy="raise"
    )
