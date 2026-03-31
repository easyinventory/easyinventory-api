"""Add inventory_movements table.

Revision ID: b4c5d6e7f8a9
Revises: a2b3c4d5e6f7
Create Date: 2026-03-31 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "b4c5d6e7f8a9"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    movement_type = sa.Enum("receipt", "sale", name="movement_type", create_type=True)

    op.create_table(
        "inventory_movements",
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
        sa.Column("movement_type", movement_type, nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "performed_by_user_id",
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
            ["performed_by_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_inventory_movements_store_inventory_id",
        "inventory_movements",
        ["store_inventory_id"],
    )
    op.create_index(
        "ix_inventory_movements_performed_by_user_id",
        "inventory_movements",
        ["performed_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inventory_movements_performed_by_user_id",
        table_name="inventory_movements",
    )
    op.drop_index(
        "ix_inventory_movements_store_inventory_id",
        table_name="inventory_movements",
    )
    op.drop_table("inventory_movements")
    op.execute("DROP TYPE movement_type")
