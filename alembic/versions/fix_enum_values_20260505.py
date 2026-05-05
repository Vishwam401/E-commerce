"""Rename discounttype enum values to uppercase.

Revision ID: fix_enum_values_20260505
Revises: add_coupon_tables_20260505
Create Date: 2026-05-05

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fix_enum_values_20260505"
down_revision: Union[str, Sequence[str], None] = "add_coupon_tables_20260505"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE discounttype RENAME VALUE 'flat' TO 'FLAT'")
    op.execute("ALTER TYPE discounttype RENAME VALUE 'percentage' TO 'PERCENTAGE'")


def downgrade() -> None:
    op.execute("ALTER TYPE discounttype RENAME VALUE 'FLAT' TO 'flat'")
    op.execute("ALTER TYPE discounttype RENAME VALUE 'PERCENTAGE' TO 'percentage'")

