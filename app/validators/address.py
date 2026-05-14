"""
Address validation functions
"""
import re
from typing import Optional


def validate_phone_number(v: str) -> str:
    """
    Validate Indian phone number:
    - Accepts: +91XXXXXXXXXX, 0XXXXXXXXXX, XXXXXXXXXX
    - Digits must start with 6-9
    - Empty strings are not allowed (required field)
    """
    if not v or v.strip() == "":
        raise ValueError("Phone number is required.")

    pattern = r"^(?:\+91|0)?[6-9]\d{9}$"
    if not re.match(pattern, v):
        raise ValueError("Invalid Indian Phone Number. Must be 10 digits starting with 6-9.")
    return v


def validate_pincode(v: str) -> str:
    """
    Validate pincode:
    - Must be exactly 6 digits
    - No spaces or non-numeric characters
    """
    if not v or v.strip() == "":
        raise ValueError("Pincode is required.")

    if not v.isdigit():
        raise ValueError("Pincode must contain only digits.")

    if len(v) != 6:
        raise ValueError("Pincode must be exactly 6 digits.")

    return v

