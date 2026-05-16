from __future__ import annotations

import uuid
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from jose import JWTError, jwt
from sqlalchemy import select

from app.core.config import settings
from app.core.websocket_manager import manager
from app.core.security import is_token_blacklisted
from app.db.models.order import Order
from app.db.session import async_session_maker
logger = logging.getLogger(__name__)
router = APIRouter()



async def verify_ws_token(token: str) -> uuid.UUID | None:
    """
    Validate JWT from query param.
    Returns user_id UUID if valid, None otherwise.
    """
    try:
        # Step 1: Blacklist check (Redis)
        if await is_token_blacklisted(token):
            logger.warning("[WS] Token blacklisted")
            return None

        # Step 2: Decode JWT
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        # Step 3: Must be access token
        if payload.get("type") != "access":
            logger.warning(f"[WS] Wrong token type: {payload.get('type')}")
            return None

        # Step 4: Extract and convert subject to UUID
        subject = payload.get("sub")
        if not subject:
            return None

        return uuid.UUID(subject)

    except (JWTError, ValueError):
        return None


@router.websocket("/orders/{order_id}")
async def order_status_websocket(
    websocket: WebSocket,
    order_id: str,
    token: str = Query(..., description="JWT access token from query param"),
):
    """
    WebSocket endpoint for real-time order status updates.

    Flow:
        1. Auth     — JWT validate karo (no DB)
        2. UUID     — order_id format validate karo (no DB)
        3. Authz    — order ownership check karo (short DB session, then close)
        4. Connect  — long-lived WS loop (no DB at all)
    """

    # ─── PHASE 1: AUTH (no DB) ───────────────────────────────────────────────
    user_id = await verify_ws_token(token)
    if not user_id:
        await websocket.accept()
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

    # ─── PHASE 2: UUID VALIDATION (no DB) ────────────────────────────────────
    try:
        order_uuid = uuid.UUID(order_id)
    except ValueError:
        await websocket.accept()
        await websocket.close(code=1008, reason="Invalid order ID format")
        return

    # ─── PHASE 3: AUTHORIZATION (short DB session) ───────────────────────────
    # Session yahan open hoti hai aur is block ke baad immediately close ho
    # jaati hai — long-lived WS loop mein koi DB session nahi rehti.
    try:
        async with async_session_maker() as db:
            result = await db.execute(
                select(Order).where(
                    Order.id == order_uuid,
                    Order.user_id == user_id,
                )
            )
            if not result.scalar_one_or_none():
                await websocket.accept()
                await websocket.close(
                    code=1008,
                    reason="Order not found or unauthorized",
                )
                return

    except Exception as e:
        logger.error(f"[WS] DB auth error | order={order_id} | err={e}")
        await websocket.accept()
        await websocket.close(code=1011, reason="Internal server error")
        return

    # ─── PHASE 4: CONNECTION (no DB from here onwards) ───────────────────────
    await manager.connect(order_id, websocket)
    logger.info(f"[WS] Connected | order={order_id} | user={user_id}")

    try:
        while True:
            # Connection alive rakhne ke liye receive karte rehte hain.
            # Client "ping" bhej sakta hai — hum "pong" reply karte hain.
            data = await websocket.receive_text()

            if data.strip() == "ping":
                await websocket.send_text('{"type":"pong"}')

    except WebSocketDisconnect:
        manager.disconnect(order_id, websocket)
        logger.info(f"[WS] Disconnected | order={order_id} | user={user_id}")

    except Exception as e:
        logger.error(f"[WS] Loop error | order={order_id} | err={e}")
        manager.disconnect(order_id, websocket)
