"""
Whisper Transcription — faster-whisper for GPU-accelerated speech-to-text.
"""

from __future__ import annotations

import torch
from faster_whisper import WhisperModel
from rich import print

from config import WHISPER_MODEL

# ── Singleton ───────────────────────────────────────────────────────────────
_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        _model = WhisperModel(WHISPER_MODEL, device=device, compute_type=compute_type)
        print(f"  Whisper loaded on {device.upper()}")
    return _model


def transcribe_segment(audio_path: str, language: str = "en") -> list[dict]:
    """
    Transcribe an audio/video segment.

    Parameters
    ----------
    audio_path : str
        Path to audio or video file.
    language : str
        Language code (default: 'en').

    Returns
    -------
    list[dict]
        Each dict has: start, end, text.
    """
    model = _get_model()

    segments_gen, info = model.transcribe(
        audio_path,
        beam_size=1,          # greedy decoding — ~2x faster, minimal quality loss
        language=language,
        vad_filter=True,      # skip silent sections automatically
        condition_on_previous_text=False,  # avoid context drift in short clips
    )

    results = []
    for seg in segments_gen:
        results.append({
            "start": float(seg.start),
            "end": float(seg.end),
            "text": seg.text.strip(),
        })

    return results


def transcribe_full(video_path: str, language: str = "en") -> str:
    """Transcribe an entire video and return full text."""
    segments = transcribe_segment(video_path, language)
    return " ".join(s["text"] for s in segments)
