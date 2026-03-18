"""add products and product_suppliers tables

Revision ID: a1b2c3d4e5f6
Revises: e267a87df7b4
Create Date: 2026-03-17 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'e267a87df7b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Products table
    op.create_table(
        'products',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sku', sa.String(length=100), nullable=True),
        sa.Column('category', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_products_org_id'), 'products', ['org_id'], unique=False)
    op.create_index(op.f('ix_products_sku'), 'products', ['sku'], unique=False)

    # Product-Supplier association table
    op.create_table(
        'product_suppliers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('product_id', sa.UUID(), nullable=False),
        sa.Column('supplier_id', sa.UUID(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'supplier_id', name='uq_product_supplier'),
    )
    op.create_index(
        op.f('ix_product_suppliers_product_id'),
        'product_suppliers',
        ['product_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_product_suppliers_supplier_id'),
        'product_suppliers',
        ['supplier_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_product_suppliers_supplier_id'), table_name='product_suppliers')
    op.drop_index(op.f('ix_product_suppliers_product_id'), table_name='product_suppliers')
    op.drop_table('product_suppliers')
    op.drop_index(op.f('ix_products_sku'), table_name='products')
    op.drop_index(op.f('ix_products_org_id'), table_name='products')
    op.drop_table('products')
