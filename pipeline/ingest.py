"""
Video Ingestion Pipeline — End-to-end processing.

Orchestrates: segment → transcribe → caption → fuse → save records.
Also provides load_records() for retrieving saved segment data.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Callable, Optional

from pydantic import BaseModel, Field
from rich import print
from rich.progress import track

from config import (
    RECORDS_DIR,
    TRANSCRIPTS_DIR,
    VIDEOS_DIR,
)
from pipeline.segment import segment_video
from pipeline.transcribe import transcribe_segment
from pipeline.caption import extract_frames, caption_frames
from pipeline.fuse import extract_emotion_signals


# ── Data Model ──────────────────────────────────────────────────────────────
class SegmentRecord(BaseModel):
    """Pydantic model matching the JSON record format on disk."""

    segment_id: str
    video_id: str
    start_sec: float
    end_sec: float
    transcript: str
    visual_captions: list[str] = Field(default_factory=list)
    combined_text: str = ""
    frame_paths: list[str] = Field(default_factory=list)
    segment_path: str = ""
    metadata: dict = Field(default_factory=dict)
    speaker: Optional[str] = None
    speaker_embedding: Optional[list[float]] = None


# ── Load Records ────────────────────────────────────────────────────────────
def load_records(video_id: str | None = None) -> list[SegmentRecord]:
    """
    Load segment records from disk.

    Parameters
    ----------
    video_id : str or None
        If provided, load only records for this video.
        If None, load all records.

    Returns
    -------
    list[SegmentRecord]
    """
    records = []

    if not RECORDS_DIR.exists():
        return records

    for path in sorted(RECORDS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            record = SegmentRecord(**data)

            if video_id is None or video_id in record.video_id:
                records.append(record)
        except Exception:
            continue

    return records


# ── Ingestion Pipeline ──────────────────────────────────────────────────────
def ingest_video(
    video_path: str,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    enable_diarization: bool = False,
    enable_captioning: bool = False,
) -> list[SegmentRecord]:
    """
    Full ingestion pipeline for a video file.

    Optimized pipeline:
      1. Segment video into 10s chunks (stream copy, no re-encode)
      2. Transcribe full video ONCE with Whisper, then map by timestamp
      3. Extract frames and generate captions (only if enable_captioning)
      4. Detect emotions from transcript + visuals (pure Python, fast)
      5. Speaker diarization (only if enable_diarization)
      6. Fuse into SegmentRecords and save to disk + rebuild search indexes

    Parameters
    ----------
    video_path : str
        Path to the video file.
    progress_callback : callable, optional
        Function(progress: float, stage: str) for progress updates.
    enable_diarization : bool
        Whether to run speaker diarization (slow, requires HF_TOKEN).
    enable_captioning : bool
        Whether to run visual frame captioning (slow, requires BLIP model).
        Set to True only for 'full' processing mode.

    Returns
    -------
    list[SegmentRecord]
        The created segment records.
    """
    video_path = Path(video_path)
    video_id = f"{uuid.uuid4().hex[:8]}_{video_path.stem}"

    def _progress(pct: float, msg: str):
        if progress_callback:
            progress_callback(pct, msg)
        print(f"  [{pct:.0f}%] {msg}")

    _progress(5, "Starting ingestion")

    # ── Step 1: Segment ─────────────────────────────────────────────────
    _progress(10, "Segmenting video (stream copy)")
    segments = segment_video(str(video_path))

    if not segments:
        raise ValueError("No segments produced — check video file")

    # ── Step 2: Transcribe full video ONCE, map to segments ─────────────
    # Much faster: one Whisper pass on the whole video vs N separate calls.
    _progress(20, "Transcribing full video with Whisper (single pass)")
    try:
        full_results = transcribe_segment(str(video_path))  # runs on full video
    except Exception as e:
        print(f"  [yellow]⚠ Full-video transcription failed ({e}), falling back to per-segment[/yellow]")
        full_results = None

    all_transcript_parts = []

    if full_results:
        # Map whisper word-level segments → 10s buckets
        for i, seg in enumerate(segments):
            seg_start = seg["start_sec"]
            seg_end = seg["end_sec"]
            # Collect whisper segments whose midpoint falls inside this bucket
            matching = [
                r["text"] for r in full_results
                if r["end"] > seg_start and r["start"] < seg_end
            ]
            seg["transcript"] = " ".join(matching).strip()
            all_transcript_parts.append(seg["transcript"])
            pct = 20 + (40 * (i + 1) / len(segments))
            _progress(pct, f"Mapped transcript to segment {i + 1}/{len(segments)}")
    else:
        # Fallback: transcribe each segment individually
        for i, seg in enumerate(segments):
            seg_results = transcribe_segment(seg["segment_path"])
            seg["transcript"] = " ".join(r["text"] for r in seg_results)
            all_transcript_parts.append(seg["transcript"])
            pct = 20 + (40 * (i + 1) / len(segments))
            _progress(pct, f"Transcribed segment {i + 1}/{len(segments)}")

    # Save full transcript
    transcript_path = TRANSCRIPTS_DIR / f"{video_id}_transcript.json"
    transcript_path.write_text(
        json.dumps({"video_id": video_id, "segments": all_transcript_parts}, indent=2),
        encoding="utf-8",
    )

    # ── Step 3: Visual Captioning (only for 'full' mode) ─────────────────
    if enable_captioning:
        _progress(60, "Extracting frames (full mode)")
        all_frame_paths = []
        for i, seg in enumerate(segments):
            seg_id = f"{video_id}_seg{seg['index']:04d}"
            frame_paths = extract_frames(
                seg["segment_path"], video_id, seg_id, num_frames=3,
            )
            seg["frame_paths"] = frame_paths
            all_frame_paths.extend(frame_paths)
            
        _progress(62, "Generating captions (batch processing)")
        all_captions = caption_frames(all_frame_paths) if all_frame_paths else []
        
        caption_idx = 0
        for seg in segments:
            num_frames = len(seg.get("frame_paths", []))
            seg["visual_captions"] = all_captions[caption_idx:caption_idx + num_frames]
            caption_idx += num_frames
    else:
        # Skip BLIP model entirely — saves multiple minutes on CPU
        for seg in segments:
            seg["frame_paths"] = []
            seg["visual_captions"] = []

    # ── Step 4: Emotion Extraction (pure Python, fast) ───────────────────
    _progress(65, "Detecting emotions")
    for seg in segments:
        emotion_data = extract_emotion_signals(
            seg["transcript"],
            seg.get("visual_captions", []),
        )
        seg["emotions"] = emotion_data

    # ── Step 5: Speaker Diarization (only if enabled) ────────────────────
    diarization_map = None
    if enable_diarization:
        _progress(75, "Running speaker diarization")
        try:
            from pipeline.audio_embeddings import diarize_audio, get_speaker_for_segment
            diarization_map = diarize_audio(str(video_path))
        except Exception as e:
            print(f"  [yellow]⚠ Diarization skipped: {e}[/yellow]")

    # ── Step 6: Build and Save Records ──────────────────────────────────
    _progress(80, "Saving segment records")
    records = []

    for seg in segments:
        seg_id = f"{video_id}_seg{seg['index']:04d}"
        emotion_data = seg.get("emotions", {})
        captions = seg.get("visual_captions", [])

        # Build combined text
        emotion_parts = []
        for emo in emotion_data.get("detected_emotions", []):
            conf = emotion_data.get("emotion_scores", {}).get(emo, 0)
            emotion_parts.append(f"{emo}({conf:.2f})")
        emotion_str = ", ".join(emotion_parts) if emotion_parts else "neutral"

        combined = (
            f"[TRANSCRIPT] {seg['transcript']} "
            f"[VISUAL] {' | '.join(captions)} "
            f"[EMOTIONS] {emotion_str}"
        )

        # Determine speaker
        speaker = None
        if diarization_map:
            try:
                speaker = get_speaker_for_segment(
                    diarization_map, seg["start_sec"], seg["end_sec"]
                )
            except Exception:
                pass

        record = SegmentRecord(
            segment_id=seg_id,
            video_id=video_id,
            start_sec=seg["start_sec"],
            end_sec=seg["end_sec"],
            transcript=seg["transcript"],
            visual_captions=captions,
            combined_text=combined,
            frame_paths=seg.get("frame_paths", []),
            segment_path=seg["segment_path"],
            metadata={
                "index": seg["index"],
                "emotions": emotion_data.get("detected_emotions", []),
                "emotion_scores": emotion_data.get("emotion_scores", {}),
                "visual_emotions": emotion_data.get("visual_emotions", []),
                "visual_scores": emotion_data.get("visual_scores", {}),
                "emotion_intensity": emotion_data.get("emotion_intensity", 0),
                "avg_emotion_confidence": emotion_data.get("avg_emotion_confidence", 0),
                "has_reaction": emotion_data.get("emotion_intensity", 0) > 0,
            },
            speaker=speaker,
        )

        # Save record to disk
        record_path = RECORDS_DIR / f"{seg_id}.json"
        record_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        records.append(record)

    _progress(90, "Building search indexes")

    # Rebuild search indexes
    try:
        from embed.bm25_index import build_bm25_index
        from embed.store import rebuild_dense_index

        all_records = load_records()  # Load everything for full index
        build_bm25_index(all_records)
        rebuild_dense_index(all_records)
    except Exception as e:
        print(f"  [yellow]⚠ Index rebuild skipped: {e}[/yellow]")

    _progress(100, "Ingestion complete")
    print(f"  ✓ Ingested {len(records)} segments for video {video_id}")

    return records
