from __future__ import annotations
import uuid
import re
from typing import List, TYPE_CHECKING
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import validates, relationship, Mapped
from sqlalchemy.sql import func
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.order import Order

class User(Base):
    __tablename__ = "users"

    # DB schema is migrated to native UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Perfect relationship mapping
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="user")

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

