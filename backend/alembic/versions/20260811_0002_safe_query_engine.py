"""Add safe query execution history."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260811_0002"
down_revision: str | None = "20260811_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    query_status = postgresql.ENUM(
        "SUCCESS",
        "VALIDATION_FAILED",
        "EXECUTION_FAILED",
        "TIMEOUT",
        name="query_execution_status_enum",
        create_type=False,
    )
    query_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "query_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("database_connection_id", sa.Uuid(), nullable=False),
        sa.Column("sql", sa.Text(), nullable=False),
        sa.Column("status", query_status, nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("truncated", sa.Boolean(), nullable=False),
        sa.Column("execution_time_ms", sa.Float(), nullable=False),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["database_connection_id"],
            ["database_connections.id"],
            name=op.f("fk_query_executions_database_connection_id_database_connections"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name=op.f("fk_query_executions_session_id_sessions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_query_executions")),
    )
    op.create_index(
        op.f("ix_query_executions_database_connection_id"),
        "query_executions",
        ["database_connection_id"],
    )
    op.create_index(
        op.f("ix_query_executions_session_id"),
        "query_executions",
        ["session_id"],
    )


def downgrade() -> None:
    op.drop_table("query_executions")
    postgresql.ENUM(name="query_execution_status_enum").drop(op.get_bind(), checkfirst=True)
