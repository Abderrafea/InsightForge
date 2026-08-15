from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.session import Session


JSON_VARIANT = JSON().with_variant(JSONB(), "postgresql")


class Dashboard(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "dashboards"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_modified_by_message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), index=True, nullable=True
    )

    session: Mapped[Session] = relationship(back_populates="dashboard", lazy="raise")
    last_modified_by_message: Mapped[Message | None] = relationship(lazy="raise")
    versions: Mapped[list[DashboardVersion]] = relationship(
        back_populates="dashboard",
        cascade="all, delete-orphan",
        order_by="DashboardVersion.version_number",
        lazy="raise",
    )


class DashboardVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "dashboard_versions"
    __table_args__ = (
        UniqueConstraint("dashboard_id", "version_number", name="uq_dashboard_version_number"),
    )

    dashboard_id: Mapped[UUID] = mapped_column(
        ForeignKey("dashboards.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )
    created_by_message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), index=True, nullable=True
    )

    dashboard: Mapped[Dashboard] = relationship(back_populates="versions", lazy="raise")
    created_by_message: Mapped[Message | None] = relationship(lazy="raise")
