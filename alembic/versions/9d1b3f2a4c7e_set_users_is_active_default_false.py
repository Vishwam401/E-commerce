"""Set users.is_active default false

Revision ID: 9d1b3f2a4c7e
Revises: 74a44fedbb3e
Create Date: 2026-04-21 01:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d1b3f2a4c7e"
down_revision: Union[str, Sequence[str], None] = "74a44fedbb3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Ensure existing NULL values don't break NOT NULL constraint.
    op.execute("UPDATE users SET is_active = FALSE WHERE is_active IS NULL")

    op.alter_column(
        "users",
        "is_active",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "users",
        "is_active",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )

