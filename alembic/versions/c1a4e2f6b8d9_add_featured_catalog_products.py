"""Add the production featured catalog products.

Revision ID: c1a4e2f6b8d9
Revises: 815be9c1e7ce
Create Date: 2026-08-14
"""

import json
import uuid
from decimal import Decimal

from alembic import op
import sqlalchemy as sa


revision = "c1a4e2f6b8d9"
down_revision = "815be9c1e7ce"
branch_labels = None
depends_on = None


FEATURED_PRODUCTS = (
    {
        "name": "Zenith Earbuds Premium",
        "slug": "zenith-earbuds-premium",
        "description": "Active Noise Cancellation (ANC), 36-hour battery life, IPX5 water resistance, and studio-grade audio drivers.",
        "price": Decimal("2499.00"),
        "attributes": {"brand": "Zenith", "battery": "36 hours", "water_resistance": "IPX5", "audio": "Studio-grade drivers"},
    },
    {
        "name": "Nexus Monitor Ultra",
        "slug": "nexus-monitor-ultra",
        "description": "27-inch 4K UHD IPS display, 144Hz refresh rate, 1ms response time, and HDR400 color calibration.",
        "price": Decimal("24799.00"),
        "attributes": {"brand": "Nexus", "display": "27-inch 4K UHD IPS", "refresh_rate": "144Hz", "response_time": "1ms", "color": "HDR400"},
    },
    {
        "name": "Nexus Keyboard Classic",
        "slug": "nexus-keyboard-classic",
        "description": "Hot-swappable tactile mechanical switches, per-key RGB backlighting, aircraft-grade aluminum top frame.",
        "price": Decimal("4899.00"),
        "attributes": {"brand": "Nexus", "switches": "Hot-swappable tactile mechanical", "lighting": "Per-key RGB", "frame": "Aircraft-grade aluminum"},
    },
    {
        "name": "Quantum Mouse Plus",
        "slug": "quantum-mouse-plus",
        "description": "Ergonomic 58g ultra-lightweight design, 26,000 DPI optical sensor, and low-latency wireless.",
        "price": Decimal("2999.00"),
        "attributes": {"brand": "Quantum", "weight": "58g", "sensor": "26,000 DPI optical", "connectivity": "Low-latency wireless"},
    },
)


def upgrade() -> None:
    connection = op.get_bind()
    category_id = connection.execute(
        sa.text("SELECT id FROM categories WHERE name = :name ORDER BY id LIMIT 1"),
        {"name": "Electronics"},
    ).scalar_one_or_none()

    if category_id is None:
        category_id = uuid.uuid4()
        connection.execute(
            sa.text("INSERT INTO categories (id, name, slug, is_deleted) VALUES (:id, :name, :slug, false)"),
            {"id": category_id, "name": "Electronics", "slug": "electronics"},
        )

    for product in FEATURED_PRODUCTS:
        existing_id = connection.execute(
            sa.text("SELECT id FROM products WHERE name = :name LIMIT 1"),
            {"name": product["name"]},
        ).scalar_one_or_none()
        values = {**product, "attributes": json.dumps(product["attributes"]), "category_id": category_id}

        if existing_id is None:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO products (id, name, slug, description, price, stock_quantity, is_deleted, attributes, category_id, low_stock_threshold, reorder_point)
                    VALUES (:id, :name, :slug, :description, :price, 100, false, CAST(:attributes AS jsonb), :category_id, 10, 5)
                    """
                ),
                {**values, "id": uuid.uuid4()},
            )
        else:
            connection.execute(
                sa.text(
                    """
                    UPDATE products
                    SET description = :description, price = :price, attributes = CAST(:attributes AS jsonb),
                        category_id = :category_id, is_deleted = false
                    WHERE id = :id
                    """
                ),
                {**values, "id": existing_id},
            )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM products WHERE name IN :names").bindparams(sa.bindparam("names", expanding=True)),
        {"names": [product["name"] for product in FEATURED_PRODUCTS]},
    )
