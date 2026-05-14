"""
Validators module - centralized validation logic
Import validators from here for use in schemas
"""

from app.validators.user import (
    validate_password_strength,
    validate_full_name,
    validate_indian_phone,
    normalize_email,
    normalize_username,
)

from app.validators.address import (
    validate_phone_number,
    validate_pincode,
)

from app.validators.coupon import (
    normalize_coupon_code,
    validate_discount_value,
    validate_discount_cap,
    validate_coupon_dates,
)

__all__ = [
    # User validators
    "validate_password_strength",
    "validate_full_name",
    "validate_indian_phone",
    "normalize_email",
    "normalize_username",
    # Address validators
    "validate_phone_number",
    "validate_pincode",
    # Coupon validators
    "normalize_coupon_code",
    "validate_discount_value",
    "validate_discount_cap",
    "validate_coupon_dates",
]

