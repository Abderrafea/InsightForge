"""Add immutable dashboard version history."""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260815_0004"
down_revision: str | None = "20260813_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dashboards",
        sa.Column("current_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "dashboards", sa.Column("last_modified_by_message_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_dashboards_last_modified_by_message_id_messages"),
        "dashboards",
        "messages",
        ["last_modified_by_message_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_dashboards_last_modified_by_message_id"),
        "dashboards",
        ["last_modified_by_message_id"],
    )
    versions = op.create_table(
        "dashboard_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dashboard_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by_message_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_message_id"],
            ["messages.id"],
            name=op.f("fk_dashboard_versions_created_by_message_id_messages"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["dashboard_id"],
            ["dashboards.id"],
            name=op.f("fk_dashboard_versions_dashboard_id_dashboards"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dashboard_versions")),
        sa.UniqueConstraint(
            "dashboard_id", "version_number", name="uq_dashboard_version_number"
        ),
    )
    op.create_index(
        op.f("ix_dashboard_versions_dashboard_id"),
        "dashboard_versions",
        ["dashboard_id"],
    )
    op.create_index(
        op.f("ix_dashboard_versions_created_by_message_id"),
        "dashboard_versions",
        ["created_by_message_id"],
    )

    connection = op.get_bind()
    dashboards = connection.execute(
        sa.text("SELECT id, config_json, created_at FROM dashboards")
    ).mappings()
    snapshots = [
        {
            "id": uuid4(),
            "dashboard_id": row["id"],
            "version_number": 1,
            "config_json": row["config_json"],
            "created_at": row["created_at"],
            "created_by_message_id": None,
        }
        for row in dashboards
    ]
    if snapshots:
        op.bulk_insert(versions, snapshots)
        connection.execute(sa.text("UPDATE dashboards SET current_version = 1"))


def downgrade() -> None:
    op.drop_table("dashboard_versions")
    op.drop_index(
        op.f("ix_dashboards_last_modified_by_message_id"), table_name="dashboards"
    )
    op.drop_constraint(
        op.f("fk_dashboards_last_modified_by_message_id_messages"),
        "dashboards",
        type_="foreignkey",
    )
    op.drop_column("dashboards", "last_modified_by_message_id")
    op.drop_column("dashboards", "current_version")
