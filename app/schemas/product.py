import uuid
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any


# --- Category Schemas ---
class CategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    parent_id: Optional[uuid.UUID] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: uuid.UUID
    slug: str
    # Recursive response: Category ke andar uski sub-categories ki list
    sub_categories: List["CategoryResponse"] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# --- Product Schemas ---
class ProductBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    stock_quantity: int = Field(default=0, ge=0)
    category_id: Optional[uuid.UUID] = None  # native UUID
    attributes: Dict[str, Any] = Field(default_factory=dict)


class ProductCreate(ProductBase):
    pass


class ProductResponse(ProductBase):
    id: uuid.UUID
    slug: str
    is_deleted: bool

    model_config = ConfigDict(from_attributes=True)


CategoryResponse.model_rebuild()
