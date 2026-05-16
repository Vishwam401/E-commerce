from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from app.api import dependencies as deps
from app.schemas.product import ProductCreate, ProductResponse, CategoryCreate, CategoryResponse
from app.services.category_service import CatalogService
from app.services.product_service import ProductService
from app.core.exceptions import NotFoundError

router = APIRouter()


@router.post("/categories", response_model=CategoryResponse)
async def create_category(
    obj_in: CategoryCreate,
    db: AsyncSession = Depends(deps.get_db),
    _: deps.User = Depends(deps.require_roles("admin")),
):
    created = await CatalogService.create_category(db, obj_in)
    return CategoryResponse(
        id=created.id,
        name=created.name,
        slug=created.slug,
        parent_id=created.parent_id,
        sub_categories=[]
    )


@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(db: AsyncSession = Depends(deps.get_db)):
    return await CatalogService.get_categories(db)


@router.post("/", response_model=ProductResponse)
async def create_product(
    obj_in: ProductCreate,
    db: AsyncSession = Depends(deps.get_db),
    _: deps.User = Depends(deps.require_roles("admin")),
):
    return await ProductService.create(db, obj_in)


@router.get("/", response_model=List[ProductResponse])
async def list_products(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 20
):
    return await ProductService.get_active_products(db, skip, limit)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
    _: deps.User = Depends(deps.require_roles("admin")),
):
    await ProductService.soft_delete(db, str(product_id))
    return None


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db)
):
    product = await ProductService.get_by_id(db, product_id)
    if not product:
        raise NotFoundError("Product not found.")
    return product