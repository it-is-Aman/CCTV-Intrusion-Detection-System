"""YOLOv8n person detector.

Wraps the Ultralytics inference API behind a clean, stateless interface.
The caller owns the tracker and all state — this module only performs
frame-level inference.

Design notes:
- Model is loaded once at construction time (expensive).
- ``detect()`` is intentionally synchronous and CPU-bound; the pipeline
  runs it in an executor thread so it doesn't block the event loop.
- Only class 0 (person) detections above the configured threshold are returned.
"""

from __future__ import annotations

import logging

import numpy as np
from ultralytics import YOLO

from app.config import settings

logger = logging.getLogger(__name__)


class Detector:
    """Wraps YOLOv8n and filters detections to the 'person' class."""

    _PERSON_CLASS_ID = 0

    def __init__(self) -> None:
        logger.info("Loading YOLO model: %s", settings.yolo_model)
        self._model = YOLO(settings.yolo_model)
        # Warm-up pass — avoids first-frame latency spike.
        dummy = np.zeros((480, 640, 3), dtype=np.uint8)
        self._model(dummy, verbose=False)
        logger.info("YOLO model loaded and warmed up")

    def detect(self, frame: np.ndarray) -> list[dict]:
        """Run inference on ``frame`` and return person detections.

        Returns
        -------
        list of dicts with keys:
            ``bbox``         — (x1, y1, x2, y2) in pixel coordinates (ints)
            ``confidence``   — float in [0, 1]
        """
        results = self._model(
            frame,
            classes=[self._PERSON_CLASS_ID],
            conf=settings.confidence_threshold,
            verbose=False,
        )

        detections: list[dict] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                xyxy = box.xyxy[0].cpu().numpy().astype(int)
                conf = float(box.conf[0])
                detections.append({"bbox": tuple(xyxy), "confidence": conf})

        return detections
