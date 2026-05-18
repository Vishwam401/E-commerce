import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.worker.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, name="send_notification_email")
def send_notification_email(
    self,
    to_email: str,
    subject: str,
    template_name: str,
    context: dict,
):
    """
    Generic notification email sender with linear-backoff retry logic.

    bind=True      → self milta hai taaki self.retry() call kar sakein
    max_retries=3  → SMTP down ho toh 3 baar try karega
    countdown      → FIX (Bug 3): ab actual linear backoff hai:
                     attempt 1 → 60s, attempt 2 → 120s, attempt 3 → 180s

    template_name → context dict ke variables fill karke HTML banata hai.
    Jinja2 use karo agar templates zyada complex ho jaayein —
    abhi simple string format kaafi hai.

    Args:
        to_email:      Recipient email address
        subject:       Email subject line
        template_name: NotificationType value string (e.g. "order.shipped")
        context:       Dict with template variables (order_id_short, new_status, etc.)
    """
    try:
        html_content = _render_notification_template(template_name, context)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.MAIL_FROM
        msg["To"] = to_email
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT) as server:
            if settings.MAIL_STARTTLS:
                server.starttls()
            server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            server.send_message(msg)

        logger.info(f"[EMAIL] Sent | to={to_email} | subject={subject}")
        return {"status": "sent", "to": to_email}

    except Exception as exc:
        retry_count = self.request.retries

        if retry_count < self.max_retries:

            countdown = 60 * (retry_count + 1)
            logger.warning(
                f"[EMAIL] Failed (attempt {retry_count + 1}/{self.max_retries}) | "
                f"to={to_email} | err={exc} | retrying in {countdown}s..."
            )
            raise self.retry(exc=exc, countdown=countdown)



        logger.error(
            f"[EMAIL] PERMANENT FAIL | to={to_email} | subject={subject} | err={exc}"
        )
        raise


# ── Private: Template Renderer ─────────────────────────────────────────────────

def _render_notification_template(template_name: str, context: dict) -> str:

    order_id_short = context.get("order_id_short", "")
    old_status     = context.get("old_status", "")
    new_status     = context.get("new_status", "")
    total_price    = context.get("total_price", "")
    updated_at     = context.get("updated_at", "")
    username       = context.get("username", "Customer")
    payment_id     = context.get("payment_id", "")
    amount         = context.get("amount", total_price)

    # Status ke hisaab se badge color
    status_colors = {
        "paid":       "#4CAF50",
        "processing": "#2196F3",
        "shipped":    "#FF9800",
        "delivered":  "#4CAF50",
        "cancelled":  "#F44336",
    }
    badge_color = status_colors.get(new_status.lower(), "#888888")

    base_style = """
        font-family: Arial, sans-serif;
        max-width: 600px;
        margin: auto;
        border: 1px solid #ddd;
        padding: 20px;
        border-radius: 8px;
    """

    if template_name == "payment.confirmed":
        return f"""
        <div style="{base_style}">
            <div style="text-align: center; margin-bottom: 20px;">
                <h2 style="color: #2e6c80; margin: 0;">Pro-Commerce</h2>
                <p style="color: #888; font-size: 14px; margin: 5px 0;">Payment Receipt</p>
            </div>
            <h3 style="color: #4CAF50; text-align: center;">Payment Successful! 🎉</h3>
            <p>Hi {username},</p>
            <p>Thank you for shopping with us. We have successfully received your payment of <strong>₹{amount}</strong>.</p>
            <hr style="border-top: 1px dashed #ccc; margin: 20px 0;">
            <h4 style="margin-bottom: 10px;">Order Details:</h4>
            <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd; background-color: #f9f9f9;"><strong>Order ID</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{order_id_short}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd; background-color: #f9f9f9;"><strong>Payment ID</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{payment_id}</td>
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

    if template_name == "order.cancelled":
        return f"""
        <div style="{base_style}">
            <h2 style="color: #F44336; text-align: center;">Order Cancelled</h2>
            <p>Hi {username},</p>
            <p>Your order <strong>#{order_id_short}</strong> has been cancelled.</p>
            <p>Refund will be processed within 5-7 business days.</p>
            <hr style="border-top: 1px solid #eee; margin: 20px 0;">
            <p style="font-size: 12px; color: #888; text-align: center;">
                This is an automated message. Please do not reply.
            </p>
        </div>
        """

    if template_name == "order.shipped":
        return f"""
        <div style="{base_style}">
            <h2 style="color: #FF9800; text-align: center;">Order Shipped!</h2>
            <p>Hi {username},</p>
            <p>Your order <strong>#{order_id_short}</strong> has been shipped and is on its way!</p>
            <p><strong>Total:</strong> ₹{total_price}</p>
            <hr style="border-top: 1px solid #eee; margin: 20px 0;">
            <p style="font-size: 12px; color: #888; text-align: center;">
                This is an automated message. Please do not reply.
            </p>
        </div>
        """

    if template_name == "order.delivered":
        return f"""
        <div style="{base_style}">
            <h2 style="color: #4CAF50; text-align: center;">Order Delivered!</h2>
            <p>Hi {username},</p>
            <p>Your order <strong>#{order_id_short}</strong> has been delivered successfully.</p>
            <p>We hope you enjoy your purchase!</p>
            <hr style="border-top: 1px solid #eee; margin: 20px 0;">
            <p style="font-size: 12px; color: #888; text-align: center;">
                This is an automated message. Please do not reply.
            </p>
        </div>
        """

    # Default: generic status update (order.status_update ya koi bhi unknown type)
    return f"""
    <div style="{base_style}">
        <h2 style="color: #2e6c80; text-align: center;">Order Update</h2>
        <p>Hi {username},</p>
        <p>Your order <strong>#{order_id_short}</strong> status has been updated.</p>
        <div style="
            background: {badge_color};
            color: white;
            padding: 12px;
            text-align: center;
            font-size: 16px;
            font-weight: bold;
            border-radius: 5px;
            margin: 16px 0;
        ">
            {old_status.upper()} → {new_status.upper()}
        </div>
        <p><strong>Total:</strong> ₹{total_price}</p>
        <p><strong>Updated at:</strong> {updated_at}</p>
        <hr style="border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; color: #888; text-align: center;">
            This is an automated message. Please do not reply.
        </p>
    </div>
    """