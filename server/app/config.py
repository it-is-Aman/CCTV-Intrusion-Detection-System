"""Application configuration — all tuneable parameters in one place.

Loaded from environment variables (or a .env file) with sane defaults
so the app works out-of-the-box with zero configuration.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime-tuneable configuration for the intrusion detection MVP."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Camera ────────────────────────────────────────────────────────────────
    camera_device: int = 0
    """OpenCV VideoCapture device index (0 = default webcam)."""

    capture_fps: int = 30
    """Target FPS for the raw frame capture loop (actual FPS limited by hardware)."""

    stream_fps: int = 15
    """FPS at which annotated MJPEG frames are served to the browser."""

    inference_fps: int = 10
    """FPS at which YOLOv8n inference runs (sampled from the capture loop)."""

    # ── Ring buffer ───────────────────────────────────────────────────────────
    ring_buffer_seconds: int = 10
    """How many seconds of raw frames to keep in the pre-event ring buffer."""

    clip_post_seconds: int = 5
    """How many seconds of frames to collect *after* a crossing event fires."""

    # ── Detection ─────────────────────────────────────────────────────────────
    yolo_model: str = "yolov8n.pt"
    """YOLOv8 model weights file (auto-downloaded by ultralytics on first run)."""

    confidence_threshold: float = 0.45
    """Minimum YOLO confidence to consider a detection valid."""

    # ── Zone engine ───────────────────────────────────────────────────────────
    debounce_frames: int = 3
    """Consecutive frames a person must be inside a zone before crossing fires."""

    # ── Storage ───────────────────────────────────────────────────────────────
    storage_root: Path = Path("storage")
    """Root directory for all local file storage (relative to server/ working dir)."""

    @property
    def snapshots_dir(self) -> Path:
        return self.storage_root / "snapshots"

    @property
    def clips_dir(self) -> Path:
        return self.storage_root / "clips"

    @property
    def sqlite_path(self) -> Path:
        return self.storage_root / "events.db"

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


# Singleton instance — import this everywhere.
settings = Settings()
