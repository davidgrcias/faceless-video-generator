"""Transcription service – uses OpenAI Whisper locally."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("fcg.transcriber")

# We lazy-load whisper to avoid slow import at startup
_model = None
_model_name: str | None = None


def _get_model(model_name: str = "base"):
    """Load the Whisper model (cached after first call)."""
    global _model, _model_name
    if _model is None or _model_name != model_name:
        import whisper

        logger.info("Loading Whisper model '%s' …", model_name)
        _model = whisper.load_model(model_name)
        _model_name = model_name
        logger.info("Whisper model loaded.")
    return _model


def transcribe(audio_path: str, model_name: str = "base") -> dict:
    """
    Transcribe an audio file and return Whisper result dict.

    Returns dict with keys: 'text', 'segments', 'language'.
    Each segment has: 'start', 'end', 'text'.
    """
    model = _get_model(model_name)
    logger.info("Transcribing: %s", audio_path)
    result = model.transcribe(
        audio_path,
        word_timestamps=True,
        verbose=False,
    )
    logger.info(
        "Transcription complete – %d segments, language=%s",
        len(result.get("segments", [])),
        result.get("language", "?"),
    )
    return result


def generate_srt(segments: list[dict], output_path: str) -> str:
    """
    Convert Whisper segments to an SRT subtitle file.

    Returns the path to the generated SRT file.
    """
    lines: list[str] = []
    for idx, seg in enumerate(segments, start=1):
        start = _format_srt_time(seg["start"])
        end = _format_srt_time(seg["end"])
        text = seg["text"].strip()
        lines.append(f"{idx}")
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")  # blank line separator

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    logger.info("SRT written to %s (%d cues)", output_path, len(segments))
    return output_path


def generate_word_level_srt(segments: list[dict], output_path: str) -> str:
    """
    Generate word-level SRT for more dynamic subtitle display.
    Groups words into chunks of ~4-6 words for readability.
    """
    all_words: list[dict] = []
    for seg in segments:
        for word_info in seg.get("words", []):
            all_words.append(word_info)

    if not all_words:
        # Fallback to segment-level if no word timestamps
        return generate_srt(segments, output_path)

    # Group words into chunks of ~5 words
    chunk_size = 5
    chunks: list[dict] = []
    for i in range(0, len(all_words), chunk_size):
        group = all_words[i : i + chunk_size]
        chunks.append(
            {
                "start": group[0]["start"],
                "end": group[-1]["end"],
                "text": " ".join(w["word"].strip() for w in group),
            }
        )

    return generate_srt(chunks, output_path)


def _format_srt_time(seconds: float) -> str:
    """Format seconds to SRT timestamp: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
