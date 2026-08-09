"""Evidence writer — saves snapshots and stitches ring-buffer clips.

Design:
- All disk I/O is synchronous OpenCV/aiofiles operations, run in an
  executor thread via ``asyncio.to_thread`` so they never block the loop.
- ``save_snapshot`` writes a JPEG immediately from the trigger frame.
- ``stitch_clip`` combines ring-buffer pre-event frames with post-event
  frames collected from the camera after the alert fires, then writes MP4.
- Both methods return the path they wrote so the caller can persist it.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import cv2
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

# Ensure storage directories exist.
settings.snapshots_dir.mkdir(parents=True, exist_ok=True)
settings.clips_dir.mkdir(parents=True, exist_ok=True)


class EvidenceWriter:
    """Handles snapshot and clip writing for crossing events."""

    async def save_snapshot(self, frame: np.ndarray, event_id: str) -> Path:
        """Write a JPEG snapshot and return its path."""
        path = settings.snapshots_dir / f"{event_id}.jpg"
        await asyncio.to_thread(self._write_jpeg, frame, path)
        logger.info("Snapshot saved: %s", path)
        return path

    async def stitch_clip(
        self,
        pre_frames: list[np.ndarray],
        camera,
        event_id: str,
    ) -> Path:
        """Collect post-event frames then write a complete MP4 clip.

        Parameters
        ----------
        pre_frames:
            Ring-buffer snapshot taken at the moment of the alert
            (contains pre-event context).
        camera:
            Active ``CameraManager`` — used to collect post-event frames.
        event_id:
            Used to name the output file.
        """
        path = settings.clips_dir / f"{event_id}.mp4"

        # Collect post-event frames (blocking sleep in thread).
        post_frames = await asyncio.to_thread(
            self._collect_post_frames, camera
        )

        all_frames = pre_frames + post_frames
        if not all_frames:
            logger.warning("No frames available for clip %s", event_id)
            return path

        await asyncio.to_thread(self._write_mp4, all_frames, path)
        logger.info("Clip saved: %s  (%d frames)", path, len(all_frames))
        return path

    # ── Thread-safe synchronous helpers ──────────────────────────────────────

    @staticmethod
    def _write_jpeg(frame: np.ndarray, path: Path) -> None:
        cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])

    @staticmethod
    def _collect_post_frames(camera) -> list[np.ndarray]:
        """Sleep for post_seconds then return frames added since now."""
        frames: list[np.ndarray] = []
        deadline = time.monotonic() + settings.clip_post_seconds
        while time.monotonic() < deadline:
            frame = camera.get_latest_frame()
            if frame is not None:
                frames.append(frame)
            time.sleep(1.0 / settings.capture_fps)
        return frames

    @staticmethod
    def _write_mp4(frames: list[np.ndarray], path: Path) -> None:
        if not frames:
            return
        h, w = frames[0].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(path), fourcc, settings.capture_fps, (w, h))
        try:
            for frame in frames:
                if frame.shape[:2] == (h, w):
                    writer.write(frame)
        finally:
            writer.release()
