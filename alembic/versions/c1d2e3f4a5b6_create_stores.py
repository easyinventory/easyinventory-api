"""Create stores table and backfill existing organizations.

Revision ID: c1d2e3f4a5b6
Revises: a1b2c3d4e5f6
Create Date: 2026-03-30 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "c1d2e3f4a5b6"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stores",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
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
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stores_org_id", "stores", ["org_id"])
    op.create_index("ix_stores_is_active", "stores", ["is_active"])

    # Backfill existing organizations with a default store
    op.execute(
        """
        INSERT INTO stores (id, org_id, name, is_active, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            id,
            name || ' Default Store',
            true,
            NOW(),
            NOW()
        FROM organizations
        WHERE id NOT IN (SELECT DISTINCT org_id FROM stores)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_stores_is_active", table_name="stores")
    op.drop_index("ix_stores_org_id", table_name="stores")
    op.drop_table("stores")
