from __future__ import annotations
import uuid
import enum
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import (
    String, ForeignKey, DateTime, Integer, Numeric, Boolean,
    Enum as SQLEnum, UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User
    from app.db.models.order import Order




class DiscountType(str, enum.Enum):
    FLAT = "flat"
    PERCENTAGE = "percentage"


class Coupon(Base):
    __tablename__ = "coupons"

    id:Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),primary_key=True, default=uuid.uuid4,
    )
    code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False,index=True
    )
    discount_type: Mapped[DiscountType] = mapped_column(
        SQLEnum(
            DiscountType,
            name="discounttype",
        ),
        nullable=False,
    )
    discount_value: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    min_order_value: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal('0.00')
    )
    max_discount_cap: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )

    #--Usage Limit---
    max_total_uses: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )
    max_uses_per_user: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )

    # --Denormalized Counter ---
    total_used_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # --Validity Window---
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


    # --- Relationships ---
    usages: Mapped[List["CouponUsage"]] = relationship(
        "CouponUsage", back_populates="coupon", cascade="all, delete-orphan"
    )




class CouponUsage(Base):
    __tablename__ = "coupon_usages"

    # --Table Level Constraints--
    __table_args__ = (
        UniqueConstraint(
            'coupon_id', 'user_id', 'order_id',
            name='uq_coupon_user_order'
        ),
        Index('ix_coupon_usages_coupon_id', 'coupon_id'),
        Index('ix_coupon_usages_user_id', 'user_id'),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    coupon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coupons.id", ondelete="CASCADE"),
        nullable=False
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )


    # --- Nullable Order ID ---
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('orders.id', ondelete="SET NULL"),
        nullable=True
    )

    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # --Relationships ---
    coupon: Mapped[Coupon] = relationship("Coupon", back_populates="usages")
    user: Mapped["User"] = relationship('User')
    order: Mapped[Optional["Order"]] = relationship("Order")
