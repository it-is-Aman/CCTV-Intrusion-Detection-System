"""Zone CRUD routes.

Zones are stored in SQLite and served to the frontend for canvas overlay
rendering.  Points are in normalised [0, 1] coordinates so they survive
resolution changes without any migration.

Endpoints
---------
GET  /zones          — list all zones
POST /zones          — create a zone
DELETE /zones/{id}   — delete a zone (cascades to events via FK)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

import app.database as db
from app.models import LineTrigger, PolygonTrigger, Zone, ZoneType

router = APIRouter(prefix="/zones", tags=["zones"])


# ── Request / response schemas ────────────────────────────────────────────────

class ZoneCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    zone_type: ZoneType
    points: list[list[float]] = Field(..., min_length=2)
    trigger: str = "entry"  # PolygonTrigger or LineTrigger value

    model_config = {"json_schema_extra": {"example": {
        "name": "Front door",
        "zone_type": "polygon",
        "points": [[0.1, 0.2], [0.4, 0.2], [0.4, 0.6], [0.1, 0.6]],
        "trigger": "entry",
    }}}


class ZoneResponse(BaseModel):
    id: str
    name: str
    zone_type: ZoneType
    points: list[list[float]]
    trigger: str
    created_at: str

    @classmethod
    def from_zone(cls, zone: Zone) -> "ZoneResponse":
        return cls(
            id=zone.id,
            name=zone.name,
            zone_type=zone.zone_type,
            points=zone.points,
            trigger=zone.trigger,
            created_at=zone.created_at.isoformat(),
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[ZoneResponse])
async def list_zones_endpoint() -> list[ZoneResponse]:
    """Return all configured zones."""
    zones = await db.list_zones()
    return [ZoneResponse.from_zone(z) for z in zones]


@router.post("/", response_model=ZoneResponse, status_code=status.HTTP_201_CREATED)
async def create_zone_endpoint(payload: ZoneCreate) -> ZoneResponse:
    """Create and persist a new zone."""
    if payload.zone_type == ZoneType.polygon and len(payload.points) < 3:
        raise HTTPException(status_code=422, detail="Polygon zones require at least 3 points.")
    if payload.zone_type == ZoneType.line and len(payload.points) != 2:
        raise HTTPException(status_code=422, detail="Line zones require exactly 2 points.")

    # Validate trigger value matches zone type.
    valid_polygon = {t.value for t in PolygonTrigger}
    valid_line = {t.value for t in LineTrigger}
    if payload.zone_type == ZoneType.polygon and payload.trigger not in valid_polygon:
        raise HTTPException(status_code=422, detail=f"Polygon trigger must be one of: {valid_polygon}")
    if payload.zone_type == ZoneType.line and payload.trigger not in valid_line:
        raise HTTPException(status_code=422, detail=f"Line trigger must be one of: {valid_line}")

    zone = Zone(
        id=str(uuid.uuid4()),
        name=payload.name,
        zone_type=payload.zone_type,
        points=payload.points,
        trigger=payload.trigger,
        created_at=datetime.utcnow(),
    )
    await db.insert_zone(zone)
    return ZoneResponse.from_zone(zone)


@router.delete("/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_zone_endpoint(zone_id: str) -> None:
    """Delete a zone and all associated events (FK cascade)."""
    deleted = await db.delete_zone(zone_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Zone not found.")
