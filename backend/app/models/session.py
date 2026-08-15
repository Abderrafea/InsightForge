from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.agent_run import AgentRun
    from app.models.dashboard import Dashboard
    from app.models.database_connection import DatabaseConnection
    from app.models.message import Message
    from app.models.query_execution import QueryExecution
    from app.models.user import User


class Session(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sessions"

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    database_connection_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("database_connections.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    ai_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(150), nullable=True)

    user: Mapped[User | None] = relationship(back_populates="sessions", lazy="raise")
    database_connection: Mapped[DatabaseConnection | None] = relationship(
        back_populates="sessions", lazy="raise"
    )
    messages: Mapped[list[Message]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
        lazy="raise",
    )
    dashboard: Mapped[Dashboard | None] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="raise",
    )
    query_executions: Mapped[list[QueryExecution]] = relationship(
        back_populates="session", passive_deletes=True, lazy="raise"
    )
    agent_runs: Mapped[list[AgentRun]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="raise"
    )
