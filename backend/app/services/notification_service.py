from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class NotificationChannel(str, Enum):
    EMAIL     = "email"
    WEBSOCKET = "websocket"


class NotificationType(str, Enum):
    ORDER_STATUS_UPDATE = "order.status_update"
    PAYMENT_CONFIRMED   = "payment.confirmed"
    ORDER_CANCELLED     = "order.cancelled"
    ORDER_SHIPPED       = "order.shipped"
    ORDER_DELIVERED     = "order.delivered"


@dataclass
class NotificationPayload:
    user_id:           str
    user_email:        Optional[str]
    order_id:          str
    notification_type: NotificationType
    data:              dict                  = field(default_factory=dict)
    channels:          list[NotificationChannel] = field(default_factory=list)


class NotificationService:

    @staticmethod
    async def dispatch(payload: NotificationPayload) -> None:
        payload.data.setdefault("order_id_short", payload.order_id[:8])

        logger.info(
            f"[NOTIFY] Dispatching | type={payload.notification_type.value} | "
            f"order={payload.order_id[:8]} | channels={[c.value for c in payload.channels]}"
        )

        # ── EMAIL CHANNEL ──────────────────────────────────────────────────────

        if NotificationChannel.EMAIL in payload.channels and payload.user_email:
            try:
                from app.worker.tasks import send_notification_email

                send_notification_email.delay(
                    to_email=payload.user_email,
                    subject=_get_email_subject(payload),
                    template_name=payload.notification_type.value,
                    context=payload.data,
                )
                logger.debug(f"[NOTIFY] Email queued | to={payload.user_email}")

            except Exception as e:
                logger.error(f"[NOTIFY] Email queue failed: {e}")

        # ── WEBSOCKET CHANNEL ──────────────────────────────────────────────────

        if NotificationChannel.WEBSOCKET in payload.channels:
            try:
                from app.core.websocket_manager import manager

                await manager.broadcast_to_order(
                    order_id=payload.order_id,
                    message={
                        "event":     payload.notification_type.value,
                        "data":      payload.data,
                        "timestamp": _now_iso(),
                    },
                )
                logger.debug(f"[NOTIFY] WS broadcast done | order={payload.order_id[:8]}")

            except Exception as e:
                logger.error(f"[NOTIFY] WS broadcast failed: {e}")

        logger.info(f"[NOTIFY] Dispatch complete | order={payload.order_id[:8]}")


# ── Private Helpers ────────────────────────────────────────────────────────────

def _get_email_subject(payload: NotificationPayload) -> str:
    subjects = {
        NotificationType.ORDER_STATUS_UPDATE: f"Order #{payload.order_id[:8]} Status Updated",
        NotificationType.PAYMENT_CONFIRMED:   f"Payment Confirmed - Order #{payload.order_id[:8]}",
        NotificationType.ORDER_CANCELLED:     f"Order #{payload.order_id[:8]} Cancelled",
        NotificationType.ORDER_SHIPPED:       f"Order #{payload.order_id[:8]} Shipped!",
        NotificationType.ORDER_DELIVERED:     f"Order #{payload.order_id[:8]} Delivered!",
    }
    return subjects.get(payload.notification_type, "Notification")


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()