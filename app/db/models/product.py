from typing import TYPE_CHECKING, List, Optional, Dict, Any

if TYPE_CHECKING:
    from app.db.models.cart import CartItem
    from app.db.models.inventory import StockMovement

import uuid
from decimal import Decimal
from sqlalchemy import String, Text, Integer, ForeignKey, Boolean, Numeric, text, Index, Computed
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB, UUID, TSVECTOR
from app.db.base_class import Base



class Category(Base):
    __tablename__ = 'categories'

    # Native Postgres UUID use kiya
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('categories.id', ondelete="SET NULL"), nullable=True, index=True
    )

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    # Explicit self-referential mapping: one parent -> many sub-categories
    parent: Mapped[Optional["Category"]] = relationship(
        "Category",
        remote_side=[id],
        back_populates="sub_categories"
    )
    sub_categories: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="parent",
        lazy="selectin"
    )
    products: Mapped[list["Product"]] = relationship("Product", back_populates="category", lazy="selectin")

    def __repr__(self):
        return f"<Category(name='{self.name}', slug='{self.slug}')>"


class Product(Base):
    __tablename__ = "products"

    # Composite index: category listing pages filter by category_id and
    # sort/filter by price in the same query. A single (category_id) index
    # still needs a separate sort step for price — this composite index
    # covers both in one lookup.
    #
    # GIN index on search_vector: required for fast full-text search. A normal
    # B-tree index can't index tsvector tokens; GIN builds a reverse lookup
    # (token -> rows) so "which products contain this word" is instant.
    __table_args__ = (
        Index("ix_products_category_price", "category_id", "price"),
        Index("ix_products_search_vector", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    attributes: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))

    # Full-text search column — a GENERATED column maintained by Postgres itself.
    # It auto-recomputes on every insert/update from name + description, so the
    # application never sets it manually. to_tsvector('english', ...) tokenizes
    # + stems the text (e.g. "running" -> "run") and strips stop-words.
    # coalesce(...,'') guards against NULL description breaking the concatenation.
    search_vector: Mapped[Optional[str]] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(name, '') || ' ' || coalesce(description, ''))",
            persisted=True,
        ),
        nullable=True,
    )



    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('categories.id', ondelete='SET NULL'), nullable=True, index=True
    )
    category: Mapped[Optional[Category]] = relationship("Category", back_populates="products")

    cart_items: Mapped[List["CartItem"]] = relationship("CartItem", back_populates="product")

    low_stock_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
    )

    reorder_point: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
    )

    stock_movements: Mapped[List["StockMovement"]] = relationship(
        "StockMovement",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self):
        return f"<Product(name='{self.name}', price={self.price})>"