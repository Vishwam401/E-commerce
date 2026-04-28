from fastapi import APIRouter, Request, Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from app.db.session import get_db
from app.services.webhook_service import RazorpayWebhookService

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/razorpay")
async def razorpay_webhook(
        request: Request,
        x_razorpay_signature: str = Header(None),
        db: AsyncSession = Depends(get_db)
):
    """
        Razorpay Webhook Handler
        Ye function Razorpay se aane wale saare events (payment.captured etc.) ko receive karega.
    """

    #1. Raw body uthanya (pydantic use nai kre idhr)
    raw_body = await request.body()

    #2. check krna ki siganture aya ya naii
    if not x_razorpay_signature:
        logger.warning("Webhook pe bina signature ki request aayi!")
        raise HTTPException(status_code=400, detail="Signature is missing")

    try:
        await RazorpayWebhookService.process_webhook(
            db=db,
            raw_body=raw_body,
            signature=x_razorpay_signature
        )
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook process karte time error agi: {str(e)}")
        return {"status": "error_logged"}
