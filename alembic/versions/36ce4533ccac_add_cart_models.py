"""Placeholder: add cart models

Revision ID: 36ce4533ccac
Revises: convert_ids_to_uuid_20260422
Create Date: 2026-04-23 12:00:00.000000

This revision exists to keep the migration chain consistent.
The actual cart schema is (re)created in `b8acccfb944a`.
"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "36ce4533ccac"
down_revision: Union[str, Sequence[str], None] = "convert_ids_to_uuid_20260422"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Intentionally empty.
    pass


def downgrade() -> None:
    # Intentionally empty.
    pass
