from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.database_connection import DatabaseConnection


JSON_VARIANT = JSON().with_variant(JSONB(), "postgresql")


class DatabaseSchemaCache(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "database_schema_cache"

    database_connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("database_connections.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False)

    database_connection: Mapped[DatabaseConnection] = relationship(
        back_populates="schema_cache", lazy="raise"
    )
