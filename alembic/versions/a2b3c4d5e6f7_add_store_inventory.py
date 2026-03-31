"""Add store_inventory table.

Revision ID: a2b3c4d5e6f7
Revises: f3a4b5c6d7e8
Create Date: 2026-03-31 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "a2b3c4d5e6f7"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "store_inventory",
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
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("low_stock_threshold", sa.Float(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "store_id",
            "product_id",
            name="uq_store_inventory_store_product",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_store_inventory_store_id", "store_inventory", ["store_id"]
    )
    op.create_index(
        "ix_store_inventory_product_id", "store_inventory", ["product_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_store_inventory_product_id", table_name="store_inventory")
    op.drop_index("ix_store_inventory_store_id", table_name="store_inventory")
    op.drop_table("store_inventory")
