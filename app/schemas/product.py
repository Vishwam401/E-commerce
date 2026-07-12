import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List, Dict, Any


# --- Category Schemas ---
class CategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    parent_id: Optional[uuid.UUID] = None

    @field_validator("parent_id", mode="before")
    @classmethod
    def blank_parent_id_to_none(cls, v):
        # HTML forms send "" for an empty optional field — Pydantic's UUID
        # validator rejects "" outright, so normalize it to None here.
        return None if v == "" else v


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

    @field_validator("category_id", mode="before")
    @classmethod
    def blank_category_id_to_none(cls, v):
        # Same empty-string-from-form issue as Category.parent_id above.
        return None if v == "" else v


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    """Schema for partial admin updates — all fields optional."""
    price: Optional[float] = Field(default=None, gt=0)
    stock_quantity: Optional[int] = Field(default=None, ge=0)
    description: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class ProductResponse(ProductBase):
    id: uuid.UUID
    slug: str
    is_deleted: bool

    model_config = ConfigDict(from_attributes=True)


CategoryResponse.model_rebuild()
