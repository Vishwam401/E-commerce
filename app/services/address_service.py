import uuid
import logging
from typing import List
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.db.models.address import Address
from app.schemas.address import AddressCreate, AddressUpdate
from app.core.exceptions import NotFoundError, DatabaseError

logger = logging.getLogger(__name__)


class AddressService:

    @staticmethod
    async def get_user_addresses(db: AsyncSession, user_id: uuid.UUID) -> List[Address]:
        try:
            query = select(Address).where(
                and_(Address.user_id == user_id, Address.is_deleted == False)
            ).order_by(Address.is_default.desc())

            result = await db.execute(query)
            return result.scalars().all()
        except SQLAlchemyError as exc:
            logger.error(f"Database error fetching addresses for user {user_id}: {exc}", exc_info=True)
            raise DatabaseError("Failed to fetch addresses")

    @staticmethod
    async def create_address(
        db: AsyncSession,
        user_id: uuid.UUID,
        address_in: AddressCreate
    ) -> Address:
        try:
            existing_check = await db.execute(
                select(Address).where(
                    Address.user_id == user_id, Address.is_deleted == False
                )
            )
            is_first = existing_check.first() is None

            new_address = Address(
                **address_in.model_dump(),
                user_id=user_id,
                is_default=is_first
            )

            db.add(new_address)
            await db.commit()
            await db.refresh(new_address)
            return new_address
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.error(f"Database error creating address for user {user_id}: {exc}", exc_info=True)
            raise DatabaseError("Failed to create address")

    @staticmethod
    async def set_default_address(
        db: AsyncSession,
        user_id: uuid.UUID,
        address_id: uuid.UUID
    ) -> Address:
        try:
            # Remove default from all
            await db.execute(
                update(Address)
                .where(Address.user_id == user_id)
                .values(is_default=False)
            )

            # Set new default
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
                raise NotFoundError("Address not found.")

            await db.commit()
            return updated_address

        except SQLAlchemyError as exc:
            await db.rollback()
            logger.error(f"Database error setting default address: {exc}")
            raise DatabaseError("Failed to update default address.")

    @staticmethod
    async def update_address(
        db: AsyncSession,
        user_id: uuid.UUID,
        address_id: uuid.UUID,
        address_in: AddressUpdate
    ) -> Address:
        stmt = select(Address).where(
            and_(
                Address.id == address_id,
                Address.user_id == user_id,
                Address.is_deleted == False
            )
        )
        result = await db.execute(stmt)
        db_address = result.scalar_one_or_none()

        if not db_address:
            raise NotFoundError("Address not found.")

        update_data = address_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_address, field, value)

        await db.commit()
        await db.refresh(db_address)
        return db_address

    @staticmethod
    async def delete_address(
        db: AsyncSession,
        user_id: uuid.UUID,
        address_id: uuid.UUID
    ):
        stmt = select(Address).where(
            and_(Address.id == address_id, Address.user_id == user_id)
        )
        result = await db.execute(stmt)
        address = result.scalar_one_or_none()

        if not address:
            raise NotFoundError("Address not found.")

        address.is_deleted = True
        if address.is_default:
            address.is_default = False

        await db.commit()
        return {"detail": "Address deleted successfully"}