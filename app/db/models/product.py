from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.cart import CartItem

import uuid
from typing import Optional, Dict, Any
from decimal import Decimal
from sqlalchemy import String, Text, Integer, ForeignKey, Boolean, Numeric, text
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB, UUID
from app.db.base_class import Base
from app.db.models.cart import CartItem



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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    attributes: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))

    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('categories.id', ondelete='SET NULL'), nullable=True, index=True
    )
    category: Mapped[Optional[Category]] = relationship("Category", back_populates="products")

    cart_items: Mapped[list["CartItem"]] = relationship("CartItem", back_populates="product")

    def __repr__(self):
        return f"<Product(name='{self.name}', price={self.price})>"