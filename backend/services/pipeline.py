"""Video generation pipeline – orchestrates transcription + video assembly."""

from __future__ import annotations

import logging
import traceback
from pathlib import Path

import config
from models import JobStatus
from services.job_manager import JobManager
from services.transcriber import generate_word_level_srt, transcribe
from services.image_generator import generate_scene_images, split_into_scenes
from services.video_builder import (
    build_final_video,
    build_simple_video,
    build_slideshow_video,
    check_ffmpeg,
    generate_waveform_video,
    get_audio_duration,
)

logger = logging.getLogger("fcg.pipeline")


class PipelineError(Exception):
    """Raised when the pipeline encounters a fatal error."""


def run_pipeline(job: dict, manager: JobManager) -> None:
    """
    Execute the full video generation pipeline for a job.

    Steps:
      1. Validate FFmpeg availability
      2. Get audio duration
      3. Transcribe audio with Whisper → SRT
      4. Generate waveform video track
      5. Burn subtitles + combine audio → final MP4
    """
    job_id = job["id"]
    audio_path = job["audio_path"]

    try:
        # ------------------------------------------------------------------
        # Step 1: Pre-flight checks
        # ------------------------------------------------------------------
        _log(manager, job_id, "🔍 Checking FFmpeg availability…")
        if not check_ffmpeg():
            raise PipelineError(
                "FFmpeg not found on PATH. Please install FFmpeg and try again."
            )
        manager.update_status(job_id, JobStatus.PROCESSING, progress=5)
        _log(manager, job_id, "✅ FFmpeg is available.")

        # ------------------------------------------------------------------
        # Step 2: Get audio duration
        # ------------------------------------------------------------------
        _log(manager, job_id, "🎵 Analysing audio file…")
        duration = get_audio_duration(audio_path)
        _log(manager, job_id, f"   Duration: {duration:.1f}s")

        if duration > config.MAX_AUDIO_DURATION:
            raise PipelineError(
                f"Audio too long ({duration:.0f}s). Max allowed: {config.MAX_AUDIO_DURATION}s."
            )
        manager.update_status(job_id, JobStatus.PROCESSING, progress=10)

        # ------------------------------------------------------------------
        # Step 3: Transcription
        # ------------------------------------------------------------------
        srt_path = str(config.OUTPUTS_DIR / f"{job_id}.srt")
        transcription_ok = False

        try:
            _log(manager, job_id, "🗣️ Transcribing audio with Whisper…")
            manager.update_status(job_id, JobStatus.PROCESSING, progress=15)
            result = transcribe(audio_path, model_name=config.WHISPER_MODEL)
            segments = result.get("segments", [])

            if segments:
                generate_word_level_srt(segments, srt_path)
                _log(
                    manager,
                    job_id,
                    f"✅ Transcription complete – {len(segments)} segments.",
                )
                transcription_ok = True
            else:
                _log(manager, job_id, "⚠️ No segments found, using fallback subtitles.")
        except Exception as e:
            _log(manager, job_id, f"⚠️ Transcription failed: {e}. Using fallback subtitles.")
            logger.warning("Whisper failed for job %s: %s", job_id, e)

        manager.update_status(job_id, JobStatus.PROCESSING, progress=50)

        # ------------------------------------------------------------------
        # Step 4: Generate video
        # ------------------------------------------------------------------
        output_path = str(config.OUTPUTS_DIR / f"{job_id}.mp4")
        slideshow_path = str(config.OUTPUTS_DIR / f"{job_id}_slideshow.mp4")
        images_used = False

        if transcription_ok:
            # --- Try AI image generation ---
            try:
                _log(manager, job_id, "🖼️ Splitting transcript into scenes…")
                scenes = split_into_scenes(segments, scene_duration=5.0)
                _log(manager, job_id, f"   {len(scenes)} scenes created.")

                _log(manager, job_id, "🎨 Generating AI images (Pollinations.ai)…")

                def on_img_progress(i, total):
                    pct = 50 + int((i / total) * 20)  # 50% → 70%
                    manager.update_status(job_id, JobStatus.PROCESSING, progress=pct)
                    _log(manager, job_id, f"   🖼️ Image {i}/{total} ready.")

                scene_images = generate_scene_images(
                    scenes=scenes,
                    output_dir=str(config.OUTPUTS_DIR),
                    job_id=job_id,
                    on_progress=on_img_progress,
                )

                _log(manager, job_id, "🎬 Building slideshow video from AI images…")
                build_slideshow_video(scene_images, slideshow_path)
                images_used = True
                manager.update_status(job_id, JobStatus.PROCESSING, progress=75)

            except Exception as e:
                _log(manager, job_id, f"⚠️ AI images failed: {e}. Falling back to waveform.")
                logger.warning("Image generation failed for %s: %s", job_id, e)
                images_used = False

            # Fallback to waveform if images failed
            if not images_used:
                _log(manager, job_id, "🎬 Generating waveform video (fallback)…")
                generate_waveform_video(audio_path, slideshow_path, duration)
                manager.update_status(job_id, JobStatus.PROCESSING, progress=75)

            _log(manager, job_id, "📝 Burning subtitles + combining audio…")
            build_final_video(
                video_path=slideshow_path,
                audio_path=audio_path,
                output_path=output_path,
                srt_path=srt_path,
                duration=duration,
            )
            manager.update_status(
                job_id, JobStatus.PROCESSING, progress=90, srt_path=srt_path
            )

            # Clean up intermediate files
            _safe_delete(slideshow_path)
            if images_used:
                _cleanup_scene_images(job_id, str(config.OUTPUTS_DIR))
        else:
            # Fallback: simple video with static text
            _log(manager, job_id, "🎬 Generating simple video with fallback subtitles…")
            build_simple_video(
                audio_path=audio_path,
                output_path=output_path,
                duration=duration,
                subtitle_text="Faceless Video Generator",
            )
            manager.update_status(job_id, JobStatus.PROCESSING, progress=90)

        # ------------------------------------------------------------------
        # Step 5: Done!
        # ------------------------------------------------------------------
        _log(manager, job_id, "✅ Video generation complete!")
        manager.update_status(
            job_id,
            JobStatus.DONE,
            progress=100,
            output_path=output_path,
        )
        logger.info("Job %s completed successfully.", job_id)

    except PipelineError as e:
        _log(manager, job_id, f"❌ Pipeline error: {e}")
        manager.update_status(job_id, JobStatus.FAILED, error=str(e))
        logger.error("Job %s failed (pipeline): %s", job_id, e)

    except Exception as e:
        tb = traceback.format_exc()
        _log(manager, job_id, f"❌ Unexpected error: {e}")
        manager.update_status(job_id, JobStatus.FAILED, error=str(e))
        logger.error("Job %s failed (unexpected): %s\n%s", job_id, e, tb)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _log(manager: JobManager, job_id: str, message: str) -> None:
    logger.info("[%s] %s", job_id, message)
    manager.append_log(job_id, message)


def _safe_delete(path: str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass


def _cleanup_scene_images(job_id: str, output_dir: str) -> None:
    """Remove temporary scene images after video is built."""
    import glob
    for f in glob.glob(str(Path(output_dir) / f"{job_id}_scene_*.jpg")):
        _safe_delete(f)
