import hmac
import hashlib
import json
import logging

from sqlalchemy.future import select

from app.core.config import settings
from app.db.models.transaction import Transaction
from app.db.models.order import Order, OrderStatus
from app.worker.tasks import send_invoice_email
from app.db.models.user import User

logger = logging.getLogger(__name__)

class RazorpayWebhookService:

    @staticmethod
    def verify_signature(body: bytes, signature: str) -> bool:
        """
        Razorpay se aayi raw body aur apne secret ko mix karke hash banata hai.
        Agar apna hash aur Razorpay ka signature match ho gaya, matlab request asli hai!
        """

        secret = settings.RAZORPAY_WEBHOOK_SECRET

        # HMAC-SHA256 algorithm se naya signature generate karna
        expected_signature = hmac.new(
            key=secret.encode(),
            msg=body,
            digestmod=hashlib.sha256
        ).hexdigest()

        # Dono ko compare karna (hmac.compare_digest safe hota hai timing attacks se)
        return hmac.compare_digest(expected_signature, signature)

    @classmethod
    async def process_webhook(cls, db, raw_body: bytes, signature: str):
        """
        Ye function router se call hoga.
        """

        # 1. sabse pehela security check
        if not cls.verify_signature(raw_body, signature):
            logger.error("Invalid signature")
            raise Exception("Hacker Attack Attempted")

        logger.info("Signature Verified")

        # 2. Body ko JSON mein convert karna
        data = json.loads(raw_body)
        event_type = data.get("event")

        # 3. Check karna ki konsa event aaya hai
        if event_type == "payment.captured":
            logger.info(" Payment Captured Event Received!")

            payment_entity = data["payload"]["payment"]["entity"]
            razorpay_order_id = payment_entity.get("order_id")


            await cls.handle_payment_success(db, razorpay_order_id, payment_entity)

        elif event_type == "order.paid":
            logger.info(" Order Paid Event Received!")
            # Ye bhi hum handle kar sakte hain future mein

        else:
            logger.info(f"Ignored event: {event_type}")

        return True



    @classmethod
    async def handle_payment_success(cls, db, razorpay_order_id: str, payment_entity: dict):
        """
        Ye function database mein Order aur Transaction ka status update karega.
        """

        # 1. Database se transaction dhundh ke laao jo is razorpay_order_id se juda ho
        stmt = select(Transaction).where(Transaction.razorpay_order_id == razorpay_order_id)
        result = await db.execute(stmt)
        transaction = result.scalar_one_or_none()

        if not transaction:
            logger.error(f"Transaction not found: {razorpay_order_id}")
            return False

        # 🛡THE IDEMPOTENCY CHECK (Duplicate rokna)
        if transaction.status == "SUCCESS":
            logger.info(f"Idempotency: Order {razorpay_order_id} already PAID")
            return True

        # ⚛THE ATOMIC TRANSACTION (Dono update ya ek bhi nahi)
        try:
            # 1. Update Transaction Table
            transaction.status = "SUCCESS"
            transaction.razorpay_payment_id = payment_entity.get("id")

            # 2. Find order table and update status
            order_stmt = select(Order).where(Order.id == transaction.order_id)
            order_result = await db.execute(order_stmt)
            order = order_result.scalar_one_or_none()

            if order:
                order.status = OrderStatus.PAID

            # 3: Dono changes ko ek saath database mein save karo (COMMIT FIRST!)
            await db.commit()
            logger.info(f"Order {order.id} is officially PAID in database.")

            # 4. ONLY AFTER COMMIT - Try to send email (failures won't block payment)
            try:
                if order and order.user_id:
                    user_stmt = select(User).where(User.id == order.user_id)
                    user_result = await db.execute(user_stmt)
                    real_user = user_result.scalar_one_or_none()

                    if real_user and real_user.email:
                        logger.info(f"Queuing invoice email for {real_user.email}")
                        send_invoice_email.delay(
                            user_email=real_user.email,
                            user_id=str(real_user.id),
                            order_id=str(order.id),
                            amount=float(order.total_price)
                        )
                        logger.info(f"✉Celery Task Queued for Order {order.id}")
            except Exception as email_error:
                # Email queue failure - log it but DON'T fail the payment!
                logger.warning(f"⚠️ Email queue failed (payment ALREADY SAVED): {str(email_error)}")

            return True

        except Exception as e:
            await db.rollback()
            logger.error(f"Database update fail ho gaya: {str(e)}")
            raise e