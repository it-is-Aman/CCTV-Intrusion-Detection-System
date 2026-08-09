"""SQLite database layer using aiosqlite.

Responsibilities:
- Provide an async connection factory.
- Run schema migrations on startup (idempotent CREATE TABLE IF NOT EXISTS).
- Expose typed helpers for zone and event CRUD used by routes and the pipeline.

Design notes:
- No ORM — raw SQL for transparency and minimal dependencies.
- All public functions are async and accept a connection so callers can
  share a transaction when needed.
- JSON is used to store the ``points`` list in SQLite (TEXT column).
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

from app.config import settings
from app.models import CrossingEvent, Zone, ZoneType

logger = logging.getLogger(__name__)

# Module-level connection shared across the app lifetime.
_db: aiosqlite.Connection | None = None


async def init_db() -> None:
    """Open the SQLite connection and run migrations.  Call once at startup."""
    global _db  # noqa: PLW0603

    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    _db = await aiosqlite.connect(settings.sqlite_path)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA foreign_keys=ON")

    await _migrate(_db)
    logger.info("Database ready at %s", settings.sqlite_path)


async def close_db() -> None:
    """Close the database connection.  Call once at shutdown."""
    global _db  # noqa: PLW0603
    if _db is not None:
        await _db.close()
        _db = None


def get_db() -> aiosqlite.Connection:
    """Return the active connection (raises if not initialised)."""
    if _db is None:
        raise RuntimeError("Database not initialised — call init_db() first.")
    return _db


@asynccontextmanager
async def transaction() -> AsyncIterator[aiosqlite.Connection]:
    """Async context manager that wraps operations in a DB transaction."""
    db = get_db()
    async with db.execute("BEGIN"):
        try:
            yield db
            await db.execute("COMMIT")
        except Exception:
            await db.execute("ROLLBACK")
            raise


# ── Migrations ────────────────────────────────────────────────────────────────

async def _migrate(db: aiosqlite.Connection) -> None:
    """Apply idempotent schema migrations."""
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS zones (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            zone_type   TEXT NOT NULL CHECK(zone_type IN ('polygon', 'line')),
            points      TEXT NOT NULL,   -- JSON array of [x, y] pairs
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS events (
            id              TEXT PRIMARY KEY,
            zone_id         TEXT NOT NULL,
            zone_name       TEXT NOT NULL,
            track_id        INTEGER NOT NULL,
            timestamp       TEXT NOT NULL,
            snapshot_path   TEXT,
            clip_path       TEXT,
            FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_events_zone_id   ON events(zone_id);
        """
    )
    await db.commit()


# ── Zone helpers ──────────────────────────────────────────────────────────────

async def list_zones() -> list[Zone]:
    db = get_db()
    async with db.execute("SELECT * FROM zones ORDER BY created_at") as cur:
        rows = await cur.fetchall()
    return [_row_to_zone(r) for r in rows]


async def get_zone(zone_id: str) -> Zone | None:
    db = get_db()
    async with db.execute("SELECT * FROM zones WHERE id = ?", (zone_id,)) as cur:
        row = await cur.fetchone()
    return _row_to_zone(row) if row else None


async def insert_zone(zone: Zone) -> None:
    db = get_db()
    await db.execute(
        "INSERT INTO zones (id, name, zone_type, points, created_at) VALUES (?, ?, ?, ?, ?)",
        (zone.id, zone.name, zone.zone_type.value, json.dumps(zone.points), zone.created_at.isoformat()),
    )
    await db.commit()


async def delete_zone(zone_id: str) -> bool:
    db = get_db()
    cur = await db.execute("DELETE FROM zones WHERE id = ?", (zone_id,))
    await db.commit()
    return cur.rowcount > 0


# ── Event helpers ─────────────────────────────────────────────────────────────

async def insert_event(event: CrossingEvent) -> None:
    db = get_db()
    await db.execute(
        """INSERT INTO events
           (id, zone_id, zone_name, track_id, timestamp, snapshot_path, clip_path)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            event.id,
            event.zone_id,
            event.zone_name,
            event.track_id,
            event.timestamp.isoformat(),
            event.snapshot_path,
            event.clip_path,
        ),
    )
    await db.commit()


async def list_events(
    zone_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[CrossingEvent]:
    db = get_db()
    if zone_id:
        query = "SELECT * FROM events WHERE zone_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params: tuple = (zone_id, limit, offset)
    else:
        query = "SELECT * FROM events ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params = (limit, offset)

    async with db.execute(query, params) as cur:
        rows = await cur.fetchall()
    return [_row_to_event(r) for r in rows]


async def get_event(event_id: str) -> CrossingEvent | None:
    db = get_db()
    async with db.execute("SELECT * FROM events WHERE id = ?", (event_id,)) as cur:
        row = await cur.fetchone()
    return _row_to_event(row) if row else None


async def update_event_paths(event_id: str, snapshot_path: str | None, clip_path: str | None) -> None:
    """Update evidence file paths after they have been written to disk."""
    db = get_db()
    await db.execute(
        "UPDATE events SET snapshot_path = ?, clip_path = ? WHERE id = ?",
        (snapshot_path, clip_path, event_id),
    )
    await db.commit()


# ── Private helpers ───────────────────────────────────────────────────────────

def _row_to_zone(row: aiosqlite.Row) -> Zone:
    return Zone(
        id=row["id"],
        name=row["name"],
        zone_type=ZoneType(row["zone_type"]),
        points=json.loads(row["points"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _row_to_event(row: aiosqlite.Row) -> CrossingEvent:
    return CrossingEvent(
        id=row["id"],
        zone_id=row["zone_id"],
        zone_name=row["zone_name"],
        track_id=row["track_id"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        snapshot_path=row["snapshot_path"],
        clip_path=row["clip_path"],
    )
