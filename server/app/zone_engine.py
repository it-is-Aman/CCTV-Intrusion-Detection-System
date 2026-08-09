"""Zone engine — pure, stateless crossing-detection logic.

This module contains ZERO I/O.  It takes zones and tracked persons as inputs,
maintains per-track-per-zone state, and returns only *new* crossing events.
This design makes it trivially unit-testable without mocking any I/O.

Crossing semantics
------------------
Polygon zones
    A person is "inside" when their centroid is within the polygon.
    A crossing fires when a person transitions from outside→inside.
    Debounce: they must be inside for ``debounce_frames`` consecutive frames
    before the event fires (prevents flicker at the boundary).

Line / tripwire zones
    A crossing fires when the signed distance from the line changes sign
    between the previous and current centroid (i.e. the centroid crossed
    the infinite line).  No debounce needed — line crossings are discrete.

Coordinate system
-----------------
All coordinates are in *pixel* space (absolute, not normalised).
The pipeline is responsible for converting normalised zone points to pixels
before calling ``update()``.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime

from shapely.geometry import Point, Polygon

from app.config import settings
from app.models import CrossingEvent, TrackedPerson, Zone, ZoneType

logger = logging.getLogger(__name__)


class ZoneEngine:
    """Stateful crossing detector for a set of zones.

    State is per-(track_id, zone_id) and is not persisted — it resets when
    the engine is recreated (e.g. on server restart).
    """

    def __init__(self, zones: list[Zone]) -> None:
        self._zones = zones
        # (track_id, zone_id) -> consecutive "inside" frame count
        self._inside_count: dict[tuple[int, str], int] = defaultdict(int)
        # (track_id, zone_id) -> True if event has already fired for this entry
        self._fired: dict[tuple[int, str], bool] = defaultdict(bool)

    def update_zones(self, zones: list[Zone]) -> None:
        """Hot-reload zones without resetting per-track state."""
        self._zones = zones

    def update(
        self,
        tracked_persons: list[TrackedPerson],
        frame_width: int,
        frame_height: int,
        tracker,  # PersonTracker — passed in to access centroid history
    ) -> list[CrossingEvent]:
        """Process one frame and return any new crossing events.

        Parameters
        ----------
        tracked_persons:
            Current frame's tracked persons (pixels).
        frame_width / frame_height:
            Used to convert normalised zone points to pixel coordinates.
        tracker:
            The active PersonTracker (for previous-centroid lookup on lines).
        """
        events: list[CrossingEvent] = []

        # Build shapely polygons once per frame (zones rarely change).
        zone_shapes = self._build_zone_shapes(frame_width, frame_height)

        active_keys: set[tuple[int, str]] = set()

        for person in tracked_persons:
            cx, cy = person.centroid

            for zone in self._zones:
                key = (person.track_id, zone.id)
                active_keys.add(key)

                if zone.zone_type == ZoneType.polygon:
                    event = self._check_polygon(key, zone, cx, cy, zone_shapes, person)
                    if event:
                        events.append(event)

                elif zone.zone_type == ZoneType.line:
                    prev = tracker.get_previous_centroid(person.track_id)
                    event = self._check_line(key, zone, cx, cy, prev, zone_shapes, person)
                    if event:
                        events.append(event)

        # Reset state for tracks that are no longer visible.
        stale_keys = set(self._inside_count.keys()) - active_keys
        for k in stale_keys:
            del self._inside_count[k]
            self._fired.pop(k, None)

        return events

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _build_zone_shapes(self, w: int, h: int) -> dict[str, object]:
        """Convert normalised zone points to pixel-space Shapely geometries."""
        shapes: dict[str, object] = {}
        for zone in self._zones:
            pts_px = [(p[0] * w, p[1] * h) for p in zone.points]
            if zone.zone_type == ZoneType.polygon and len(pts_px) >= 3:
                shapes[zone.id] = Polygon(pts_px)
            elif zone.zone_type == ZoneType.line and len(pts_px) == 2:
                shapes[zone.id] = pts_px  # raw points; signed distance computed below
        return shapes

    def _check_polygon(
        self,
        key: tuple[int, str],
        zone: Zone,
        cx: float,
        cy: float,
        zone_shapes: dict,
        person: TrackedPerson,
    ) -> CrossingEvent | None:
        shape = zone_shapes.get(zone.id)
        if shape is None:
            return None

        is_inside = shape.contains(Point(cx, cy))  # type: ignore[union-attr]

        if is_inside:
            self._inside_count[key] += 1
        else:
            self._inside_count[key] = 0
            self._fired[key] = False  # Reset so next entry fires again.
            return None

        if self._inside_count[key] >= settings.debounce_frames and not self._fired[key]:
            self._fired[key] = True
            return self._make_event(zone, person)

        return None

    def _check_line(
        self,
        key: tuple[int, str],
        zone: Zone,
        cx: float,
        cy: float,
        prev_centroid: tuple[float, float] | None,
        zone_shapes: dict,
        person: TrackedPerson,
    ) -> CrossingEvent | None:
        if prev_centroid is None:
            return None  # Need at least two points to detect a crossing.

        pts = zone_shapes.get(zone.id)
        if pts is None or not isinstance(pts, list):
            return None

        (x1, y1), (x2, y2) = pts[0], pts[1]
        dx, dy = x2 - x1, y2 - y1

        def signed_dist(px: float, py: float) -> float:
            """Signed distance from point (px, py) to the line (x1,y1)→(x2,y2)."""
            return dx * (py - y1) - dy * (px - x1)

        prev_sign = signed_dist(*prev_centroid)
        curr_sign = signed_dist(cx, cy)

        if prev_sign * curr_sign < 0:  # Sign changed → crossed the line.
            if not self._fired[key]:
                self._fired[key] = True
                return self._make_event(zone, person)
        else:
            # Allow the event to re-fire after the person crosses back.
            self._fired[key] = False

        return None

    @staticmethod
    def _make_event(zone: Zone, person: TrackedPerson) -> CrossingEvent:
        return CrossingEvent(
            id=str(uuid.uuid4()),
            zone_id=zone.id,
            zone_name=zone.name,
            track_id=person.track_id,
            timestamp=datetime.utcnow(),
        )
