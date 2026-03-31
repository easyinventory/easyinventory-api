"""Add layout_versions table.

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-03-31 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "d1e2f3a4b5c6"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "layout_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.Column("cols", sa.Integer(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("store_id", "version_number", name="uq_layout_versions_store_version"),
    )
    op.create_index("ix_layout_versions_store_id", "layout_versions", ["store_id"])
    op.create_index("ix_layout_versions_is_active", "layout_versions", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_layout_versions_is_active", table_name="layout_versions")
    op.drop_index("ix_layout_versions_store_id", table_name="layout_versions")
    op.drop_table("layout_versions")
