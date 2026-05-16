# app/core/websocket_manager.py

from __future__ import annotations

import json
import logging
from typing import Dict, List

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class OrderConnectionManager:
    """
    Room-based WebSocket manager for real-time order status updates.

    Architecture:
    - One "room" per order_id (str)
    - Multiple clients can join the same room (e.g., user has 3 tabs open)
    - Broadcast sends to ALL connections in that room
    - Dead connections are cleaned up automatically during broadcast
    """

    def __init__(self) -> None:
        # Dict[order_id, List[WebSocket]]
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, order_id: str, websocket: WebSocket) -> None:
        """Accept connection and add to order room."""
        await websocket.accept()

        if order_id not in self.active_connections:
            self.active_connections[order_id] = []

        self.active_connections[order_id].append(websocket)

        logger.info(
            f"[WS] Connected | order={order_id} | "
            f"room_size={len(self.active_connections[order_id])}"
        )

    def disconnect(self, order_id: str, websocket: WebSocket) -> None:
        """Remove connection from room. Delete room if empty to prevent memory leak."""
        if order_id not in self.active_connections:
            return

        try:
            self.active_connections[order_id].remove(websocket)

            # If room is empty, delete the key entirely (memory cleanup)
            if not self.active_connections[order_id]:
                del self.active_connections[order_id]
                logger.info(f"[WS] Room deleted | order={order_id} (empty)")

        except ValueError:
            # Connection already removed (race condition)
            pass

    async def broadcast_to_order(self, order_id: str, message: dict) -> None:
        """
        Broadcast JSON message to all clients in the order room.
        Non-blocking: dead connections are silently removed.
        """
        if order_id not in self.active_connections:
            logger.debug(f"[WS] No active connections | order={order_id}")
            return

        dead_connections: List[WebSocket] = []
        payload = json.dumps(message, default=str)  # Handles datetime/UUID safely

        for connection in self.active_connections[order_id]:
            try:
                await connection.send_text(payload)
            except (RuntimeError, WebSocketDisconnect):
                # RuntimeError = connection closed but object still referenced
                dead_connections.append(connection)
            except Exception as e:
                logger.warning(f"[WS] Send failed | order={order_id} | err={e}")
                dead_connections.append(connection)

        # Cleanup dead connections after iteration (safe removal)
        for dead in dead_connections:
            self.disconnect(order_id, dead)

        if dead_connections:
            logger.info(
                f"[WS] Cleaned {len(dead_connections)} dead conns | order={order_id}"
            )


# Global singleton — import this instance everywhere
manager = OrderConnectionManager()