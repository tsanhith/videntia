"""
NoteGPT Transcript Ingestion — Optimized for political/news interview content.

Parses the NoteGPT timestamp format (HH:MM:SS blocks) and creates overlapping
30-second sliding-window segments for richer context retrieval.

Usage:
    python ingest_notegpt.py
    python ingest_notegpt.py --video "path/to/video.mp4" --transcript "path/to/transcript.txt"
"""

from __future__ import annotations

import argparse
import json
import re
import uuid
from pathlib import Path

from config import RECORDS_DIR
from pipeline.fuse import extract_emotion_signals
from pipeline.ingest import SegmentRecord, load_records
from embed.bm25_index import build_bm25_index
from embed.store import rebuild_dense_index


# ---------------------------------------------------------------------------
# Transcript Parser
# ---------------------------------------------------------------------------

def parse_notegpt_transcript(path: str) -> list[dict]:
    """
    Parse NoteGPT-style transcript with HH:MM:SS timestamp blocks.

    Format:
        00:00:00
        Text of what was said...
        00:00:32
        More text...

    Returns list of dicts: {start_sec, text}
    """
    content = Path(path).read_text(encoding="utf-8").strip()

    # Split on lines that look like timestamps: 00:00:00 or 0:00:00
    parts = re.split(r"\n((?:\d+:)?\d{2}:\d{2})\n", content)

    blocks = []

    # parts = [possible_preamble, ts1, text1, ts2, text2, ...]
    # If content starts with a timestamp, parts[0] is empty
    for i in range(1, len(parts) - 1, 2):
        ts_str = parts[i].strip()
        text = parts[i + 1].strip()
        if not text:
            continue
        start_sec = _ts_to_sec(ts_str)
        blocks.append({"start_sec": start_sec, "text": text})

    # Infer end times from next block's start (last block ends +30s)
    for i, blk in enumerate(blocks):
        if i + 1 < len(blocks):
            blk["end_sec"] = blocks[i + 1]["start_sec"]
        else:
            blk["end_sec"] = blk["start_sec"] + 30.0

    return blocks


def _ts_to_sec(ts: str) -> float:
    parts = ts.split(":")
    parts = [float(p) for p in parts]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0]


# ---------------------------------------------------------------------------
# Segment Builder — Overlapping 30s windows
# ---------------------------------------------------------------------------

def build_overlapping_segments(
    blocks: list[dict],
    window_sec: float = 30.0,
    stride_sec: float = 15.0,
) -> list[dict]:
    """
    Build overlapping sliding-window segments from parsed transcript blocks.

    Overlapping windows mean that important statements near a boundary
    appear in multiple segments — improving retrieval recall significantly
    compared to hard cuts.

    Parameters
    ----------
    blocks : list[dict]
        Parsed transcript blocks from parse_notegpt_transcript().
    window_sec : float
        Width of each window in seconds (default 30s).
    stride_sec : float
        Step size between windows in seconds (default 15s).

    Returns
    -------
    list[dict]
        Each dict contains: index, start_sec, end_sec, transcript
    """
    if not blocks:
        return []

    total_duration = blocks[-1]["end_sec"]
    segments = []
    idx = 0
    win_start = 0.0

    while win_start < total_duration:
        win_end = win_start + window_sec

        # Collect all blocks whose text overlaps with this window
        texts = []
        for blk in blocks:
            if blk["start_sec"] < win_end and blk["end_sec"] > win_start:
                texts.append(blk["text"])

        transcript = " ".join(texts).strip()

        if transcript:
            segments.append({
                "index": idx,
                "start_sec": win_start,
                "end_sec": min(win_end, total_duration),
                "transcript": transcript,
            })
            idx += 1

        win_start += stride_sec

    return segments


# ---------------------------------------------------------------------------
# Main Ingestion
# ---------------------------------------------------------------------------

