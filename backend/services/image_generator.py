"""AI image generator – fetches images from Pollinations.ai (free, no API key)."""

from __future__ import annotations

import logging
import time
import urllib.parse
import urllib.request
from pathlib import Path

logger = logging.getLogger("fcg.image_generator")

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}?width={width}&height={height}&nologo=true&seed={seed}"

# Style suffix appended to every prompt for consistent cinematic look
STYLE_SUFFIX = ", cinematic lighting, digital art, vibrant colors, 4k, detailed background, no text, no watermark"


def generate_scene_images(
    scenes: list[dict],
    output_dir: str,
    job_id: str,
    width: int = 1280,
    height: int = 720,
    on_progress: callable = None,
) -> list[dict]:
    """
    Generate one AI image per scene using Pollinations.ai.

    Args:
        scenes: list of {"start": float, "end": float, "text": str}
        output_dir: directory to save images
        job_id: for unique filenames
        width/height: image dimensions
        on_progress: callback(i, total) for progress updates

    Returns:
        list of {"path": str, "start": float, "end": float, "duration": float}
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    results = []

    for i, scene in enumerate(scenes):
        text = scene["text"].strip()
        if not text:
            text = "abstract colorful background"

        # Build a visual prompt from the spoken text
        prompt = _text_to_visual_prompt(text)
        image_path = str(Path(output_dir) / f"{job_id}_scene_{i:03d}.jpg")

        try:
            logger.info("Generating image %d/%d: '%s'", i + 1, len(scenes), prompt[:80])
            _download_image(prompt, image_path, width, height, seed=i + 42)
            results.append({
                "path": image_path,
                "start": scene["start"],
                "end": scene["end"],
                "duration": scene["end"] - scene["start"],
            })
            logger.info("Image %d/%d saved: %s", i + 1, len(scenes), image_path)
        except Exception as e:
            logger.warning("Failed to generate image %d: %s", i + 1, e)
            # Generate a fallback solid-color image with FFmpeg
            _generate_fallback_image(image_path, width, height)
            results.append({
                "path": image_path,
                "start": scene["start"],
                "end": scene["end"],
                "duration": scene["end"] - scene["start"],
            })

        if on_progress:
            on_progress(i + 1, len(scenes))

        # Small delay between requests to be respectful to the API
        if i < len(scenes) - 1:
            time.sleep(1)

    return results


def split_into_scenes(segments: list[dict], scene_duration: float = 5.0) -> list[dict]:
    """
    Group transcript segments into scenes of approximately `scene_duration` seconds.
    Each scene gets combined text for image prompt generation.

    Returns: list of {"start": float, "end": float, "text": str}
    """
    if not segments:
        return []

    scenes = []
    current_start = segments[0]["start"]
    current_texts = []
    current_end = segments[0]["start"]

    for seg in segments:
        current_texts.append(seg["text"].strip())
        current_end = seg["end"]

        # If we've accumulated enough duration, close this scene
        if current_end - current_start >= scene_duration:
            scenes.append({
                "start": current_start,
                "end": current_end,
                "text": " ".join(current_texts),
            })
            current_start = current_end
            current_texts = []

    # Don't forget the last scene
    if current_texts:
        scenes.append({
            "start": current_start,
            "end": current_end,
            "text": " ".join(current_texts),
        })

    # Ensure minimum 1 scene
    if not scenes and segments:
        scenes.append({
            "start": segments[0]["start"],
            "end": segments[-1]["end"],
            "text": " ".join(s["text"].strip() for s in segments),
        })

    logger.info("Split %d segments into %d scenes", len(segments), len(scenes))
    return scenes


def _text_to_visual_prompt(text: str) -> str:
    """Convert spoken text into a visual image prompt."""
    # Clean up and limit length
    clean = text.strip().replace("\n", " ")
    # Truncate to avoid overly long URLs
    if len(clean) > 150:
        clean = clean[:150]
    return clean + STYLE_SUFFIX


def _download_image(prompt: str, output_path: str, width: int, height: int, seed: int = 42) -> None:
    """Download an AI-generated image from Pollinations.ai."""
    encoded_prompt = urllib.parse.quote(prompt)
    url = POLLINATIONS_URL.format(prompt=encoded_prompt, width=width, height=height, seed=seed)

    req = urllib.request.Request(url, headers={"User-Agent": "FCG/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        data = response.read()
        if len(data) < 1000:
            raise RuntimeError(f"Image too small ({len(data)} bytes), likely an error")
        Path(output_path).write_bytes(data)


def _generate_fallback_image(output_path: str, width: int, height: int) -> None:
    """Generate a simple gradient fallback image using FFmpeg."""
    import subprocess
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=#1a1a2e:s={width}x{height}:d=1",
        "-frames:v", "1",
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, timeout=15)
    logger.info("Fallback image generated: %s", output_path)
