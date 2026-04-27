"""add image_url to products

Revision ID: a1b2c3d4e5f6
Revises: 9617e4cbcd52
Create Date: 2026-04-27 16:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '9617e4cbcd52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'products',
        sa.Column('image_url', sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('products', 'image_url')
