import hmac
import hashlib
import json
import logging

from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.exceptions import (
    WebhookSignatureError,
    NotFoundError,
    DatabaseError,
    ServiceUnavailableError,
)
from app.db.models.transaction import Transaction
from app.db.models.order import Order, OrderStatus
from app.db.models.user import User
from app.worker.tasks import send_invoice_email

logger = logging.getLogger(__name__)


class RazorpayWebhookService:

    @staticmethod
    def verify_signature(body: bytes, signature: str) -> bool:
        secret = settings.RAZORPAY_WEBHOOK_SECRET
        expected_signature = hmac.new(
            key=secret.encode(),
            msg=body,
            digestmod=hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)

    @classmethod
    async def process_webhook(cls, db, raw_body: bytes, signature: str):
        if not cls.verify_signature(raw_body, signature):
            logger.error("Invalid webhook signature received")
            raise WebhookSignatureError()

        logger.info("Webhook signature verified")

        data = json.loads(raw_body)
        event_type = data.get("event")

        if event_type == "payment.captured":
            logger.info("Payment Captured Event Received")
            payment_entity = data["payload"]["payment"]["entity"]
            razorpay_order_id = payment_entity.get("order_id")
            await cls.handle_payment_success(db, razorpay_order_id, payment_entity)

        elif event_type == "order.paid":
            logger.info("Order Paid Event Received")

        else:
            logger.info(f"Ignored webhook event: {event_type}")

        return True

    @classmethod
    async def handle_payment_success(
        cls,
        db,
        razorpay_order_id: str,
        payment_entity: dict
    ):
        stmt = select(Transaction).where(
            Transaction.razorpay_order_id == razorpay_order_id
        )
        result = await db.execute(stmt)
        transaction = result.scalar_one_or_none()

        if not transaction:
            logger.error(f"Transaction not found: {razorpay_order_id}")
            raise NotFoundError("Transaction record not found.")

        # Idempotency check
        if transaction.status == "SUCCESS":
            logger.info(f"Idempotency: Order {razorpay_order_id} already PAID")
            return True

        try:
            transaction.status = "SUCCESS"
            transaction.razorpay_payment_id = payment_entity.get("id")

            order_stmt = select(Order).where(Order.id == transaction.order_id)
            order_result = await db.execute(order_stmt)
            order = order_result.scalar_one_or_none()

            if not order:
                raise NotFoundError("Associated order not found.")

            order.status = OrderStatus.PAID
            await db.commit()

            logger.info(f"Order {order.id} marked PAID via webhook")

            # Email queue (after commit, failures isolated)
            try:
                user_stmt = select(User).where(User.id == order.user_id)
                user_result = await db.execute(user_stmt)
                real_user = user_result.scalar_one_or_none()

                if real_user and real_user.email:
                    send_invoice_email.delay(
                        user_email=real_user.email,
                        user_id=str(real_user.id),
                        order_id=str(order.id),
                        amount=float(order.total_price)
                    )
                    logger.info(f"Invoice email queued for Order {order.id}")
            except Exception as email_error:
                logger.warning(
                    f"Email queue failed (payment already saved): {email_error}"
                )

            return True

        except SQLAlchemyError as exc:
            await db.rollback()
            logger.error(f"Webhook DB update failed: {exc}")
            raise DatabaseError("Failed to update payment status.")
        except NotFoundError:
            await db.rollback()
            raise
        except Exception as exc:
            await db.rollback()
            logger.error(f"Webhook processing error: {exc}")
            raise ServiceUnavailableError("Webhook processing failed.")