from __future__ import annotations
import uuid
import enum
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING

from psycopg2._psycopg import Column
from sqlalchemy import String, ForeignKey, DateTime, Integer, Numeric, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User
    from app.db.models.product import Product
    


# 1. Strict Enum for Order Status
class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Order(Base):
    __tablename__ = "orders"

    # 1. PRIMARY & FOREIGN KEYS
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    address_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("addresses.id", ondelete="SET NULL"), nullable=True)

    # 2. BUSINESS PRICING DATA
    # Sabhi prices ek saath rakho taaki calculation logic samajhne mein aasani ho
    subtotal_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal('0.00')) # Raw Product Total
    tax_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal('0.00'))
    shipping_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal('0.00'))
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal('0.00')) # Grand Total

    # 3. ORDER STATUS
    status: Mapped[OrderStatus] = mapped_column(SQLEnum(OrderStatus), default=OrderStatus.PENDING, nullable=False)

    # 4. ADDRESS SNAPSHOT (Critical for Data Integrity)
    shipping_address_snapshot: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # 5. AUDIT TRAIL (Timestamps)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 6. RELATIONSHIPS
    user: Mapped[User] = relationship("User", back_populates="orders")
    items: Mapped[List[OrderItem]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")



class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"),
                                                nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False,
                                                  index=True)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Currency stored as Decimal
    price_at_purchase: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Relationships
    order: Mapped[Order] = relationship("Order", back_populates="items")
    product: Mapped[Product] = relationship("Product")

    product_name: Mapped[str] = mapped_column(String, nullable=False)