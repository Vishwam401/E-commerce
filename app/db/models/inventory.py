from __future__ import annotations

import uuid
import enum
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Integer, DateTime, Index, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.product import Product
    from app.db.models.user import User


class StockMovementType(str, enum.Enum):
    SALE = "SALE"
    RETURN = "RETURN"
    RESTOCK = "RESTOCK"
    ADJUSTMENT = "ADJUSTMENT"


class StockMovement(Base):
    __tablename__ = "stock_movements"

    __table_args__ = (
        Index("ix_stock_movements_product_id", "product_id"),
        Index("ix_stock_movements_created_at", "created_at"),
        Index("ix_stock_movements_product_created", "product_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    movement_type: Mapped[StockMovementType] = mapped_column(
        SQLEnum(StockMovementType, name="stockmovementtype"),
        nullable=False,
    )

    quantity_changed: Mapped[int] = mapped_column(Integer, nullable=False)

    quantity_before: Mapped[int] = mapped_column(Integer, nullable=False)

    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)

    reference_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    performed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="stock_movements",
    )

    performed_by_user: Mapped[Optional["User"]] = relationship("User")