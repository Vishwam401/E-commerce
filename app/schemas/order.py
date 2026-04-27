from pydantic import BaseModel, Field, UUID4
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from app.db.models.order import OrderStatus

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

class PaymentVerifyRequest(BaseModel):
    razorpay_order_id: str = Field(..., min_length=1)
    razorpay_payment_id: str = Field(..., min_length=1)
    razorpay_signature: str = Field(..., min_length=1)
