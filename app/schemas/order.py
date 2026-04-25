from pydantic import BaseModel, Field, UUID4
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from app.db.models.order import OrderStatus
from app.schemas.product import ProductResponse


class OrderItemOut(BaseModel):
    id:UUID4
    product_id: UUID4
    quantity: int
    price_at_purchase: Decimal
    product: Optional[ProductResponse] = None

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id: UUID4
    user_id: UUID4
    total_price: Decimal
    status: OrderStatus
    shipping_address: Optional[str] = None
    created_at: datetime
    items: List[OrderItemOut] = Field(default_factory=list)

    class Config:
        from_attributes = True

class OrderCreate(BaseModel):
    shipping_address: Optional[str] = None
