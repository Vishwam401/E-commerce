import uuid
from typing import List, Optional
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.db.models.address import Address
from app.schemas.address import AddressCreate, AddressUpdate


class AddressService:

    @staticmethod
    async def get_user_addresses(db: AsyncSession, user_id: uuid.UUID)-> List[Address]:
        """
            Audit Fix: Hamesha user_id se filter karo taaki koi doosre ka address na dekh sake.
            Only fetch addresses that are not soft-deleted.
        """

        query = select(Address).where(
            and_(
                Address.user_id == user_id,
                Address.is_deleted == False
            )
        ).order_by(Address.is_deleted.desc()) # Default wala sabse upar dikhega

        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def create_address(db: AsyncSession, user_id: uuid.UUID, address_in: AddressCreate) -> Address:
        """
        Business Logic: Agar ye pehla address hai, toh isko automatically default set kar do.
        """
        # Check if any address exists
        existing_check = await db.execute(
            select(Address).where(Address.user_id == user_id, Address.is_deleted == False)
        )
        is_first = existing_check.first() is None

        new_address = Address(
            **address_in.model_dump(),
            user_id=user_id,
            is_default=is_first  # Pehla address hai toh True
        )

        db.add(new_address)
        await db.commit()
        await db.refresh(new_address)
        return new_address

    @staticmethod
    async def set_default_address(db: AsyncSession, user_id: uuid.UUID, address_id: uuid.UUID) -> Address:
        """
        RACE CONDITION FIX: Atomic update taaki ek hi default address rahe.
        """
        # 1. Pehle user ke saare addresses se default flag hatao
        await db.execute(
            update(Address)
            .where(Address.user_id == user_id)
            .values(is_default=False)
        )

        # 2. Specific address ko default set karo (Security: user_id check zaroori hai)
        stmt = (
            update(Address)
            .where(and_(Address.id == address_id, Address.user_id == user_id))
            .values(is_default=True)
            .returning(Address)
        )

        result = await db.execute(stmt)
        updated_address = result.scalar_one_or_none()

        if not updated_address:
            await db.rollback()
            raise HTTPException(status_code=404, detail="Address not found")

        await db.commit()
        return updated_address

    @staticmethod
    async def update_address(
            db: AsyncSession,
            user_id: uuid.UUID,
            address_id: uuid.UUID,
            address_in: AddressUpdate
    ) -> Address:
        """
        Security: Ensure user owns the address before updating.
        """
        stmt = select(Address).where(
            and_(Address.id == address_id, Address.user_id == user_id, Address.is_deleted == False)
        )
        result = await db.execute(stmt)
        db_address = result.scalar_one_or_none()

        if not db_address:
            raise HTTPException(status_code=404, detail="Address not found")

        update_data = address_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_address, field, value)

        await db.commit()
        await db.refresh(db_address)
        return db_address

    @staticmethod
    async def delete_address(db: AsyncSession, user_id: uuid.UUID, address_id: uuid.UUID):
        """
        DATA INTEGRITY FIX: Soft delete use karo taaki purane orders ka link na toote.
        """
        stmt = select(Address).where(
            and_(Address.id == address_id, Address.user_id == user_id)
        )
        result = await db.execute(stmt)
        address = result.scalar_one_or_none()

        if not address:
            raise HTTPException(status_code=404, detail="Address not found")

        address.is_deleted = True

        # Agar default address delete ho raha hai, toh kisi aur ko default banana padega (Optional Logic)
        if address.is_default:
            address.is_default = False

        await db.commit()
        return {"detail": "Address deleted successfully"}