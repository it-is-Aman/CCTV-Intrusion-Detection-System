"""Pure Python dataclasses for domain objects.

No ORM — these map 1-to-1 with the SQLite schema and are used as
the canonical types throughout the pipeline and API layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ZoneType(str, Enum):
    """Supported zone geometry types."""

    polygon = "polygon"
    line = "line"


class PolygonTrigger(str, Enum):
    """When to fire an alert for polygon zones."""

    entry = "entry"   # person enters the polygon (default)
    exit = "exit"     # person leaves the polygon


class LineTrigger(str, Enum):
    """Which crossing direction fires an alert for line/tripwire zones."""

    both = "both"       # either direction (default)
    a_to_b = "a_to_b"  # crosses from the A-side to the B-side
    b_to_a = "b_to_a"  # crosses from the B-side to the A-side


@dataclass
class Zone:
    """A named detection zone drawn by the user.

    ``points`` is a list of [x, y] pairs in *normalised* canvas coordinates
    (0.0–1.0) so the zone survives frame-size changes.
    """

    id: str
    name: str
    zone_type: ZoneType
    points: list[list[float]]  # [[x, y], ...]
    trigger: str = "entry"     # PolygonTrigger or LineTrigger value
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "zone_type": self.zone_type.value,
            "points": self.points,
            "trigger": self.trigger,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class CrossingEvent:
    """A zone-crossing event produced by ZoneEngine.

    Created in-memory first; persisted to SQLite by the pipeline
    after evidence files are written.
    """

    id: str
    zone_id: str
    zone_name: str
    track_id: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    snapshot_path: str | None = None
    clip_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "track_id": self.track_id,
            "timestamp": self.timestamp.isoformat(),
            "snapshot_path": self.snapshot_path,
            "clip_path": self.clip_path,
        }


@dataclass
class TrackedPerson:
    """A single person returned by the tracker for one frame."""

    track_id: int
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2) in pixel coords
    confidence: float

    @property
    def centroid(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)
