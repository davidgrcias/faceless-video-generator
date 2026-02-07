"""API routes for job management."""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse

import config
from models import JobResponse, JobStatus, UploadResponse
from services.job_manager import JobManager

router = APIRouter()


def _manager(request: Request) -> JobManager:
    return request.app.state.job_manager


# ---------------------------------------------------------------------------
# POST /api/jobs/upload
# ---------------------------------------------------------------------------
@router.post("/upload", response_model=UploadResponse)
async def upload_audio(request: Request, file: UploadFile = File(...)):
    """Upload an MP3 file and create a new video generation job."""

    # Validate file type
    if not file.filename:
        raise HTTPException(400, "No file provided.")

    allowed_extensions = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            400,
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(allowed_extensions))}",
        )

    # Validate file size (max 50 MB)
    content = await file.read()
    max_size = 50 * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(400, f"File too large. Maximum size: {max_size // (1024*1024)} MB.")

    # Save to disk
    manager = _manager(request)
    job_id = manager.create_job("")  # placeholder, update after save

    safe_filename = f"{job_id}{ext}"
    audio_path = str(config.UPLOADS_DIR / safe_filename)
    Path(audio_path).write_bytes(content)

    # Update job with actual audio path
    manager.update_status(
        job_id,
        JobStatus.QUEUED,
        progress=0,
    )
    # Also update audio_path directly
    with manager._connect() as conn:
        conn.execute("UPDATE jobs SET audio_path = ? WHERE id = ?", (audio_path, job_id))

    manager.append_log(job_id, f"📁 Audio uploaded: {file.filename} ({len(content) / 1024:.0f} KB)")

    return UploadResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        message="Job created successfully. Processing will begin shortly.",
    )


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}
# ---------------------------------------------------------------------------
@router.get("/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str, request: Request):
    """Get the current status of a job."""
    manager = _manager(request)
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found.")

    download_url = None
    if job["status"] == JobStatus.DONE.value and job.get("output_path"):
        download_url = f"/api/jobs/{job_id}/download"

    return JobResponse(
        id=job["id"],
        status=JobStatus(job["status"]),
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        logs=job["logs"] or "",
        error=job.get("error"),
        download_url=download_url,
        progress=job.get("progress", 0),
    )


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}/download
# ---------------------------------------------------------------------------
@router.get("/{job_id}/download")
async def download_video(job_id: str, request: Request):
    """Download the generated MP4 video."""
    manager = _manager(request)
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found.")

    if job["status"] != JobStatus.DONE.value:
        raise HTTPException(400, "Video is not ready yet.")

    output_path = job.get("output_path")
    if not output_path or not Path(output_path).exists():
        raise HTTPException(404, "Video file not found on disk.")

    return FileResponse(
        output_path,
        media_type="video/mp4",
        filename=f"faceless-video-{job_id}.mp4",
    )


# ---------------------------------------------------------------------------
# GET /api/jobs  (list all jobs)
# ---------------------------------------------------------------------------
@router.get("/", response_model=list[JobResponse])
async def list_jobs(request: Request):
    """List all jobs (most recent first)."""
    manager = _manager(request)
    jobs = manager.list_jobs()
    results = []
    for job in jobs:
        download_url = None
        if job["status"] == JobStatus.DONE.value and job.get("output_path"):
            download_url = f"/api/jobs/{job['id']}/download"
        results.append(
            JobResponse(
                id=job["id"],
                status=JobStatus(job["status"]),
                created_at=job["created_at"],
                updated_at=job["updated_at"],
                logs=job["logs"] or "",
                error=job.get("error"),
                download_url=download_url,
                progress=job.get("progress", 0),
            )
        )
    return results
