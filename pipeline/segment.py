"""
Video Segmenter — Split video into fixed-duration chunks.

Uses FFmpeg for precise cutting and MoviePy for metadata.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from rich import print

from config import SEGMENTS_DIR, SEGMENT_DURATION


def segment_video(
    video_path: str,
    segment_duration: int = SEGMENT_DURATION,
) -> list[dict]:
    """
    Split a video into fixed-duration segments.

    Parameters
    ----------
    video_path : str
        Path to the input video file.
    segment_duration : int
        Duration of each segment in seconds (default: 10).

    Returns
    -------
    list[dict]
        Each dict has: segment_path, start_sec, end_sec, index.
    """
    video_path = Path(video_path)
    video_stem = video_path.stem

    # Get total duration via FFprobe
    total_duration = _get_duration(str(video_path))
    if total_duration <= 0:
        raise ValueError(f"Could not determine video duration: {video_path}")

    # Create output directory
    output_dir = SEGMENTS_DIR / video_stem
    output_dir.mkdir(parents=True, exist_ok=True)

    segments = []
    index = 0
    start = 0.0

    while start < total_duration:
        end = min(start + segment_duration, total_duration)
        segment_filename = f"{video_stem}_{index:04d}.mp4"
        segment_path = output_dir / segment_filename

        # FFmpeg precise cut — stream copy avoids re-encoding (much faster)
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", str(video_path),
            "-t", str(end - start),
            "-c", "copy",
            "-loglevel", "error",
            str(segment_path),
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"  [red]⚠ Segment {index} failed: {e.stderr.decode()[:200]}[/red]")
            start = end
            index += 1
            continue

        segments.append({
            "segment_path": str(segment_path),
            "start_sec": start,
            "end_sec": end,
            "index": index,
        })

        start = end
        index += 1

    print(f"  → Split into {len(segments)} segments ({segment_duration}s each)")
    return segments


def _get_duration(video_path: str) -> float:
    """Get video duration in seconds via FFprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0
