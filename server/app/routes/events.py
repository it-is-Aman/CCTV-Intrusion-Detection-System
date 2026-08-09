"""Event history routes.

Provides paginated access to crossing events and individual event detail
(including paths to snapshot and clip files for media playback).

Endpoints
---------
GET /events          — paginated event list, optional ?zone_id= filter
GET /events/{id}     — single event detail
GET /events/{id}/snapshot — serve snapshot image file
GET /events/{id}/clip     — serve video clip file
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

import app.database as db
from app.models import CrossingEvent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/events", tags=["events"])


# ── Response schemas ──────────────────────────────────────────────────────────

class EventResponse(BaseModel):
    id: str
    zone_id: str
    zone_name: str
    track_id: int
    timestamp: str
    snapshot_path: str | None
    clip_path: str | None
    has_snapshot: bool
    has_clip: bool

    @classmethod
    def from_event(cls, event: CrossingEvent) -> "EventResponse":
        return cls(
            id=event.id,
            zone_id=event.zone_id,
            zone_name=event.zone_name,
            track_id=event.track_id,
            timestamp=event.timestamp.isoformat(),
            snapshot_path=event.snapshot_path,
            clip_path=event.clip_path,
            has_snapshot=event.snapshot_path is not None and Path(event.snapshot_path).exists(),
            has_clip=event.clip_path is not None and Path(event.clip_path).exists(),
        )


class PaginatedEventsResponse(BaseModel):
    items: list[EventResponse]
    limit: int
    offset: int
    count: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=PaginatedEventsResponse)
async def list_events_endpoint(
    zone_id: str | None = Query(default=None, description="Filter by zone ID"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedEventsResponse:
    """List crossing events, newest first, with optional zone filter."""
    events = await db.list_events(zone_id=zone_id, limit=limit, offset=offset)
    items = [EventResponse.from_event(e) for e in events]
    return PaginatedEventsResponse(items=items, limit=limit, offset=offset, count=len(items))


@router.get("/{event_id}", response_model=EventResponse)
async def get_event_endpoint(event_id: str) -> EventResponse:
    """Retrieve a single crossing event by ID."""
    event = await db.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    return EventResponse.from_event(event)


@router.get("/{event_id}/snapshot")
async def get_event_snapshot(event_id: str) -> FileResponse:
    """Serve the snapshot JPEG for an event."""
    event = await db.get_event(event_id)
    if event is None or event.snapshot_path is None:
        raise HTTPException(status_code=404, detail="Snapshot not found.")
    path = Path(event.snapshot_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Snapshot file missing from disk.")
    return FileResponse(path, media_type="image/jpeg")


@router.get("/{event_id}/clip")
async def get_event_clip(event_id: str) -> FileResponse:
    """Serve the MP4 clip for an event."""
    event = await db.get_event(event_id)
    if event is None or event.clip_path is None:
        raise HTTPException(status_code=404, detail="Clip not found.")
    path = Path(event.clip_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Clip file missing from disk.")
    return FileResponse(path, media_type="video/mp4")
