"""Add fixtures table.

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-03-31 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None

FIXTURE_TYPE_VALUES = (
    "WALL",
    "CHECKOUT",
    "FRONT_DESK",
    "DOOR",
    "PILLAR",
    "RESTROOM",
    "STORAGE",
    "STAIRS",
)


def upgrade() -> None:
    op.create_table(
        "fixtures",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "layout_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "fixture_type",
            sa.String(20),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("cells", sa.JSON(), nullable=False),
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
            ["layout_version_id"],
            ["layout_versions.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            f"fixture_type IN ({', '.join(repr(v) for v in FIXTURE_TYPE_VALUES)})",
            name="ck_fixtures_fixture_type",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fixtures_layout_version_id", "fixtures", ["layout_version_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_fixtures_layout_version_id", table_name="fixtures")
    op.drop_table("fixtures")
