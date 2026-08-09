"""MJPEG stream + annotation overlay.

``mjpeg_generator`` is an async generator that:
1. Grabs the latest frame from CameraManager.
2. Draws zone overlays and detection boxes (if the pipeline is running).
3. JPEG-encodes the frame.
4. Yields a multipart/x-mixed-replace boundary chunk.

The annotator is intentionally decoupled from the pipeline: it reads shared
state (current zones, latest detections) through lightweight in-memory stores
so the stream can run even if detection is disabled.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncIterator

import cv2
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared annotation state — written by the pipeline, read by the streamer.
# Use a simple dict so there's no circular import.
# ---------------------------------------------------------------------------
_annotation_state: dict = {
    "zones": [],          # list[Zone]
    "detections": [],     # list[TrackedPerson]
}


def update_annotation_state(zones: list, detections: list) -> None:
    """Called by the pipeline each inference cycle to update overlay data."""
    _annotation_state["zones"] = zones
    _annotation_state["detections"] = detections


# ── Colour palette for zone/track overlays ────────────────────────────────────
_ZONE_COLOUR = (0, 200, 100)       # green
_BOX_COLOUR  = (0, 165, 255)       # orange
_TEXT_COLOUR = (255, 255, 255)     # white
_ALERT_COLOUR = (0, 0, 220)        # red (BGR)


def _annotate_frame(frame: np.ndarray) -> np.ndarray:
    """Draw zones and detection boxes onto a copy of ``frame``."""
    out = frame.copy()
    h, w = out.shape[:2]

    zones: list = _annotation_state["zones"]
    detections: list = _annotation_state["detections"]

    # Draw zones ──────────────────────────────────────────────────────────────
    for zone in zones:
        # Convert normalised coords → pixel coords.
        pts_norm: list[list[float]] = zone.points
        pts_px = np.array(
            [[int(p[0] * w), int(p[1] * h)] for p in pts_norm],
            dtype=np.int32,
        )

        if zone.zone_type.value == "polygon" and len(pts_px) >= 3:
            overlay = out.copy()
            cv2.fillPoly(overlay, [pts_px], (*_ZONE_COLOUR, 60))
            cv2.addWeighted(overlay, 0.25, out, 0.75, 0, out)
            cv2.polylines(out, [pts_px], isClosed=True, color=_ZONE_COLOUR, thickness=2)
        elif zone.zone_type.value == "line" and len(pts_px) == 2:
            cv2.line(out, tuple(pts_px[0]), tuple(pts_px[1]), _ZONE_COLOUR, 2)
            # Arrow heads to indicate crossing direction
            mid = pts_px.mean(axis=0).astype(int)
            cv2.putText(out, zone.name, tuple(mid), cv2.FONT_HERSHEY_SIMPLEX, 0.5, _ZONE_COLOUR, 1, cv2.LINE_AA)
        
        # Zone name label for polygons
        if zone.zone_type.value == "polygon" and len(pts_px) >= 1:
            centroid = pts_px.mean(axis=0).astype(int)
            cv2.putText(out, zone.name, tuple(centroid), cv2.FONT_HERSHEY_SIMPLEX, 0.55, _TEXT_COLOUR, 1, cv2.LINE_AA)

    # Draw detections ─────────────────────────────────────────────────────────
    for person in detections:
        x1, y1, x2, y2 = person.bbox
        cv2.rectangle(out, (x1, y1), (x2, y2), _BOX_COLOUR, 2)
        label = f"#{person.track_id}  {person.confidence:.0%}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(out, (x1, y1 - th - 6), (x1 + tw + 4, y1), _BOX_COLOUR, -1)
        cv2.putText(out, label, (x1 + 2, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, _TEXT_COLOUR, 1, cv2.LINE_AA)

    # Timestamp watermark ─────────────────────────────────────────────────────
    ts = time.strftime("%Y-%m-%d  %H:%M:%S")
    cv2.putText(out, ts, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1, cv2.LINE_AA)

    return out


async def mjpeg_generator(camera) -> AsyncIterator[bytes]:
    """Async generator yielding MJPEG boundary chunks at ``stream_fps``."""
    interval = 1.0 / settings.stream_fps
    boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"

    while True:
        t0 = asyncio.get_event_loop().time()

        frame = camera.get_latest_frame()
        if frame is None:
            # Camera not ready yet — send a placeholder black frame.
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "Waiting for camera…", (120, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (100, 100, 100), 2)

        annotated = _annotate_frame(frame)

        ret, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            await asyncio.sleep(interval)
            continue

        yield boundary + buf.tobytes() + b"\r\n"

        elapsed = asyncio.get_event_loop().time() - t0
        sleep_for = interval - elapsed
        if sleep_for > 0:
            await asyncio.sleep(sleep_for)
