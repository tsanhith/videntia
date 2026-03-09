"""
Frame Captioning — Extract key frames and generate visual descriptions.

Uses BLIP-2 or Moondream for generating forensic-style captions.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from rich import print

from config import FRAMES_DIR

# ── BLIP singleton cache (load once, reuse across calls) ────────────────────
_blip_processor = None
_blip_model = None


def _get_blip():
    global _blip_processor, _blip_model
    if _blip_processor is None:
        from PIL import Image  # noqa: F401 — ensure PIL available
        from transformers import BlipProcessor, BlipForConditionalGeneration
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"  Loading BLIP captioning model on {device.upper()} (once)...")
        _blip_processor = BlipProcessor.from_pretrained(
            "Salesforce/blip-image-captioning-base"
        )
        _blip_model = BlipForConditionalGeneration.from_pretrained(
            "Salesforce/blip-image-captioning-base"
        ).to(device)
    return _blip_processor, _blip_model


def extract_frames(
    segment_path: str,
    video_stem: str,
    segment_id: str,
    num_frames: int = 3,
) -> list[str]:
    """
    Extract key frames from a video segment using FFmpeg.

    Parameters
    ----------
    segment_path : str
        Path to the segment video file.
    video_stem : str
        Identifier for the video (for directory naming).
    segment_id : str
        Segment identifier (for file naming).
    num_frames : int
        Number of frames to extract (default 3).

    Returns
    -------
    list[str]
        Paths to extracted frame images.
    """
    output_dir = FRAMES_DIR / video_stem
    output_dir.mkdir(parents=True, exist_ok=True)

    frame_paths = []
    for i in range(num_frames):
        frame_path = output_dir / f"{segment_id}_frame{i}.jpg"
        # Extract frame at evenly spaced intervals
        # For a 10s segment: frame0=1s, frame1=5s, frame2=9s
        time_offset = (i + 0.5) * (10.0 / num_frames)

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(time_offset),
            "-i", str(segment_path),
            "-frames:v", "1",
            "-q:v", "2",
            "-loglevel", "error",
            str(frame_path),
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            if frame_path.exists():
                frame_paths.append(str(frame_path))
        except subprocess.CalledProcessError:
            pass

    return frame_paths


def caption_frames(frame_paths: list[str]) -> list[str]:
    """
    Generate forensic-style captions for extracted frames.

    Uses BLIP-2 or a lightweight captioning model. Falls back to
    basic descriptions if the model is not available.

    Parameters
    ----------
    frame_paths : list[str]
        Paths to frame images.

    Returns
    -------
    list[str]
        Captions describing each frame.
    """
    try:
        return _caption_with_blip(frame_paths)
    except Exception as e:
        print(f"  [yellow]⚠ Captioning fallback (model unavailable): {e}[/yellow]")
        return [f"a forensic image showing frame {i}" for i in range(len(frame_paths))]


def _caption_with_blip(frame_paths: list[str], batch_size: int = 16) -> list[str]:
    """Generate captions using cached BLIP model with batched inference."""
    from PIL import Image
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor, model = _get_blip()

    all_captions = []
    for i in range(0, len(frame_paths), batch_size):
        batch_paths = frame_paths[i:i + batch_size]
        images = []
        valid_indices = []
        
        for idx, path in enumerate(batch_paths):
            try:
                img = Image.open(path).convert("RGB")
                images.append(img)
                valid_indices.append(idx)
            except Exception:
                pass
                
        if not images:
            all_captions.extend(["a forensic image (caption unavailable)"] * len(batch_paths))
            continue
            
        try:
            inputs = processor(
                images=images,
                text=["a forensic image showing"] * len(images),
                return_tensors="pt",
                padding=True,
            ).to(device)

            with torch.no_grad():
                outputs = model.generate(**inputs, max_new_tokens=50)

            decoded = processor.batch_decode(outputs, skip_special_tokens=True)
            
            # Map back to original indices in case some images failed
            batch_captions = ["a forensic image (caption unavailable)"] * len(batch_paths)
            for j, valid_idx in enumerate(valid_indices):
                batch_captions[valid_idx] = decoded[j].strip()
                
            all_captions.extend(batch_captions)
        except Exception as e:
            print(f"  [yellow]⚠ Batch captioning failed: {e}[/yellow]")
            all_captions.extend(["a forensic image (caption unavailable)"] * len(batch_paths))

    return all_captions