def ingest_notegpt(
    video_path: str,
    transcript_path: str,
    window_sec: float = 30.0,
    stride_sec: float = 15.0,
    clear_existing: bool = False,
) -> str:
    """
    Ingest a video + NoteGPT transcript into the Videntia retrieval system.

    Creates overlapping segment records, extracts emotions, and rebuilds
    all search indexes (BM25 + ChromaDB dense vectors).

    Returns
    -------
    str
        The video_id for querying.
    """
    print(f"\n{'='*60}")
    print(f"NoteGPT Ingestion")
    print(f"  Video:      {video_path}")
    print(f"  Transcript: {transcript_path}")
    print(f"  Window:     {window_sec}s  Stride: {stride_sec}s")
    print(f"{'='*60}\n")

    video_stem = Path(video_path).stem
    video_id = f"{uuid.uuid4().hex[:8]}_{video_stem[:30]}"
    print(f"Video ID: {video_id}")

    # Step 1: Parse transcript
    print("\n[1/4] Parsing NoteGPT transcript...")
    blocks = parse_notegpt_transcript(transcript_path)
    print(f"  → {len(blocks)} timestamp blocks parsed")

    # Step 2: Build overlapping segments
    print(f"\n[2/4] Building overlapping {window_sec}s segments (stride={stride_sec}s)...")
    segments = build_overlapping_segments(blocks, window_sec=window_sec, stride_sec=stride_sec)
    print(f"  → {len(segments)} segments created")

    # Optional: wipe existing records for this video
    if clear_existing:
        for p in RECORDS_DIR.glob(f"{video_id}_*.json"):
            p.unlink()
        print(f"  Cleared existing records for {video_id}")

    # Step 3: Extract emotions and build SegmentRecords
    print("\n[3/4] Extracting emotions and building records...")
    records = []

    for seg in segments:
        seg_id = f"{video_id}_seg{seg['index']:04d}"
        transcript = seg["transcript"]
        start_sec = seg["start_sec"]
        end_sec = seg["end_sec"]

        # Emotion extraction
        emotion_data = extract_emotion_signals(transcript, [])

        # Build enriched combined_text for BM25 & dense search
        emotion_parts = []
        for emo in emotion_data.get("detected_emotions", []):
            conf = emotion_data.get("emotion_scores", {}).get(emo, 0)
            emotion_parts.append(f"{emo}({conf:.2f})")
        emotion_str = ", ".join(emotion_parts) if emotion_parts else "neutral"

        # Richer combined text: timestamp context helps temporal queries
        time_label = f"{int(start_sec)//60}:{int(start_sec)%60:02d}-{int(end_sec)//60}:{int(end_sec)%60:02d}"
        combined = (
            f"[TIME: {time_label}] "
            f"[TRANSCRIPT] {transcript} "
            f"[EMOTIONS] {emotion_str}"
        )

        record = SegmentRecord(
            segment_id=seg_id,
            video_id=video_id,
            start_sec=float(start_sec),
            end_sec=float(end_sec),
            transcript=transcript,
            visual_captions=[],
            combined_text=combined,
            frame_paths=[],
            segment_path="",
            metadata={
                "index": seg["index"],
                "emotions": emotion_data.get("detected_emotions", []),
                "emotion_scores": emotion_data.get("emotion_scores", {}),
                "visual_emotions": [],
                "visual_scores": {},
                "emotion_intensity": float(emotion_data.get("emotion_intensity", 0)),
                "avg_emotion_confidence": float(emotion_data.get("avg_emotion_confidence", 0)),
                "has_reaction": emotion_data.get("emotion_intensity", 0) > 0,
            },
            speaker=None,
        )

        record_path = RECORDS_DIR / f"{seg_id}.json"
        record_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        records.append(record)

        pct = int(100 * (seg["index"] + 1) / len(segments))
        print(f"  [{pct:3d}%] {seg_id}  {time_label}  "
              f"({len(transcript)} chars)  emotions={emotion_str[:40]}")

    print(f"  → {len(records)} records saved to {RECORDS_DIR}")

    # Step 4: Rebuild search indexes
    print("\n[4/4] Rebuilding search indexes (BM25 + ChromaDB)...")
    all_records = load_records()
    print(f"  Total records on disk: {len(all_records)}")

    build_bm25_index(all_records)
    print("  ✓ BM25 index rebuilt")

    rebuild_dense_index(all_records)
    print("  ✓ Dense (ChromaDB) index rebuilt")

    print(f"\n{'='*60}")
    print(f"Ingestion complete!")
    print(f"  video_id : {video_id}")
    print(f"  segments : {len(records)}")
    print(f"{'='*60}\n")

    # Save video_id to a file so run_iran_tests.py can pick it up automatically
    vid_ref = Path(__file__).parent / "data" / "last_video_id.txt"
    vid_ref.parent.mkdir(parents=True, exist_ok=True)
    vid_ref.write_text(video_id, encoding="utf-8")

    return video_id


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest NoteGPT transcript into Videntia")
    parser.add_argument(
        "--video",
        default=r"C:\Users\abhi\Downloads\Iran_s_survival_strategy_against_US_control_Global_News_Podcast_480P.mp4",
        help="Path to the video file",
    )
    parser.add_argument(
        "--transcript",
        default=r"C:\Users\abhi\Downloads\NoteGPT_TRANSCRIPT_Iran's survival strategy with time text.txt",
        help="Path to the NoteGPT transcript (.txt)",
    )
    parser.add_argument("--window", type=float, default=30.0, help="Segment window in seconds")
    parser.add_argument("--stride", type=float, default=15.0, help="Segment stride in seconds")
    parser.add_argument("--clear", action="store_true", help="Clear existing records for this video")
    args = parser.parse_args()

    ingest_notegpt(
        video_path=args.video,
        transcript_path=args.transcript,
        window_sec=args.window,
        stride_sec=args.stride,
        clear_existing=args.clear,
    )
