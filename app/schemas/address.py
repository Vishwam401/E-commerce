import re
import uuid
from typing import Optional
from pydantic import BaseModel, Field, field_validator



class AddressBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, examples=["Vishwam Vaghasiya"])
    phone_number: str = Field(..., examples=["+919876543210"])
    pincode: str = Field(..., min_length=6, max_length=6, examples=["380001"])
    state: str = Field(..., min_length=2, max_length=50)
    city: str = Field(..., min_length=2, max_length=50)
    house_no: str = Field(..., min_length=1, max_length=255)
    area: str = Field(..., min_length=2, max_length=255)
    address_type: str = Field("Home", examples=["Home", "Office"])

    # === SECURITY & INTEGRITY CHECK: Phone Number ===
    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        pattern = r"^(?:\+91|0)?[6-9]\d{9}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid Indian Phone Number")
        return v

    # === SECURITY & INTEGRITY CHECK: Pincode ===
    @field_validator("pincode")
    @classmethod
    def validate_pincode(cls, v):
        if not v.isdigit():
            raise ValueError("Pincode must contain only digits")
        return v


# Create Schema: Address banane ke waqt
class AddressCreate(AddressBase):
    pass


# Update Schema: Address edit karne ke waqt
class AddressUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    pincode: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    house_no: Optional[str] = None
    area: Optional[str] = None
    address_type: Optional[str] = None
    is_default: Optional[bool] = None


# Response Schema: User ko dikhane ke liye
class AddressResponse(AddressBase):
    id: uuid.UUID
    is_default: bool

    class Config:
        from_attributes = True