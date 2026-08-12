from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.query_execution import QueryExecution
    from app.models.schema_cache import DatabaseSchemaCache
    from app.models.session import Session
    from app.models.user import User


class DatabaseConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "database_connections"

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    database_type: Mapped[str] = mapped_column(
        String(30), default="postgresql", server_default="postgresql", nullable=False
    )
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    database_name: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_password: Mapped[str] = mapped_column(Text, nullable=False)
    ssl_mode: Mapped[str] = mapped_column(String(20), nullable=False)

    user: Mapped[User | None] = relationship(back_populates="database_connections", lazy="raise")
    sessions: Mapped[list[Session]] = relationship(
        back_populates="database_connection", lazy="raise"
    )
    schema_cache: Mapped[DatabaseSchemaCache | None] = relationship(
        back_populates="database_connection",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="raise",
    )
    query_executions: Mapped[list[QueryExecution]] = relationship(
        back_populates="database_connection", lazy="raise"
    )
