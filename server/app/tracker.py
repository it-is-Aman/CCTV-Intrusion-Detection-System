"""Person tracker — wraps supervision's ByteTrack implementation.

Takes raw YOLO detections each frame and assigns stable ``track_id`` values
to each person across frames.  Centroid history is maintained here so the
ZoneEngine can do line-crossing direction tests.

Design:
- ``supervision.ByteTrack`` is the same tracker used in Ultralytics production
  pipelines — identical semantics to what the enterprise system will use.
- ``update()`` is synchronous and CPU-bound; run in executor if needed.
- Centroid history is capped at 30 entries to avoid unbounded growth.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque

import numpy as np
import supervision as sv

from app.models import TrackedPerson

logger = logging.getLogger(__name__)

_CENTROID_HISTORY_LEN = 30


class PersonTracker:
    """Wraps ByteTrack and exposes a simple update interface."""

    def __init__(self) -> None:
        self._tracker = sv.ByteTrack()
        # track_id -> deque of (x, y) centroids, oldest first
        self.centroid_history: dict[int, deque[tuple[float, float]]] = defaultdict(
            lambda: deque(maxlen=_CENTROID_HISTORY_LEN)
        )

    def update(self, detections: list[dict], frame: np.ndarray) -> list[TrackedPerson]:
        """Update tracker with new detections and return tracked persons.

        Parameters
        ----------
        detections:
            Output of ``Detector.detect()`` — list of bbox+confidence dicts.
        frame:
            The current video frame (used by supervision for internal state).

        Returns
        -------
        List of ``TrackedPerson`` with stable track IDs.
        """
        if not detections:
            return []

        xyxy = np.array([d["bbox"] for d in detections], dtype=np.float32)
        confs = np.array([d["confidence"] for d in detections], dtype=np.float32)
        class_ids = np.zeros(len(detections), dtype=int)

        sv_detections = sv.Detections(
            xyxy=xyxy,
            confidence=confs,
            class_id=class_ids,
        )

        tracked = self._tracker.update_with_detections(sv_detections)

        results: list[TrackedPerson] = []
        for i in range(len(tracked)):
            bbox = tuple(tracked.xyxy[i].astype(int))  # (x1,y1,x2,y2)
            track_id = int(tracked.tracker_id[i])
            conf = float(tracked.confidence[i]) if tracked.confidence is not None else 1.0

            person = TrackedPerson(track_id=track_id, bbox=bbox, confidence=conf)
            self.centroid_history[track_id].append(person.centroid)
            results.append(person)

        return results

    def get_previous_centroid(self, track_id: int) -> tuple[float, float] | None:
        """Return the second-to-last centroid for a track (for line-crossing tests)."""
        history = self.centroid_history.get(track_id)
        if history is None or len(history) < 2:
            return None
        return history[-2]
