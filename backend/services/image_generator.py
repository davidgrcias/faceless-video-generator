"""
AI image generator — multi-provider with retry & beautiful fallbacks.

Provider priority:
  1. Pollinations.ai  (AI-generated, free, no key)
  2. Picsum.photos     (curated stock photos, free, no key)
  3. FFmpeg gradient   (locally generated, always works)
"""

from __future__ import annotations

import hashlib
import logging
import random
import subprocess
import time
import urllib.parse
from pathlib import Path

import requests

logger = logging.getLogger("fcg.image_generator")

# ---------------------------------------------------------------------------
# Provider URLs
# ---------------------------------------------------------------------------
POLLINATIONS_URL = (
    "https://image.pollinations.ai/prompt/{prompt}"
    "?width={width}&height={height}&nologo=true&seed={seed}"
)
PICSUM_URL = "https://picsum.photos/{width}/{height}"

# Style suffix for Pollinations prompts
STYLE_SUFFIX = (
    ", cinematic lighting, digital art, vibrant colors, "
    "4k, detailed background, no text, no watermark"
)

# Retry settings
MAX_RETRIES = 3
RETRY_BACKOFF = [3, 8, 15]  # seconds between retries
REQUEST_TIMEOUT = 120  # generous timeout for AI generation

# Gradient palette for fallback images (vibrant, not dark)
GRADIENT_COLORS = [
    ("#0f3460", "#e94560"),
    ("#1a1a2e", "#e94560"),
    ("#16213e", "#533483"),
    ("#0f0f23", "#e94560"),
    ("#1b262c", "#0f4c75"),
    ("#2d132c", "#ee4540"),
    ("#121212", "#1db954"),
    ("#0d1117", "#58a6ff"),
    ("#1c1c3c", "#f39c12"),
    ("#0b0b2b", "#00d2ff"),
]

