# app/worker/tasks.py
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.worker.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, name="send_invoice_email")
def send_invoice_email(self, user_email: str, user_id: str, order_id: str, amount: float):
    logger.info(f"Celery Task: Preparing Invoice for Order {order_id} to {user_email}")

    try:
        # THE HTML INVOICE TEMPLATE (User ID aur Order ID ke sath)
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #ddd; padding: 20px; border-radius: 8px;">
            <div style="text-align: center; margin-bottom: 20px;">
                <h2 style="color: #2e6c80; margin: 0;">Pro-Commerce</h2>
                <p style="color: #888; font-size: 14px; margin: 5px 0;">Payment Receipt</p>
            </div>

            <h3 style="color: #4CAF50; text-align: center;">Payment Successful! 🎉</h3>
            <p>Hi there,</p>
            <p>Thank you for shopping with us. We have successfully received your payment of <strong>₹{amount}</strong>.</p>

            <hr style="border-top: 1px dashed #ccc; margin: 20px 0;">

            <h4 style="margin-bottom: 10px;">Order Details:</h4>
            <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd; background-color: #f9f9f9;"><strong>Order ID</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{order_id}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd; background-color: #f9f9f9;"><strong>User ID</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{user_id}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd; background-color: #f9f9f9;"><strong>Total Amount Paid</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd; color: #4CAF50; font-weight: bold;">₹{amount}</td>
                </tr>
            </table>

            <p style="margin-top: 20px; font-size: 14px;">Your order is currently <strong>Processing</strong>. We will notify you once it is shipped!</p>

            <hr style="border-top: 1px solid #eee; margin: 20px 0;">
            <p style="font-size: 12px; color: #888; text-align: center;">
                This is an automated email. Please do not reply directly to this message.
            </p>
        </div>
        """

        # EMAIL SENDING LOGIC (Synchronous & Celery Safe)
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Payment Receipt - Order #{order_id[-6:]}"  # Order ID ke last 6 chars

        # .env se MAIL_FROM aur username fetch kar rahe hain
        msg["From"] = settings.MAIL_FROM
        msg["To"] = user_email

        # HTML attach karna
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT) as server:
            # TLS check
            if settings.MAIL_STARTTLS:
                server.starttls()  # Secure connection

            # Login with MAIL_USERNAME and MAIL_PASSWORD from settings
            server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            server.send_message(msg)

        logger.info(f"Celery Task: HTML Invoice successfully SENT to {user_email}")
        return True

    except Exception as exc:
        logger.error(f"Celery Task Failed to send invoice to {user_email}. Error: {exc}")
        # Agar net chala gaya ya SMTP down hai, toh 60 seconds baad khud retry karega
        raise self.retry(exc=exc, countdown=60)