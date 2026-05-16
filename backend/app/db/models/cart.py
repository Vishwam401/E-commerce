from __future__ import annotations
from typing import TYPE_CHECKING, Optional
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    ForeignKey, DateTime, Integer, CheckConstraint,
    UniqueConstraint, Numeric, String
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.product import Product


class Cart(Base):
    __tablename__ = 'carts'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete="CASCADE"),
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items: Mapped[list["CartItem"]] = relationship(
        "CartItem",
        back_populates="cart",
        cascade="all, delete-orphan"
    )

    # -- Coupon Fields ---
    coupon_code: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, default=None
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),nullable=False, default=Decimal('0.00')
    )

    @property
    def subtotal_price(self) -> Decimal:
        return sum(
            item.quantity * item.product.price
            for item in self.items
            if item.product
        )

    @property
    def total_price(self) -> Decimal:
        raw_total = self.subtotal_price - self.discount_amount
        return max(raw_total, Decimal('0.00'))


class CartItem(Base):
    __tablename__ = 'cart_items'

    __table_args__ = (
        UniqueConstraint('cart_id', 'product_id', name='uq_cart_product'),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,default=uuid.uuid4)
    
    cart_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('carts.id', ondelete="CASCADE"),
        index=True
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('products.id', ondelete="CASCADE"),
        index=True
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        CheckConstraint("quantity > 0", name="check_quantity_positive"),
        default=1
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cart: Mapped["Cart"] = relationship("Cart", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="cart_items")
