from __future__ import annotations
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models.coupon import DiscountType
from app.validators import (
    normalize_coupon_code,
    validate_discount_value,
    validate_discount_cap,
    validate_coupon_dates,
)



# 1. COUPON BASE -- Shared validation Logic

class CouponBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="Unique coupon code")
    discount_type: DiscountType
    discount_value: Decimal = Field(..., gt=Decimal('0'), description="Flat amount or percentage rate")
    min_order_value: Decimal = Field(default=Decimal('0.00'), ge=Decimal('0'))
    max_discount_cap: Optional[Decimal] = Field(default=None, description="Max discount for percentage type")
    max_total_uses: int = Field(default=1, gt=0)
    max_uses_per_user: int = Field(default=1, gt=0)
    valid_from: datetime
    valid_until: datetime
    is_active: bool = True

    @field_validator('code', mode="after")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return normalize_coupon_code(v)

    @model_validator(mode='after')
    def validate_dates_and_discount(self):
        validate_coupon_dates(self.valid_from, self.valid_until)
        validate_discount_value(self.discount_value, self.discount_type)
        validate_discount_cap(self.discount_type, self.max_discount_cap)
        return self


# 2. Admin creates New COUPON

# CouponBase se inherit → saari validation automatic.
# Admin POST /api/v1/admin/coupons pe yeh bhejega.
class CouponCreate(CouponBase):
    pass


# 3. COUPON UPDATE - Partial update by Admin

class CouponUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    discount_type: Optional[DiscountType] = None
    discount_value: Optional[Decimal] = Field(default=None, gt=Decimal('0'))
    min_order_value: Optional[Decimal] = Field(default=None, ge=Decimal('0'))
    max_discount_cap: Optional[Decimal] = None
    max_total_uses: Optional[int] = Field(default=None, gt=0)
    max_uses_per_user: Optional[int] = Field(default=None, gt=0)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: Optional[bool] = None

    @field_validator('code', mode="after")
    @classmethod
    def normalize_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return normalize_coupon_code(v)
        return v

    @model_validator(mode='after')
    def validate_partial_updates(self):
        # Partial update: only validate dates if both provided
        if self.valid_from is not None and self.valid_until is not None:
            validate_coupon_dates(self.valid_from, self.valid_until)

        # Validate discount value if provided
        if self.discount_type is not None and self.discount_value is not None:
            validate_discount_value(self.discount_value, self.discount_type)

        return self


# 4. COUPON RESPONSE - DB se frontend ko data
class CouponResponse(BaseModel):
        id: UUID
        code: str
        discount_type: DiscountType
        discount_value: Decimal
        min_order_value: Decimal
        max_discount_cap: Optional[Decimal]
        max_total_uses: int
        max_uses_per_user: int
        total_used_count: int  # ← usage stat from DB model
        valid_from: datetime
        valid_until: datetime
        is_active: bool
        created_at: datetime

        model_config = ConfigDict(from_attributes=True)


# 5. APPLY COUPON REQUEST - User checkout pe code bhejta hai

# Sirf code chahiye. User_id token se milega, cart_id user se pata chalta hai.
class ApplyCouponRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)

    @field_validator('code', mode="after")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return normalize_coupon_code(v)


# 6. APPLY COUPON RESPONSE - Frontend ko dikhane ke liye
class ApplyCouponResponse(BaseModel):
    coupon_code: str
    discount_amount: Decimal
    original_total: Decimal
    final_total: Decimal

    model_config = ConfigDict(from_attributes=True)


# 7. ADMIN LIST RESPONSE — Paginated coupon list
class CouponAdminListResponse(BaseModel):
    items: List[CouponResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)