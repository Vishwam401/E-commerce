from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from typing import Optional
from uuid import UUID


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(
        ...,  # Required field
        min_length=1,
        max_length=50,
        regex=r'^[a-zA-Z0-9_]+$'  # Alphanumeric with underscores
    )


class UserCreate(UserBase):
    password: str = Field(
        ...,  # Required field
        min_length=8,
        max_length=50,
        regex=r'^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]+$'  # Strong password policy
    )


class UserOut(UserBase):
    id: UUID
    is_active: bool = Field(default=False)
    is_admin: bool = Field(default=False)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
