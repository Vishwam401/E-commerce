from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from datetime import datetime
from uuid import UUID
import re
from typing import Optional


def _validate_password_strength(value: str) -> str:
    if not re.search(r"[A-Z]", value):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", value):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", value):
        raise ValueError("Password must contain at least one digit.")
    if not re.search(r"[@$!%*?&]", value):
        raise ValueError("Password must contain at least one special character (@$!%*?&).")
    return value


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(
        ...,  # Required field
        min_length=3,
        max_length=50,
        pattern=r'^[a-zA-Z0-9_]+$'  # Alphanumeric with underscores
    )


class UserCreate(UserBase):
    password: str = Field(
        ...,  # Required field
        min_length=8,
        max_length=50
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        return _validate_password_strength(value)


class UserOut(UserBase):
    id: UUID
    is_active: bool = Field(default=False)
    is_admin: bool = Field(default=False)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PasswordResetCheck(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    email: EmailStr
    token: str = Field(..., min_length=10, max_length=2048)
    new_password: str = Field(..., min_length=8, max_length=50)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, value: str) -> str:
        return _validate_password_strength(value)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None

    @field_validator("phone_number")
    @classmethod
    def validate_indian_phone(cls, v: str):
        if v is None: return v

        pattern = r"^(?:\+91|0)?[6-9]\d{9}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid Indian Phone Number. Must be 10 digits.")

        # Standardize: Always store as +91XXXXXXXXXX
        clean_v = "".join(filter(str.isdigit, v))
        if len(clean_v) == 10:
            return f"+91{clean_v}"
        elif len(clean_v) == 12 and clean_v.startswith("91"):
            return f"+{clean_v}"
        return v


