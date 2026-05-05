"""Add coupon system to e-commerce database

Revision ID: add_coupon_tables_20260505
Revises: 2041b525957e, a1b2c3d4e5f6, add_webhook_events_20260429
Create Date: 2026-05-05 18:43:00.000000+00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_coupon_tables_20260505'
down_revision: Union[str, Sequence[str], None] = (
    '2041b525957e',
    'a1b2c3d4e5f6',
    'add_webhook_events_20260429'
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ═══════════════════════════════════════════════════════════════
    # 1. CREATE COUPONS TABLE
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'coupons',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('discount_type', sa.Enum('flat', 'percentage', name='discounttype'), nullable=False),
        sa.Column('discount_value', sa.Numeric(10, 2), nullable=False),
        sa.Column('min_order_value', sa.Numeric(10, 2), server_default='0.00', nullable=False),
        sa.Column('max_discount_cap', sa.Numeric(10, 2), nullable=True),
        sa.Column('max_total_uses', sa.Integer(), server_default='1', nullable=False),
        sa.Column('max_uses_per_user', sa.Integer(), server_default='1', nullable=False),
        sa.Column('total_used_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_coupon_code')
    )

    # Index on code for fast lookup
    op.create_index('ix_coupons_code', 'coupons', ['code'], unique=False)

    # ═══════════════════════════════════════════════════════════════
    # 2. CREATE COUPON_USAGES TABLE
    # ═══════════════════════════════════════════════════════════════
    op.create_table(
        'coupon_usages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('coupon_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('used_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('coupon_id', 'user_id', 'order_id', name='uq_coupon_user_order'),
        sa.ForeignKeyConstraint(['coupon_id'], ['coupons.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='SET NULL')
    )

    # Indexes for fast queries
    op.create_index('ix_coupon_usages_coupon_id', 'coupon_usages', ['coupon_id'], unique=False)
    op.create_index('ix_coupon_usages_user_id', 'coupon_usages', ['user_id'], unique=False)

    # ═══════════════════════════════════════════════════════════════
    # 3. MODIFY CARTS TABLE — Add coupon fields
    # ═══════════════════════════════════════════════════════════════
    # Existing rows ke liye default values — data break nahi hoga

    op.add_column(
        'carts',
        sa.Column('coupon_code', sa.String(50), nullable=True, default=None)
    )

    op.add_column(
        'carts',
        sa.Column(
            'discount_amount',
            sa.Numeric(10, 2),
            server_default='0.00',
            nullable=False
        )
    )

    # ═══════════════════════════════════════════════════════════════
    # 4. MODIFY ORDERS TABLE — Add coupon snapshot fields
    # ═══════════════════════════════════════════════════════════════

    op.add_column(
        'orders',
        sa.Column('coupon_code_snapshot', sa.String(50), nullable=True, default=None)
    )

    op.add_column(
        'orders',
        sa.Column(
            'discount_amount',
            sa.Numeric(10, 2),
            server_default='0.00',
            nullable=False
        )
    )


def downgrade() -> None:
    # ═══════════════════════════════════════════════════════════════
    # REVERSE ORDER mein delete karo — dependencies ke liye
    # ═══════════════════════════════════════════════════════════════

    # 1. Drop order columns
    op.drop_column('orders', 'discount_amount')
    op.drop_column('orders', 'coupon_code_snapshot')

    # 2. Drop cart columns
    op.drop_column('carts', 'discount_amount')
    op.drop_column('carts', 'coupon_code')

    # 3. Drop coupon_usages table
    op.drop_index('ix_coupon_usages_user_id', table_name='coupon_usages')
    op.drop_index('ix_coupon_usages_coupon_id', table_name='coupon_usages')
    op.drop_table('coupon_usages')

    # 4. Drop coupons table
    op.drop_index('ix_coupons_code', table_name='coupons')
    op.drop_table('coupons')

    # 5. Drop enum type (PostgreSQL specific)
    op.execute('DROP TYPE IF EXISTS discounttype')

