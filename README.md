# Intrusion Detection MVP

Local webcam-based zone-crossing intrusion detection. No cloud, no auth, no external services.

## Quick Start

### 1. Install backend dependencies

```bash
cd server
uv sync
```

### 2. Start the backend

```bash
cd server
uv run uvicorn main:app --reload --port 8000
```

On first run, `ultralytics` will auto-download `yolov8n.pt` (~6 MB).

### 3. Start the frontend

```bash
cd web
pnpm dev
```

Open **http://localhost:5173** in your browser.

---

## Architecture

```
Browser (localhost:5173)
  ├─ <img src="/stream"> ────────────► GET /stream  (MJPEG annotated feed)
  ├─ Canvas overlay (zone drawing)
  ├─ fetch() ────────────────────────► REST /zones, /events
  └─ WebSocket ──────────────────────► WS /ws (real-time alerts)

FastAPI (localhost:8000)
  ├─ /stream  ← CameraManager + MJPEG annotator
  ├─ /ws      ← WebSocket fan-out on crossing events
  ├─ /zones   ← SQLite CRUD
  ├─ /events  ← SQLite + filesystem file serving
  └─ DetectionPipeline (background asyncio task)
        ├─ CameraManager    (ring buffer, OpenCV thread)
        ├─ Detector         (YOLOv8n, sampled @ inference_fps)
        ├─ PersonTracker    (ByteTrack via supervision)
        ├─ ZoneEngine       (pure crossing logic, Shapely)
        └─ EvidenceWriter   (snapshot JPEG + MP4 clip)
```

## Configuration

All settings live in `server/app/config.py` with sane defaults.  
Override via environment variables or a `.env` file in `server/`:

| Variable | Default | Description |
|---|---|---|
| `CAMERA_DEVICE` | `0` | OpenCV device index |
| `INFERENCE_FPS` | `10` | Detection sample rate |
| `STREAM_FPS` | `15` | MJPEG output FPS |
| `CONFIDENCE_THRESHOLD` | `0.45` | YOLO min confidence |
| `DEBOUNCE_FRAMES` | `3` | Frames inside zone before alert fires |
| `RING_BUFFER_SECONDS` | `10` | Pre-event clip context |
| `CLIP_POST_SECONDS` | `5` | Post-event clip duration |
| `STORAGE_ROOT` | `storage/` | Root for snapshots + clips + DB |

## Running tests

```bash
cd server
uv run pytest tests/ -v
```

Tests for `ZoneEngine` run with zero I/O — no camera, no YOLO model needed.

## File layout

```
server/
  app/
    config.py        — Settings (pydantic-settings)
    models.py        — Domain dataclasses (Zone, CrossingEvent, TrackedPerson)
    database.py      — aiosqlite layer (zones + events tables)
    camera.py        — OpenCV capture thread + ring buffer
    detector.py      — YOLOv8n inference (stateless)
    tracker.py       — ByteTrack wrapper (supervision)
    zone_engine.py   — Pure crossing logic (Shapely, debounce)
    evidence.py      — Snapshot + MP4 clip writer
    pipeline.py      — Async detection loop (orchestrates all above)
    stream.py        — MJPEG generator + annotation overlay
    ws_manager.py    — WebSocket fan-out manager
    routes/
      zones.py       — GET/POST/DELETE /zones
      events.py      — GET /events, /events/{id}, /snapshot, /clip
      stream.py      — GET /stream, WS /ws
  main.py            — FastAPI app factory + lifespan
  tests/
    test_zone_engine.py

web/
  src/
    types.ts         — Shared TypeScript interfaces
    api.ts           — Typed fetch API client
    hooks/
      useWebSocket.ts  — WS with auto-reconnect
      useZones.ts      — Zone CRUD with optimistic updates
      useEvents.ts     — Events list + WS prepend
    components/
      LiveFeed.jsx     — MJPEG img + drawing canvas
      ZoneEditor.jsx   — Drawing toolbar + save form
      ZoneList.jsx     — Zone list with alert highlight
      AlertBanner.jsx  — Stacked slide-in alert toasts
      EventList.jsx    — Scrollable event history
      EventDetail.jsx  — Modal with snapshot + clip player
    App.jsx          — Root layout + state orchestration
```
