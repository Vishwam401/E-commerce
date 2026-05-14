from __future__ import annotations
import uuid
import re
from typing import List, TYPE_CHECKING, Optional
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import validates, relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.order import Order
    from app.db.models.address import Address

class User(Base):
    __tablename__ = "users"

    # DB schema is migrated to native UUID
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(100), nullable=False)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # For Razorpay
    phone_number: Mapped[Optional[str]] = mapped_column(
        String(20),
        unique=True,
        index=True,
        nullable=True
    )

    full_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="user")
    addresses: Mapped[List["Address"]] = relationship("Address", back_populates="user", cascade="all, delete-orphan")

    @validates('email')
    def validate_email(self, key, address):
        address = address.lower()
        if not re.match(r"[^@]+@[^@]+\.[^@]+", address):
            raise ValueError("Invalid email address format")
        return address

    @validates('username')
    def validate_username(self, key, name):
        if len(name) < 3:
            raise ValueError("Username must be at least 3 characters long")
        return name.lower()

