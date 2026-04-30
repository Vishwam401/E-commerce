import json
import logging
from fastapi import APIRouter, Request, Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.webhook_service import RazorpayWebhookService
from app.db.models.webhook_event import WebhookEvent
from app.core.exceptions import BadRequestError, DatabaseError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    raw_body = await request.body()

    if not x_razorpay_signature:
        raise BadRequestError("Signature is missing")

    webhook_log = None

    # Immediate audit logging
    try:
        data = json.loads(raw_body)
        webhook_log = WebhookEvent(
            event_type=data.get("event", "unknown"),
            payload=data,
            processed=False
        )
        db.add(webhook_log)
        await db.commit()
    except Exception as exc:
        logger.error(f"Failed to log webhook event: {exc}")
        await db.rollback()

    # Business logic
    try:
        is_processed = await RazorpayWebhookService.process_webhook(
            db, raw_body, x_razorpay_signature
        )

        if is_processed and webhook_log:
            webhook_log.processed = True
            await db.commit()

        return {"status": "ok"}

    except Exception as exc:
        logger.error(f"Webhook error: {exc}")
        await db.rollback()
        return {"status": "error_logged"}