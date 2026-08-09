"""Stream + WebSocket routes.

GET  /stream  — MJPEG live feed
GET  /ws      — WebSocket for real-time alert push
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from app.stream import mjpeg_generator
from app.ws_manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["stream"])


@router.get("/stream")
async def video_stream(request: Request) -> StreamingResponse:
    """MJPEG live webcam stream with annotation overlays."""
    camera = request.app.state.camera

    return StreamingResponse(
        mjpeg_generator(camera),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.websocket("/ws")
async def websocket_alerts(websocket: WebSocket) -> None:
    """WebSocket endpoint — pushes JSON alert messages to connected clients."""
    await ws_manager.connect(websocket)
    try:
        # Keep the connection alive; we only push from the pipeline side.
        # Client can send pings or any message to keep the connection alive.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as exc:
        logger.warning("WebSocket error: %s", exc)
        await ws_manager.disconnect(websocket)
