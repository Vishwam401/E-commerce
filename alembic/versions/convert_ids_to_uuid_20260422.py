"""convert ids to native uuid type

Revision ID: convert_ids_to_uuid_20260422
Revises: 87b9d70b131a
Create Date: 2026-04-22 03:10:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'convert_ids_to_uuid_20260422'
down_revision = '87b9d70b131a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure pgcrypto extension is available for gen_random_uuid()
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    # --- drop foreign keys that reference these columns ---
    op.drop_constraint('categories_parent_id_fkey', 'categories', type_='foreignkey')
    op.drop_constraint('products_category_id_fkey', 'products', type_='foreignkey')

    # --- categories table ---
    # alter id to uuid using cast (only works if existing values are valid UUID strings)
    op.alter_column('categories', 'id',
                    existing_type=sa.VARCHAR(length=36),
                    type_=postgresql.UUID(as_uuid=True),
                    postgresql_using='id::uuid',
                    existing_nullable=False)

    # alter parent_id to uuid
    op.alter_column('categories', 'parent_id',
                    existing_type=sa.VARCHAR(length=36),
                    type_=postgresql.UUID(as_uuid=True),
                    postgresql_using='parent_id::uuid',
                    existing_nullable=True)

    # set default for id to gen_random_uuid()
    op.alter_column('categories', 'id', server_default=sa.text('gen_random_uuid()'))

    # --- products table ---
    op.alter_column('products', 'id',
                    existing_type=sa.VARCHAR(length=36),
                    type_=postgresql.UUID(as_uuid=True),
                    postgresql_using='id::uuid',
                    existing_nullable=False)

    op.alter_column('products', 'category_id',
                    existing_type=sa.VARCHAR(length=36),
                    type_=postgresql.UUID(as_uuid=True),
                    postgresql_using='category_id::uuid',
                    existing_nullable=True)

    op.alter_column('products', 'id', server_default=sa.text('gen_random_uuid()'))

    # recreate foreign keys with proper types
    op.create_foreign_key('categories_parent_id_fkey', 'categories', 'categories', ['parent_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('products_category_id_fkey', 'products', 'categories', ['category_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    # reverse: cast uuid back to varchar(36) as text
    op.alter_column('products', 'id',
                    existing_type=postgresql.UUID(as_uuid=True),
                    type_=sa.VARCHAR(length=36),
                    postgresql_using='id::text',
                    existing_nullable=False)
    op.alter_column('products', 'category_id',
                    existing_type=postgresql.UUID(as_uuid=True),
                    type_=sa.VARCHAR(length=36),
                    postgresql_using='category_id::text',
                    existing_nullable=True)

    op.alter_column('categories', 'id',
                    existing_type=postgresql.UUID(as_uuid=True),
                    type_=sa.VARCHAR(length=36),
                    postgresql_using='id::text',
                    existing_nullable=False)
    op.alter_column('categories', 'parent_id',
                    existing_type=postgresql.UUID(as_uuid=True),
                    type_=sa.VARCHAR(length=36),
                    postgresql_using='parent_id::text',
                    existing_nullable=True)

    # drop server defaults if present
    op.alter_column('products', 'id', server_default=None)
    op.alter_column('categories', 'id', server_default=None)

