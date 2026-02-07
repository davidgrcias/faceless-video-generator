"""Application configuration."""

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
OUTPUTS_DIR = STORAGE_DIR / "outputs"
ASSETS_DIR = BASE_DIR / "assets"
BACKGROUNDS_DIR = ASSETS_DIR / "backgrounds"
FONTS_DIR = ASSETS_DIR / "fonts"
DATABASE_PATH = BASE_DIR / "database.db"

# Ensure directories exist
for d in [UPLOADS_DIR, OUTPUTS_DIR, BACKGROUNDS_DIR, FONTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Server settings
HOST = "0.0.0.0"
PORT = 8000
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

# Whisper settings
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")  # tiny, base, small, medium, large

# Video settings
VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
VIDEO_FPS = 30
FONT_SIZE = 28
SUBTITLE_FONT_COLOR = "white"
SUBTITLE_BG_COLOR = "black@0.6"

# Worker settings
WORKER_POLL_INTERVAL = 2  # seconds between job checks
MAX_AUDIO_DURATION = 120  # seconds – reject files longer than this
