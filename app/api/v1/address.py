import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.schemas.address import AddressCreate, AddressUpdate, AddressResponse
from app.services.address_service import AddressService
from app.db.models.user import User

router = APIRouter()

# 1. Sare addresses fetch karna (Logic: get_user_addresses)
# Return type List[AddressOut] hai jisme 'id' aur 'is_default' bhi aayega
@router.get("/", response_model=List[AddressResponse])
async def list_addresses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await AddressService.get_user_addresses(db, current_user.id)

# 2. Naya address banana (Logic: create_address)
# AddressCreate schema use karega validation ke liye
@router.post("/", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
async def create_address(
    address_in: AddressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await AddressService.create_address(db, current_user.id, address_in)

# 3. Default address set karna (Logic: set_default_address)
# Service method: set_default_address(db, user_id, address_id)
@router.patch("/{address_id}/default", response_model=AddressResponse)
async def set_default(
    address_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await AddressService.set_default_address(db, current_user.id, address_id)

# 4. Address update karna (Logic: update_address)
# AddressUpdate schema use karega jisme saare fields Optional hain
@router.patch("/{address_id}", response_model=AddressResponse)
async def update_address(
    address_id: uuid.UUID,
    address_in: AddressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await AddressService.update_address(db, current_user.id, address_id, address_in)

# 5. Soft delete address (Logic: delete_address)
# Service method: delete_address(db, user_id, address_id)
@router.delete("/{address_id}", status_code=status.HTTP_200_OK)
async def delete_address(
    address_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await AddressService.delete_address(db, current_user.id, address_id)
    return {"message": "Address deleted successfully"}