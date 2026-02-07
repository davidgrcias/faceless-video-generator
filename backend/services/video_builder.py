"""Video builder – FFmpeg-based video assembly."""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

import config

logger = logging.getLogger("fcg.video_builder")


def check_ffmpeg() -> bool:
    """Return True if ffmpeg is available on PATH."""
    return shutil.which("ffmpeg") is not None


def get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def generate_background_image(output_path: str, width: int, height: int) -> str:
    """
    Generate a dark gradient background image using FFmpeg.
    Creates a visually appealing background without external dependencies.
    """
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", (
            f"color=c=#1a1a2e:s={width}x{height}:d=1,"
            f"drawbox=x=0:y=0:w={width}:h={height // 3}:color=#16213e@0.8:t=fill,"
            f"drawbox=x=0:y={height * 2 // 3}:w={width}:h={height // 3}:color=#0f3460@0.6:t=fill"
        ),
        "-frames:v", "1",
        output_path,
    ]
    _run_ffmpeg(cmd, "generate background image")
    return output_path


def generate_waveform_video(
    audio_path: str,
    output_path: str,
    duration: float,
    width: int = config.VIDEO_WIDTH,
    height: int = config.VIDEO_HEIGHT,
    fps: int = config.VIDEO_FPS,
) -> str:
    """
    Generate a video with an audio-reactive waveform visualisation.
    Creates a dark background with a centered waveform.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", audio_path,
        "-filter_complex",
        (
            f"color=c=#0f0f23:s={width}x{height}:d={duration}:r={fps}[bg];"
            f"[0:a]showwaves=s={width}x{height // 4}:mode=cline:rate={fps}"
            f":colors=#e94560|#533483:scale=sqrt[wave];"
            f"[bg][wave]overlay=0:(H-h)/2:format=auto[v]"
        ),
        "-map", "[v]",
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        output_path,
    ]
    _run_ffmpeg(cmd, "generate waveform video")
    return output_path


def build_final_video(
    video_path: str,
    audio_path: str,
    output_path: str,
    srt_path: str | None = None,
    duration: float | None = None,
) -> str:
    """
    Combine video track + audio track, optionally burn subtitles.
    Outputs an H.264 + AAC MP4.
    """
    # Build the filter chain
    vf_filters: list[str] = []

    if srt_path:
        # Escape path for FFmpeg subtitles filter (Windows needs special handling)
        safe_srt = srt_path.replace("\\", "/").replace(":", "\\:")
        vf_filters.append(
            f"subtitles='{safe_srt}'"
            f":force_style='FontSize={config.FONT_SIZE},"
            f"PrimaryColour=&H00FFFFFF,"
            f"OutlineColour=&H00000000,"
            f"Outline=2,"
            f"Shadow=1,"
            f"BackColour=&H80000000,"
            f"Alignment=2,"
            f"MarginV=50,"
            f"FontName=Arial'"
        )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
    ]

    if vf_filters:
        cmd.extend(["-vf", ",".join(vf_filters)])

    cmd.extend([
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_path,
    ])

    _run_ffmpeg(cmd, "build final video")
    return output_path


def build_simple_video(
    audio_path: str,
    output_path: str,
    duration: float,
    subtitle_text: str = "Sample subtitle",
    width: int = config.VIDEO_WIDTH,
    height: int = config.VIDEO_HEIGHT,
    fps: int = config.VIDEO_FPS,
) -> str:
    """
    Fallback: build a simple video with static text overlay.
    Used when transcription fails or as MVP baseline.
    """
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=#1a1a2e:s={width}x{height}:d={duration}:r={fps}",
        "-i", audio_path,
        "-vf", (
            f"drawtext=text='{_escape_ffmpeg_text(subtitle_text)}'"
            f":fontsize={config.FONT_SIZE}"
            f":fontcolor=white"
            f":x=(w-tw)/2:y=(h-th)/2"
            f":borderw=2:bordercolor=black"
        ),
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_path,
    ]
    _run_ffmpeg(cmd, "build simple video")
    return output_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _run_ffmpeg(cmd: list[str], description: str) -> subprocess.CompletedProcess:
    """Run an FFmpeg command with proper error handling."""
    logger.info("FFmpeg [%s]: %s", description, " ".join(cmd[:6]) + " …")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,  # 5 min max
    )
    if result.returncode != 0:
        error_msg = result.stderr[-2000:] if result.stderr else "Unknown error"
        logger.error("FFmpeg failed [%s]: %s", description, error_msg)
        raise RuntimeError(f"FFmpeg failed ({description}): {error_msg}")
    logger.info("FFmpeg [%s] completed successfully.", description)
    return result


def _escape_ffmpeg_text(text: str) -> str:
    """Escape special characters for FFmpeg drawtext filter."""
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "'\\''") 
    text = text.replace(":", "\\:")