# Session with connection pooling
_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
        })
    return _session


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_scene_images(
    scenes: list[dict],
    output_dir: str,
    job_id: str,
    width: int = 1280,
    height: int = 720,
    on_progress: callable = None,
) -> list[dict]:
    """
    Generate one image per scene using a multi-provider pipeline.

    Tries Pollinations.ai first (with retries), then Picsum, then FFmpeg gradient.

    Returns list of {"path", "start", "end", "duration"}.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    results = []

    for i, scene in enumerate(scenes):
        text = scene["text"].strip() or "abstract colorful background"
        image_path = str(Path(output_dir) / f"{job_id}_scene_{i:03d}.jpg")
        source = "none"

        # --- Provider 1: Pollinations.ai (AI-generated) ---
        try:
            prompt = _text_to_visual_prompt(text)
            logger.info(
                "Scene %d/%d — trying Pollinations.ai: '%.60s…'",
                i + 1, len(scenes), prompt,
            )
            _download_with_retry(
                _build_pollinations_url(prompt, width, height, seed=i + 42),
                image_path,
            )
            source = "pollinations"
        except Exception as e:
            logger.warning("Scene %d Pollinations failed: %s", i + 1, e)

        # --- Provider 2: Picsum.photos (stock photo) ---
        if source == "none":
            try:
                logger.info("Scene %d/%d — trying Picsum.photos…", i + 1, len(scenes))
                seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16) % 1000
                picsum_url = f"{PICSUM_URL.format(width=width, height=height)}?random={seed}"
                _download_with_retry(picsum_url, image_path, max_retries=2)
                source = "picsum"
            except Exception as e:
                logger.warning("Scene %d Picsum failed: %s", i + 1, e)

        # --- Provider 3: FFmpeg gradient (local, always works) ---
        if source == "none":
            logger.info("Scene %d/%d — generating local gradient…", i + 1, len(scenes))
            _generate_gradient_image(image_path, width, height, index=i)
            source = "gradient"

        results.append({
            "path": image_path,
            "start": scene["start"],
            "end": scene["end"],
            "duration": scene["end"] - scene["start"],
        })
        logger.info("Scene %d/%d ready [%s]: %s", i + 1, len(scenes), source, image_path)

        if on_progress:
            on_progress(i + 1, len(scenes))

        # Small delay between API calls
        if source in ("pollinations", "picsum") and i < len(scenes) - 1:
            time.sleep(1.5)

    return results


def split_into_scenes(segments: list[dict], scene_duration: float = 5.0) -> list[dict]:
    """
    Group transcript segments into scenes of ~`scene_duration` seconds.
    Returns list of {"start", "end", "text"}.
    """
    if not segments:
        return []

    scenes = []
    current_start = segments[0]["start"]
    current_texts: list[str] = []
    current_end = current_start

    for seg in segments:
        current_texts.append(seg["text"].strip())
        current_end = seg["end"]

        if current_end - current_start >= scene_duration:
            scenes.append({
                "start": current_start,
                "end": current_end,
                "text": " ".join(current_texts),
            })
            current_start = current_end
            current_texts = []

    # Remaining text
    if current_texts:
        scenes.append({
            "start": current_start,
            "end": current_end,
            "text": " ".join(current_texts),
        })

    # Safety net
    if not scenes and segments:
        scenes.append({
            "start": segments[0]["start"],
            "end": segments[-1]["end"],
            "text": " ".join(s["text"].strip() for s in segments),
        })

    logger.info("Split %d segments into %d scenes", len(segments), len(scenes))
    return scenes


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _text_to_visual_prompt(text: str) -> str:
    """Convert spoken text into a visual image prompt."""
    clean = text.strip().replace("\n", " ")
    if len(clean) > 150:
        clean = clean[:150]
    return clean + STYLE_SUFFIX


def _build_pollinations_url(prompt: str, width: int, height: int, seed: int) -> str:
    encoded = urllib.parse.quote(prompt, safe="")
    return POLLINATIONS_URL.format(
        prompt=encoded, width=width, height=height, seed=seed,
    )


def _download_with_retry(
    url: str,
    output_path: str,
    max_retries: int = MAX_RETRIES,
    min_bytes: int = 5000,
) -> None:
    """Download a URL to a file with exponential-backoff retries."""
    session = _get_session()
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            resp.raise_for_status()
            data = resp.content

            if len(data) < min_bytes:
                raise RuntimeError(
                    f"Response too small ({len(data)} bytes), likely not a real image"
                )

            # Validate it looks like an image (JPEG/PNG magic bytes)
            if not (data[:2] == b"\xff\xd8"       # JPEG
                    or data[:4] == b"\x89PNG"      # PNG
                    or data[:4] == b"RIFF"         # WEBP
                    ):
                raise RuntimeError("Response is not a valid image file")

            Path(output_path).write_bytes(data)
            return  # success

        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                logger.info(
                    "  Retry %d/%d in %ds — %s", attempt + 1, max_retries, wait, e,
                )
                time.sleep(wait)

    raise RuntimeError(f"All {max_retries} download attempts failed: {last_error}")


def _generate_gradient_image(
    output_path: str,
    width: int,
    height: int,
    index: int = 0,
) -> None:
    """Generate a beautiful gradient image using FFmpeg (always works locally)."""
    colors = GRADIENT_COLORS[index % len(GRADIENT_COLORS)]
    c1, c2 = colors

    # Create a two-tone gradient with overlapping rectangles
    # Top half = color1, bottom half = color2, middle = blended overlay
    mid = height // 2
    band = height // 4

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", (
            f"color=c={c1}:s={width}x{height}:d=1,"
            f"drawbox=x=0:y={mid - band}:w={width}:h={mid + band}:color={c2}@0.5:t=fill,"
            f"drawbox=x=0:y={mid}:w={width}:h={mid}:color={c2}@0.85:t=fill,"
            # Add some visual interest with a subtle lighter strip
            f"drawbox=x={width // 4}:y={mid - 2}:w={width // 2}:h=4:color=white@0.08:t=fill"
        ),
        "-frames:v", "1",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=15)
    if result.returncode != 0:
        # Ultra-fallback: simplest possible command
        cmd_simple = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c={c1}:s={width}x{height}:d=1",
            "-frames:v", "1",
            output_path,
        ]
        subprocess.run(cmd_simple, capture_output=True, timeout=15)
    logger.info("Gradient image generated: %s", output_path)
