from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.database_connection import DatabaseConnection
    from app.models.session import Session


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)

    sessions: Mapped[list[Session]] = relationship(back_populates="user", lazy="raise")
    database_connections: Mapped[list[DatabaseConnection]] = relationship(
        back_populates="user", lazy="raise"
    )
