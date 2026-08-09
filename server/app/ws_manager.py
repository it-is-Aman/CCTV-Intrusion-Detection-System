"""WebSocket connection manager — fan-out broadcast to all connected clients.

Keeps a set of active WebSocket connections and provides a thread-safe
``broadcast`` coroutine.  Dead connections are silently removed so the
pipeline never needs to manage individual connections.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections and fans out alert messages."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.info("WS client connected  (total=%d)", len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)
        logger.info("WS client disconnected (total=%d)", len(self._connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send ``message`` as JSON to all connected clients.

        Dead connections are silently removed — callers must not rely on
        delivery guarantees (fire-and-forget semantics).
        """
        if not self._connections:
            return

        dead: set[WebSocket] = set()

        async with self._lock:
            targets = list(self._connections)

        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)

        if dead:
            async with self._lock:
                self._connections -= dead
            logger.debug("Removed %d dead WS connection(s)", len(dead))


# Singleton used by routes and pipeline.
ws_manager = ConnectionManager()
