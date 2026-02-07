"""FastAPI application entry point."""

import asyncio
import logging
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from routes.jobs import router as jobs_router
from services.job_manager import JobManager
from workers.processor import VideoWorker

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("fcg")

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Faceless Video Generator",
    description="Generate MP4 videos from MP3 voice-overs",
    version="1.0.0",
)

# CORS – allow the Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Shared state exposed via app.state
# ---------------------------------------------------------------------------
job_manager = JobManager(config.DATABASE_PATH)
app.state.job_manager = job_manager

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
app.include_router(jobs_router, prefix="/api/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# Background worker (runs in a dedicated thread)
# ---------------------------------------------------------------------------
worker: VideoWorker | None = None


@app.on_event("startup")
async def startup_event() -> None:
    global worker
    job_manager.init_db()
    worker = VideoWorker(job_manager)
    worker.start()
    logger.info("Background video worker started.")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    global worker
    if worker:
        worker.stop()
        logger.info("Background video worker stopped.")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    return {"status": "ok"}
