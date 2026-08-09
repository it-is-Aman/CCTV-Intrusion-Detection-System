"""FastAPI application factory and entry point.

Startup/shutdown lifecycle:
1. Ensure storage directories exist.
2. Open SQLite and run migrations.
3. Start the CameraManager background thread.
4. Start the DetectionPipeline asyncio task.

On shutdown everything is torn down in reverse order.

Run with:
    uv run uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.camera import CameraManager
from app.config import settings
from app.database import close_db, init_db
from app.pipeline import DetectionPipeline
from app.routes import events, stream, zones

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle resources."""
    # ── Startup ───────────────────────────────────────────────────────────
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    settings.snapshots_dir.mkdir(parents=True, exist_ok=True)
    settings.clips_dir.mkdir(parents=True, exist_ok=True)

    await init_db()

    camera = CameraManager()
    camera.start()
    app.state.camera = camera

    pipeline = DetectionPipeline(camera)
    await pipeline.start()
    app.state.pipeline = pipeline

    logger.info("✓ Intrusion detection MVP started on http://%s:%d", settings.host, settings.port)

    yield  # ── Application runs here ───────────────────────────────────────

    # ── Shutdown ──────────────────────────────────────────────────────────
    await pipeline.stop()
    camera.stop()
    await close_db()
    logger.info("✓ Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Intrusion Detection MVP",
        description="Local webcam-based zone-crossing intrusion detection.",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(stream.router)
    app.include_router(zones.router)
    app.include_router(events.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        """Liveness check — returns camera and pipeline status."""
        camera: CameraManager = app.state.camera
        return {
            "status": "ok",
            "camera_running": camera.is_running,
            "frame_size": f"{camera.frame_width}×{camera.frame_height}",
        }

    return app


app = create_app()
