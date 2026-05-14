from pydantic import BaseModel, Field, UUID4, field_validator
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from app.db.models.order import OrderStatus
from app.validators import normalize_coupon_code

import uuid


class OrderItemOut(BaseModel):
    product_id: UUID4
    product_name: str
    quantity: int
    price_at_purchase: Decimal

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id: UUID4
    user_id: UUID4
    total_price: Decimal
    status: OrderStatus
    shipping_address_snapshot: Optional[str] = None
    coupon_code_snapshot: Optional[str]  = None
    discount_amount: Decimal = Decimal('0.00')
    created_at: datetime
    items: List[OrderItemOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


class OrderStatusUpdate(BaseModel):
    new_status: OrderStatus = Field(..., description="Target order status")

class OrderCreate(BaseModel):
    address_id: Optional[str] = None


class CheckoutRequest(BaseModel):
    address_id: uuid.UUID
    coupon_code: Optional[str] = Field(default=None, min_length=1, max_length=50)

    @field_validator('coupon_code', mode="after")
    @classmethod
    def validate_coupon_code(cls, v: Optional[str]) -> Optional[str]:
        return normalize_coupon_code(v)

    
class PaymentVerifyRequest(BaseModel):
    razorpay_order_id: str = Field(..., min_length=1)
    razorpay_payment_id: str = Field(..., min_length=1)
    razorpay_signature: str = Field(..., min_length=1)
