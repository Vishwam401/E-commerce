from hashlib import sha256
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, StringConstraints

from app.core.security import redis_client
from app.utils.email import send_contact_email

router = APIRouter()

TOPICS = {
    "demo": "Demo request",
    "growth": "Growth plan",
    "enterprise": "Enterprise and integrations",
    "support": "Platform support",
    "security": "Security report",
    "other": "General inquiry",
}


class ContactRequest(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
    email: EmailStr
    topic: Literal["demo", "growth", "enterprise", "support", "security", "other"]
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)]


@router.post("/contact", status_code=status.HTTP_204_NO_CONTENT)
async def submit_contact(data: ContactRequest, request: Request) -> None:
    host = request.client.host if request.client else "unknown"
    network_key = f"contact:network:{host}"
    # The transaction preserves the expiry under parallel requests.
    async with redis_client.pipeline() as pipeline:
        attempts, _ = await pipeline.incr(network_key).expire(network_key, 60, nx=True).execute()
    if attempts > 30:
        raise HTTPException(status_code=429, detail="Too many contact requests. Try again in a minute.")

    sender_hash = sha256(data.email.casefold().encode()).hexdigest()
    if not await redis_client.set(f"contact:sender:{sender_hash}", 1, ex=60, nx=True):
        raise HTTPException(status_code=429, detail="Please wait a minute before sending another message.")

    await send_contact_email(data.name, data.email, TOPICS[data.topic], data.message)
