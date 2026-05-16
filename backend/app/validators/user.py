import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def validate_password_strength(value: str) -> str:
    """
    Validate password strength requirements:
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character (@$!%*?&)
    """
    if not re.search(r"[A-Z]", value):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", value):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", value):
        raise ValueError("Password must contain at least one digit.")
    if not re.search(r"[@$!%*?&]", value):
        raise ValueError("Password must contain at least one special character (@$!%*?&).")
    return value


def validate_full_name(value: Optional[str]) -> Optional[str]:
    """
    Validate full name:
    - Only letters and spaces allowed
    - Whitespace trimmed
    - Empty strings converted to None
    """
    logger.debug(f"[validate_full_name] Input: {repr(value)}")
    
    if value is None:
        logger.debug("[validate_full_name] Value is None, returning None")
        return None
    
    if isinstance(value, str) and value.strip() == "":
        logger.debug("[validate_full_name] Value is empty string, returning None")
        return None

    value = value.strip()
    if not re.match(r"^[a-zA-Z\s]+$", value):
        logger.error(f"[validate_full_name] Value '{value}' doesn't match pattern")
        raise ValueError("Full name must contain only letters and spaces.")
    
    logger.debug(f"[validate_full_name] Returning: {repr(value)}")
    return value


def validate_indian_phone(v: Optional[str]) -> Optional[str]:
    """
    Validate and standardize Indian phone number:
    - Accepts: +91XXXXXXXXXX, 0XXXXXXXXXX, XXXXXXXXXX
    - Digits must start with 6-9
    - Returns standardized format: +91XXXXXXXXXX
    - Empty strings or None return None
    """
    logger.debug(f"[validate_indian_phone] Input: {repr(v)}")
    
    if v is None:
        logger.debug("[validate_indian_phone] Value is None, returning None")
        return None

    if isinstance(v, str) and v.strip() == "":
        logger.debug("[validate_indian_phone] Value is empty string, returning None")
        return None

    pattern = r"^(?:\+91|0)?[6-9]\d{9}$"
    if not re.match(pattern, v):
        logger.error(f"[validate_indian_phone] Value '{v}' doesn't match pattern. Pattern: {pattern}")
        raise ValueError("Invalid Indian Phone Number. Must be 10 digits starting with 6-9.")

    # Standardize: Always store as +91XXXXXXXXXX
    clean_v = "".join(filter(str.isdigit, v))
    logger.debug(f"[validate_indian_phone] Clean digits: {clean_v}")
    
    if len(clean_v) == 10:
        result = f"+91{clean_v}"
        logger.debug(f"[validate_indian_phone] Returning standardized: {result}")
        return result
    elif len(clean_v) == 12 and clean_v.startswith("91"):
        result = f"+{clean_v}"
        logger.debug(f"[validate_indian_phone] Returning with prefix: {result}")
        return result
    
    logger.debug(f"[validate_indian_phone] Returning as-is: {v}")
    return v


def normalize_email(v: str) -> str:
    """Normalize email to lowercase for case-insensitive matching"""
    return v.lower() if v else v


def normalize_username(v: str) -> str:
    """Normalize username to lowercase for case-insensitive matching"""
    return v.lower() if v else v

