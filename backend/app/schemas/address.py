import uuid
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from app.db.models.address import AddressType
from app.validators import validate_phone_number, validate_pincode



class AddressBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, examples=["Vishwam Vaghasiya"])
    phone_number: str = Field(..., examples=["+919876543210"])
    pincode: str = Field(..., min_length=6, max_length=6, examples=["380001"])
    state: str = Field(..., min_length=2, max_length=50)
    city: str = Field(..., min_length=2, max_length=50)
    house_no: str = Field(..., min_length=1, max_length=255)
    area: str = Field(..., min_length=2, max_length=255)
    address_type: AddressType = AddressType.HOME

    @field_validator("phone_number", mode="after")
    @classmethod
    def validate_phone(cls, v):
        return validate_phone_number(v)

    @field_validator("pincode", mode="after")
    @classmethod
    def validate_pincode_field(cls, v):
        return validate_pincode(v)


# Create Schema: Address banane ke waqt
class AddressCreate(AddressBase):
    full_name: str
    phone_number: str
    house_no: str
    area: str
    city: str
    state: str
    pincode: str
    address_type: AddressType = AddressType.HOME


# Update Schema: Address edit karne ke waqt
class AddressUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    pincode: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    house_no: Optional[str] = None
    area: Optional[str] = None
    address_type: Optional[AddressType] = None
    is_default: Optional[bool] = None


# Response Schema: User ko dikhane ke liye
class AddressResponse(AddressBase):
    id: uuid.UUID
    is_default: bool
    user_id: uuid.UUID


    class Config:
        from_attributes = True
