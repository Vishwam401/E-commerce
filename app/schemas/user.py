from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from datetime import datetime
from uuid import UUID
from typing import Optional

# Import validators from separate module
from app.validators import (
    validate_password_strength,
    validate_full_name,
    validate_indian_phone,
    normalize_email,
    normalize_username,
)


class UserBase(BaseModel):
    """Base user schema with email and username normalization"""
    email: EmailStr
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r'^[a-zA-Z0-9_]+$'
    )

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email_field(cls, v: str) -> str:
        return normalize_email(v)

    @field_validator("username", mode="after")
    @classmethod
    def normalize_username_field(cls, v: str) -> str:
        return normalize_username(v)


class UserCreate(UserBase):
    """User registration schema"""
    password: str = Field(..., min_length=8, max_length=50)
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone_number: Optional[str] = Field(None, min_length=10, max_length=15)

    @field_validator("password", mode="after")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)

    @field_validator("full_name", mode="after")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        return validate_full_name(v)

    @field_validator("phone_number", mode="after")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return validate_indian_phone(v)



class UserOut(UserBase):
    id: UUID
    email: EmailStr
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: bool = Field(default=False)
    is_admin: bool = Field(default=False)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PasswordResetCheck(BaseModel):
    """Initiate password reset"""
    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email_field(cls, v: str) -> str:
        return normalize_email(v)


class PasswordResetConfirm(BaseModel):
    """Confirm password reset with token"""
    email: EmailStr
    token: str = Field(..., min_length=10, max_length=2048)
    new_password: str = Field(..., min_length=8, max_length=50)

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email_field(cls, v: str) -> str:
        return normalize_email(v)

    @field_validator("new_password", mode="after")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


class UserUpdate(BaseModel):
    """Update user profile - all fields optional"""
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(None, min_length=10, max_length=15)

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email_field(cls, v: Optional[str]) -> Optional[str]:
        return normalize_email(v) if v else v

    @field_validator("full_name", mode="after")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        return validate_full_name(v)

    @field_validator("phone_number", mode="after")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return validate_indian_phone(v)


