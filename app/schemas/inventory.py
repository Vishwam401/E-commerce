from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.inventory import StockMovementType


class StockMovementResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    movement_type: StockMovementType
    quantity_changed: int
    quantity_before: int
    quantity_after: int
    reference_id: Optional[uuid.UUID]
    reason: Optional[str]
    performed_by: Optional[uuid.UUID]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminAdjustRequest(BaseModel):
    quantity_delta: int
    reason: str = Field(min_length=10)


class AdminRestockRequest(BaseModel):
    quantity_to_add: int = Field(gt=0)
    reason: Optional[str] = None


class LowStockProductResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    stock_quantity: int
    low_stock_threshold: int
    reorder_point: int
    is_at_reorder: bool
    category_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class StockSummaryReport(BaseModel):
    total_active_products: int
    out_of_stock_count: int
    low_stock_count: int
    reorder_alert_count: int
    low_stock_products: List[LowStockProductResponse]


class ProductThresholdUpdate(BaseModel):
    low_stock_threshold: Optional[int] = Field(None, ge=0)
    reorder_point: Optional[int] = Field(None, ge=0)