import uuid
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime


# ----------------------------------------
# 1. Product View for Cart
# (Cart mein humein pura product nahi chahiye, sirf naam aur price kafi hai)
# ----------------------------------------
class ProductCartView(BaseModel):
    id: uuid.UUID
    name: str
    price: float
    slug: str

    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------
# 2. Input Schemas (Jo User bhejega)
# ----------------------------------------
class CartItemCreate(BaseModel):
    product_id: uuid.UUID
    # Field(gt=0) = Pydantic API level pe hi rok dega agar quantity 0 ya minus hui toh
    quantity: int = Field(default=1, gt=0, description="Quantity kam se kam 1 honi chahiye")


class CartItemUpdate(BaseModel):
    quantity: int = Field(gt=0)


# ----------------------------------------
# 3. Output Schemas (Jo hum User ko wapase denge)
# ----------------------------------------
class CartItemResponse(BaseModel):
    id: uuid.UUID
    cart_id: uuid.UUID
    product_id: uuid.UUID
    quantity: int
    product: ProductCartView  # Ye automatically product ka naam/price join kar lega

    model_config = ConfigDict(from_attributes=True)


class CartResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    items: List[CartItemResponse] = []
    created_at: datetime
    updated_at: datetime

    # Ek extra field jo hum backend se calculate karke bhejenge
    total_price: float = 0.0

    model_config = ConfigDict(from_attributes=True)