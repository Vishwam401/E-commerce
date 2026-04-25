from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from app.api import dependencies as deps
from app.schemas.product import ProductCreate, ProductResponse, CategoryCreate, CategoryResponse
from app.services.category_service import CatalogService
from app.services.product_service import ProductService


router = APIRouter()

#----Category Endpoints----
@router.post("/categories", response_model =CategoryResponse)
async def create_category(obj_in: CategoryCreate, db: AsyncSession = Depends(deps.get_db)):
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



#----product Endpoints------
@router.post("/", response_model=ProductResponse)
async def create_product(obj_in: ProductCreate, db: AsyncSession = Depends(deps.get_db)):
    return await ProductService.create(db, obj_in)

@router.get("/", response_model=List[ProductResponse])
async def list_products(db: AsyncSession = Depends(deps.get_db), skip: int = 0, limit: int = 20):
    return await ProductService.get_active_products(db, skip, limit)

@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: str,
    db: AsyncSession = Depends(deps.get_db)
):
    try:
        product_uuid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid product ID format")

    success = await ProductService.soft_delete(db, str(product_uuid))
    if not success:
        raise HTTPException(status_code=404, detail="Product not found")
    return None # 204 No Content return karega


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
        product_id: uuid.UUID,
        db: AsyncSession = Depends(deps.get_db)
):
    # Router ne Service ki static method call ki
    product = await ProductService.get_by_id(db, product_id)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bhai, ye product database mein nahi hai!"
        )

    return product