"""Camera manager — OpenCV capture loop running in a dedicated background thread.

Design:
- A single daemon thread owns the ``cv2.VideoCapture`` object (OpenCV is not
  thread-safe for concurrent reads from the same device).
- A ``threading.Lock`` guards all shared state.
- The ``ring_buffer`` (``collections.deque``) holds the last N raw frames so
  that EvidenceWriter can stitch pre-event context into clips.
- ``get_latest_frame()`` is O(1) and never blocks.
- ``is_running`` can be polled to detect camera failures.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Optional

import cv2
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


class CameraManager:
    """Manages a single webcam capture loop in a background thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._ring_buffer: deque[np.ndarray] = deque(
            maxlen=settings.ring_buffer_seconds * settings.capture_fps
        )
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.is_running = False
        self.frame_width: int = 640
        self.frame_height: int = 480

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the capture thread.  Safe to call once at app startup."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("CameraManager already running — ignoring start()")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._capture_loop,
            name="camera-capture",
            daemon=True,
        )
        self._thread.start()
        logger.info("CameraManager started (device=%d)", settings.camera_device)

    def stop(self) -> None:
        """Signal the capture thread to stop and wait for it."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self.is_running = False
        logger.info("CameraManager stopped")

    # ── Frame access ──────────────────────────────────────────────────────────

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Return the most recent raw frame (thread-safe, non-blocking)."""
        with self._lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    def get_ring_buffer_snapshot(self) -> list[np.ndarray]:
        """Return a shallow copy of the ring buffer as a list (oldest → newest)."""
        with self._lock:
            return list(self._ring_buffer)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _capture_loop(self) -> None:
        cap = cv2.VideoCapture(settings.camera_device)
        if not cap.isOpened():
            logger.error("Failed to open camera device %d", settings.camera_device)
            return

        # Hint at desired resolution; actual resolution depends on hardware.
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, settings.capture_fps)

        self.frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.is_running = True

        target_interval = 1.0 / settings.capture_fps

        try:
            while not self._stop_event.is_set():
                loop_start = time.monotonic()

                ret, frame = cap.read()
                if not ret:
                    logger.warning("Camera read failed — retrying…")
                    time.sleep(0.1)
                    continue

                with self._lock:
                    self._latest_frame = frame
                    self._ring_buffer.append(frame)

                # Pace the loop to avoid burning CPU at max speed.
                elapsed = time.monotonic() - loop_start
                sleep_for = target_interval - elapsed
                if sleep_for > 0:
                    time.sleep(sleep_for)
        finally:
            cap.release()
            self.is_running = False
            logger.info("Capture loop exited")
