"""Pydantic models for API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class JobResponse(BaseModel):
    id: str
    status: JobStatus
    created_at: str
    updated_at: str
    logs: str
    error: Optional[str] = None
    download_url: Optional[str] = None
    progress: int = 0  # 0-100


class UploadResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
