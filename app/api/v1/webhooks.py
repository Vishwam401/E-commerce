import json
import logging
from fastapi import APIRouter, Request, Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.webhook_service import RazorpayWebhookService
from app.db.models.webhook_event import WebhookEvent

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
        raise HTTPException(status_code=400, detail="Signature is missing")

    # Red lines avoid karne ke liye default None assign kar diya
    webhook_log = None

    # 1. IMMEDIATE AUDIT LOGGING
    try:
        data = json.loads(raw_body)
        webhook_log = WebhookEvent(
            event_type=data.get("event", "unknown"),
            payload=data,
            processed=False
        )
        db.add(webhook_log)
        await db.commit()  # Save NOW!
    except Exception as e:
        logger.error(f"Failed to log webhook event: {e}")
        await db.rollback()

        # 2. BUSINESS LOGIC
    try:
        # Yahan humne result ko 'is_processed' naam de diya taaki 'success' wala confusion hi khatam ho jaye
        is_processed = await RazorpayWebhookService.process_webhook(db, raw_body, x_razorpay_signature)

        # 3. MARK AS PROCESSED
        if is_processed and webhook_log:
            webhook_log.processed = True
            await db.commit()

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        await db.rollback()
        return {"status": "error_logged"}
