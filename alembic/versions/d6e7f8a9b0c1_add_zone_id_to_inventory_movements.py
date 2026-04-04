"""Add zone_id to inventory_movements.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-04-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_movements",
        sa.Column(
            "zone_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_inventory_movements_zone_id",
        "inventory_movements",
        "zones",
        ["zone_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_inventory_movements_zone_id",
        "inventory_movements",
        ["zone_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inventory_movements_zone_id",
        table_name="inventory_movements",
    )
    op.drop_constraint(
        "fk_inventory_movements_zone_id",
        "inventory_movements",
        type_="foreignkey",
    )
    op.drop_column("inventory_movements", "zone_id")
