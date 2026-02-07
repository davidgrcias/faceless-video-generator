"""Background worker – polls for queued jobs and processes them."""

from __future__ import annotations

import logging
import threading
import time

import config
from services.job_manager import JobManager
from services.pipeline import run_pipeline

logger = logging.getLogger("fcg.worker")


class VideoWorker:
    """
    Background worker that runs in a daemon thread.
    Polls for queued jobs and executes the video generation pipeline.
    """

    def __init__(self, manager: JobManager) -> None:
        self.manager = manager
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="video-worker")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _run(self) -> None:
        logger.info("Worker thread started (poll interval=%ds)", config.WORKER_POLL_INTERVAL)
        while not self._stop_event.is_set():
            try:
                job = self.manager.next_queued_job()
                if job:
                    logger.info("Processing job: %s", job["id"])
                    run_pipeline(job, self.manager)
                else:
                    # No work – sleep before polling again
                    self._stop_event.wait(timeout=config.WORKER_POLL_INTERVAL)
            except Exception as e:
                logger.error("Worker loop error: %s", e, exc_info=True)
                self._stop_event.wait(timeout=config.WORKER_POLL_INTERVAL)
