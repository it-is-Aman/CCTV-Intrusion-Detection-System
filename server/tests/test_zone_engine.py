"""Unit tests for ZoneEngine — pure logic, zero I/O.

These tests exercise the crossing state machine directly without any camera,
YOLO model, or database.  A MockTracker stub substitutes for PersonTracker.
"""

from __future__ import annotations

import pytest

from app.models import CrossingEvent, TrackedPerson, Zone, ZoneType
from app.zone_engine import ZoneEngine


# ── Fixtures ─────────────────────────────────────────────────────────────────

class MockTracker:
    """Stub tracker that returns a configurable previous centroid."""

    def __init__(self, prev: tuple[float, float] | None = None) -> None:
        self._prev = prev

    def get_previous_centroid(self, track_id: int) -> tuple[float, float] | None:
        return self._prev


def _make_person(track_id: int, cx: float, cy: float) -> TrackedPerson:
    """Create a TrackedPerson with centroid at (cx, cy)."""
    half = 20
    return TrackedPerson(
        track_id=track_id,
        bbox=(int(cx - half), int(cy - half), int(cx + half), int(cy + half)),
        confidence=0.9,
    )


def _polygon_zone(pts: list[list[float]]) -> Zone:
    from datetime import datetime
    return Zone(
        id="z1",
        name="Test Zone",
        zone_type=ZoneType.polygon,
        points=pts,
        created_at=datetime.utcnow(),
    )


def _line_zone(pts: list[list[float]]) -> Zone:
    from datetime import datetime
    return Zone(
        id="z2",
        name="Tripwire",
        zone_type=ZoneType.line,
        points=pts,
        created_at=datetime.utcnow(),
    )


FRAME_W, FRAME_H = 640, 480


# ── Polygon tests ─────────────────────────────────────────────────────────────

class TestPolygonZone:
    """Polygon zone entry detection with debounce."""

    def _engine(self) -> ZoneEngine:
        # Square zone in the centre of the frame (normalised 0.25–0.75).
        zone = _polygon_zone([[0.25, 0.25], [0.75, 0.25], [0.75, 0.75], [0.25, 0.75]])
        return ZoneEngine([zone])

    def test_no_event_outside(self):
        engine = self._engine()
        tracker = MockTracker()
        # Person clearly outside the zone.
        person = _make_person(1, 50, 50)  # top-left corner
        events = engine.update([person], FRAME_W, FRAME_H, tracker)
        assert events == []

    def test_no_event_before_debounce(self):
        """Event must NOT fire until debounce_frames consecutive inside frames."""
        engine = self._engine()
        tracker = MockTracker()
        person = _make_person(1, 320, 240)  # centre — inside

        # frames 1 and 2 (debounce default is 3).
        for _ in range(2):
            events = engine.update([person], FRAME_W, FRAME_H, tracker)
            assert events == [], "Should not fire before debounce threshold"

    def test_event_fires_after_debounce(self, monkeypatch):
        """Event fires on the Nth consecutive inside frame (N = debounce_frames)."""
        import app.config as cfg
        monkeypatch.setattr(cfg.settings, "debounce_frames", 3)

        engine = self._engine()
        tracker = MockTracker()
        person = _make_person(1, 320, 240)

        events = []
        for _ in range(3):
            events = engine.update([person], FRAME_W, FRAME_H, tracker)

        assert len(events) == 1
        assert events[0].zone_name == "Test Zone"
        assert events[0].track_id == 1

    def test_event_fires_only_once_per_entry(self, monkeypatch):
        """After the event fires, subsequent inside frames must not re-fire."""
        import app.config as cfg
        monkeypatch.setattr(cfg.settings, "debounce_frames", 1)

        engine = self._engine()
        tracker = MockTracker()
        person = _make_person(1, 320, 240)

        all_events: list[CrossingEvent] = []
        for _ in range(10):
            all_events.extend(engine.update([person], FRAME_W, FRAME_H, tracker))

        assert len(all_events) == 1, "Event should fire exactly once per entry"

    def test_event_resets_after_exit_and_reentry(self, monkeypatch):
        """After a person leaves and re-enters, the event should fire again."""
        import app.config as cfg
        monkeypatch.setattr(cfg.settings, "debounce_frames", 1)

        engine = self._engine()
        tracker = MockTracker()
        inside_person = _make_person(1, 320, 240)
        outside_person = _make_person(1, 50, 50)

        # Entry 1
        events1 = engine.update([inside_person], FRAME_W, FRAME_H, tracker)
        # Exit
        engine.update([outside_person], FRAME_W, FRAME_H, tracker)
        # Entry 2
        events2 = engine.update([inside_person], FRAME_W, FRAME_H, tracker)

        assert len(events1) == 1
        assert len(events2) == 1

    def test_multiple_tracks_independent(self, monkeypatch):
        """Two separate tracks crossing the same zone each fire their own event."""
        import app.config as cfg
        monkeypatch.setattr(cfg.settings, "debounce_frames", 1)

        engine = self._engine()
        tracker = MockTracker()
        p1 = _make_person(1, 320, 240)
        p2 = _make_person(2, 310, 250)

        events = engine.update([p1, p2], FRAME_W, FRAME_H, tracker)
        track_ids = {e.track_id for e in events}
        assert track_ids == {1, 2}


# ── Line / tripwire tests ─────────────────────────────────────────────────────

class TestLineZone:
    """Line-crossing (tripwire) detection."""

    def _engine(self) -> ZoneEngine:
        # Horizontal tripwire at y=0.5 (pixel y=240), spanning full width.
        zone = _line_zone([[0.0, 0.5], [1.0, 0.5]])
        return ZoneEngine([zone])

    def test_crossing_downward(self):
        """Person moving from y<240 to y>240 fires an event."""
        engine = self._engine()
        # Previous centroid above the line, current below.
        tracker = MockTracker(prev=(320, 200))
        person = _make_person(1, 320, 280)

        events = engine.update([person], FRAME_W, FRAME_H, tracker)
        assert len(events) == 1
        assert events[0].track_id == 1

    def test_crossing_upward(self):
        """Person moving from y>240 to y<240 also fires an event."""
        engine = self._engine()
        tracker = MockTracker(prev=(320, 280))
        person = _make_person(1, 320, 200)

        events = engine.update([person], FRAME_W, FRAME_H, tracker)
        assert len(events) == 1

    def test_no_crossing_same_side(self):
        """Person staying on the same side of the line does not fire."""
        engine = self._engine()
        tracker = MockTracker(prev=(320, 100))
        person = _make_person(1, 320, 150)  # still above line

        events = engine.update([person], FRAME_W, FRAME_H, tracker)
        assert events == []

    def test_no_event_without_previous_centroid(self):
        """First frame for a track has no previous centroid — no event."""
        engine = self._engine()
        tracker = MockTracker(prev=None)
        person = _make_person(1, 320, 280)

        events = engine.update([person], FRAME_W, FRAME_H, tracker)
        assert events == []

    def test_crossing_fires_once_then_resets(self):
        """After crossing, moving further in the same direction does not re-fire."""
        engine = self._engine()

        # First call: cross downward.
        tracker1 = MockTracker(prev=(320, 200))
        person = _make_person(1, 320, 280)
        events1 = engine.update([person], FRAME_W, FRAME_H, tracker1)

        # Second call: continue moving further down (no sign change).
        tracker2 = MockTracker(prev=(320, 280))
        person2 = _make_person(1, 320, 350)
        events2 = engine.update([person2], FRAME_W, FRAME_H, tracker2)

        assert len(events1) == 1
        assert len(events2) == 0
