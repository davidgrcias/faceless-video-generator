"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

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
# Shared state
# ---------------------------------------------------------------------------
job_manager = JobManager(config.DATABASE_PATH)


# ---------------------------------------------------------------------------
# Lifespan (replaces deprecated on_event)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    job_manager.init_db()
    app.state.job_manager = job_manager
    worker = VideoWorker(job_manager)
    worker.start()
    logger.info("Background video worker started.")
    yield
    # Shutdown
    worker.stop()
    logger.info("Background video worker stopped.")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Faceless Video Generator",
    description="Generate MP4 videos from MP3 voice-overs",
    version="1.0.0",
    lifespan=lifespan,
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
# Routes
# ---------------------------------------------------------------------------
app.include_router(jobs_router, prefix="/api/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    return {"status": "ok"}
