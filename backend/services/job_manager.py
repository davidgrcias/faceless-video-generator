"""Job manager – SQLite-backed job state management."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from models import JobStatus

logger = logging.getLogger("fcg.job_manager")


class JobManager:
    """Thread-safe job CRUD backed by SQLite."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = str(db_path)

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------
    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id          TEXT PRIMARY KEY,
                    status      TEXT NOT NULL DEFAULT 'queued',
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL,
                    audio_path  TEXT NOT NULL,
                    output_path TEXT,
                    srt_path    TEXT,
                    logs        TEXT NOT NULL DEFAULT '',
                    error       TEXT,
                    progress    INTEGER NOT NULL DEFAULT 0
                );
                """
            )
        logger.info("Database initialised at %s", self.db_path)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_job(self, audio_path: str) -> str:
        job_id = uuid.uuid4().hex[:12]
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs (id, status, created_at, updated_at, audio_path) VALUES (?, ?, ?, ?, ?)",
                (job_id, JobStatus.QUEUED.value, now, now, audio_path),
            )
        logger.info("Job created: %s", job_id)
        return job_id

    def get_job(self, job_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def list_jobs(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        progress: int | None = None,
        output_path: str | None = None,
        srt_path: str | None = None,
        error: str | None = None,
    ) -> None:
        sets = ["status = ?", "updated_at = ?"]
        params: list = [status.value, self._now()]
        if progress is not None:
            sets.append("progress = ?")
            params.append(progress)
        if output_path is not None:
            sets.append("output_path = ?")
            params.append(output_path)
        if srt_path is not None:
            sets.append("srt_path = ?")
            params.append(srt_path)
        if error is not None:
            sets.append("error = ?")
            params.append(error)
        params.append(job_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id = ?", params)

    def append_log(self, job_id: str, message: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET logs = logs || ?, updated_at = ? WHERE id = ?",
                (message + "\n", self._now(), job_id),
            )

    def next_queued_job(self) -> Optional[dict]:
        """Atomically grab the oldest queued job and mark it as processing."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at ASC LIMIT 1",
                (JobStatus.QUEUED.value,),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
                    (JobStatus.PROCESSING.value, self._now(), row["id"]),
                )
                return dict(row)
        return None
