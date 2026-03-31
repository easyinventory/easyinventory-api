"""Add inventory_placements table.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-03-31 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_placements",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "store_inventory_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "zone_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "ended_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "placed_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["store_inventory_id"],
            ["store_inventory.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["zone_id"],
            ["zones.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["placed_by_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_inventory_placements_store_inventory_id",
        "inventory_placements",
        ["store_inventory_id"],
    )
    op.create_index(
        "ix_inventory_placements_zone_id",
        "inventory_placements",
        ["zone_id"],
    )
    op.create_index(
        "ix_inventory_placements_placed_by_user_id",
        "inventory_placements",
        ["placed_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inventory_placements_placed_by_user_id",
        table_name="inventory_placements",
    )
    op.drop_index(
        "ix_inventory_placements_zone_id",
        table_name="inventory_placements",
    )
    op.drop_index(
        "ix_inventory_placements_store_inventory_id",
        table_name="inventory_placements",
    )
    op.drop_table("inventory_placements")
