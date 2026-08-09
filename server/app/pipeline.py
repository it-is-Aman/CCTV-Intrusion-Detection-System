"""Detection pipeline — the main background async task.

Owns Detector, PersonTracker, ZoneEngine, and EvidenceWriter.
Runs a tight async loop that:
1. Samples a frame from the camera at ``inference_fps``.
2. Runs YOLO inference + ByteTrack in a thread executor (CPU-bound).
3. Updates the ZoneEngine and collects any crossing events.
4. For each event: persists to SQLite, fires evidence collection (async),
   broadcasts the alert over WebSocket.
5. Updates the annotation state for the MJPEG stream.

Design decisions:
- The pipeline is an asyncio task — it yields at every I/O point so the
  event loop remains responsive.
- Zones are reloaded from DB every ``zone_reload_interval`` seconds so new
  zones appear in detection without restarting the server.
- Evidence stitching runs as a separate, non-awaited task so it never blocks
  the main pipeline loop.
"""

from __future__ import annotations

import asyncio
import logging
import time

import app.database as db
from app.camera import CameraManager
from app.config import settings
from app.detector import Detector
from app.evidence import EvidenceWriter
from app.models import CrossingEvent
from app.stream import update_annotation_state
from app.tracker import PersonTracker
from app.ws_manager import ws_manager
from app.zone_engine import ZoneEngine

logger = logging.getLogger(__name__)

_ZONE_RELOAD_INTERVAL = 5.0  # seconds


class DetectionPipeline:
    """Runs the full detection pipeline as an asyncio background task."""

    def __init__(self, camera: CameraManager) -> None:
        self._camera = camera
        self._detector = Detector()
        self._tracker = PersonTracker()
        self._evidence = EvidenceWriter()
        self._zone_engine: ZoneEngine | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Load initial zones and start the pipeline loop."""
        zones = await db.list_zones()
        self._zone_engine = ZoneEngine(zones)
        self._task = asyncio.create_task(self._run(), name="detection-pipeline")
        logger.info("Detection pipeline started")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Detection pipeline stopped")

    # ── Main loop ─────────────────────────────────────────────────────────────

    async def _run(self) -> None:
        inference_interval = 1.0 / settings.inference_fps
        last_zone_reload = 0.0

        while True:
            loop_start = asyncio.get_event_loop().time()

            # ── Reload zones periodically ─────────────────────────────────
            if loop_start - last_zone_reload > _ZONE_RELOAD_INTERVAL:
                zones = await db.list_zones()
                if self._zone_engine is not None:
                    self._zone_engine.update_zones(zones)
                last_zone_reload = loop_start

            # ── Grab frame ────────────────────────────────────────────────
            frame = self._camera.get_latest_frame()
            if frame is None:
                await asyncio.sleep(0.05)
                continue

            # ── Run inference (CPU-bound → executor) ──────────────────────
            raw_detections = await asyncio.to_thread(self._detector.detect, frame)
            tracked_persons = await asyncio.to_thread(
                self._tracker.update, raw_detections, frame
            )

            # ── Zone crossing detection ───────────────────────────────────
            events: list[CrossingEvent] = []
            if self._zone_engine is not None:
                h, w = frame.shape[:2]
                events = self._zone_engine.update(
                    tracked_persons, w, h, self._tracker
                )

            # ── Update MJPEG annotation overlay ──────────────────────────
            zones = self._zone_engine._zones if self._zone_engine else []
            update_annotation_state(zones, tracked_persons)

            # ── Handle crossing events ────────────────────────────────────
            for event in events:
                asyncio.create_task(
                    self._handle_event(event, frame),
                    name=f"event-{event.id[:8]}",
                )

            # ── Pace the loop ────────────────────────────────────────────
            elapsed = asyncio.get_event_loop().time() - loop_start
            sleep_for = inference_interval - elapsed
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)

    async def _handle_event(self, event: CrossingEvent, trigger_frame) -> None:
        """Persist event, save evidence, and broadcast WebSocket alert."""
        try:
            # 1. Persist to DB immediately (without evidence paths yet).
            await db.insert_event(event)

            # 2. Broadcast alert immediately — don't wait for evidence files.
            await ws_manager.broadcast({
                "type": "crossing",
                "event": event.to_dict(),
            })
            logger.info(
                "Alert: zone=%s track=%d event=%s",
                event.zone_name, event.track_id, event.id
            )

            # 3. Save evidence asynchronously.
            snapshot_path = await self._evidence.save_snapshot(trigger_frame, event.id)

            pre_frames = self._camera.get_ring_buffer_snapshot()
            clip_path = await self._evidence.stitch_clip(
                pre_frames, self._camera, event.id
            )

            # 4. Update DB with evidence paths.
            await db.update_event_paths(
                event.id,
                str(snapshot_path),
                str(clip_path),
            )

        except Exception:
            logger.exception("Error handling event %s", event.id)
