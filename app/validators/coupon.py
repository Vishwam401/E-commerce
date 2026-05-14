"""
Coupon validation functions
"""
from decimal import Decimal
from datetime import datetime
from typing import Optional
from app.db.models.coupon import DiscountType


def normalize_coupon_code(v: str) -> str:
    """
    Normalize coupon code:
    - Strip whitespace
    - Convert to uppercase
    """
    return v.strip().upper()


def validate_discount_value(discount_value: Decimal, discount_type: DiscountType) -> None:
    """
    Validate discount value based on type:
    - Flat: Any positive value
    - Percentage: Must be 0-100
    """
    if discount_type == DiscountType.PERCENTAGE and discount_value > Decimal('100'):
        raise ValueError('Percentage discount cannot exceed 100%')


def validate_discount_cap(discount_type: DiscountType, max_discount_cap: Optional[Decimal]) -> None:
    """
    Validate discount cap:
    - Only for percentage discounts
    - Must be positive if provided
    """
    if discount_type == DiscountType.PERCENTAGE and max_discount_cap is not None:
        if max_discount_cap <= Decimal('0'):
            raise ValueError('max_discount_cap must be positive for percentage discounts')


def validate_coupon_dates(valid_from: datetime, valid_until: datetime) -> None:
    """
    Validate coupon date range:
    - valid_until must be strictly after valid_from
    """
    if valid_until <= valid_from:
        raise ValueError('valid_until must be strictly after valid_from')

