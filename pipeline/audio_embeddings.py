# pipeline/audio_embeddings.py
"""
Phase 5 Audio Embeddings & Diarization Module
Handles speaker diarization and audio speaker embeddings for segment records
"""

import os
import subprocess
import tempfile
import numpy as np
import torch
from scipy.io import wavfile
from pathlib import Path
from typing import Dict, Tuple
from rich import print
from dotenv import load_dotenv

load_dotenv()


def get_hf_token() -> str:
    """Retrieve HF_TOKEN from environment"""
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError(
            "HF_TOKEN not found. Set HF_TOKEN in .env file and accept model terms on Hugging Face: "
            "https://huggingface.co/pyannote/speaker-diarization-3.1"
        )
    return token


def extract_audio_waveform(video_path: str) -> Tuple[torch.Tensor, int]:
    """
    Extract mono 16kHz audio WAV from video using FFmpeg.
    Returns (waveform tensor, sample_rate)
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
        wav_path = tmp_wav.name

    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", video_path,
                "-ac", "1", "-ar", "16000", wav_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        sample_rate, pcm = wavfile.read(wav_path)
        
        # Handle multi-channel audio (average to mono)
        if pcm.ndim > 1:
            pcm = np.mean(pcm, axis=1)
        
        # Convert to float tensor [-1, 1] range
        waveform = torch.from_numpy(pcm).float()
        if waveform.abs().max() > 1.0:
            waveform = waveform / 32768.0
        
        return waveform, int(sample_rate)
    finally:
        # Clean up temp file
        if Path(wav_path).exists():
            try:
                Path(wav_path).unlink()
            except:
                pass


def diarize_audio(video_path: str) -> Dict[str, list[tuple[float, float]]]:
    """
    Perform speaker diarization on video audio.
    Returns dict: {speaker_label: [(start_sec, end_sec), ...]}
    """
    from pyannote.audio import Pipeline
    
    hf_token = get_hf_token()
    
    # Load diarization pipeline
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token=hf_token
    )
    
    # Use CPU for stability on Windows
    pipeline.to(torch.device("cpu"))
    
    # Extract audio waveform
    waveform, sample_rate = extract_audio_waveform(video_path)
    
    # Run diarization
    diarization_output = pipeline({
        "waveform": waveform.unsqueeze(0),
        "sample_rate": sample_rate
    })
    
    # Handle output wrapper (DiarizeOutput → Annotation)
    diarization = (
        diarization_output.speaker_diarization
        if hasattr(diarization_output, "speaker_diarization")
        else diarization_output
    )
    
    # Extract speaker segments
    speakers = {}
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        if speaker not in speakers:
            speakers[speaker] = []
        speakers[speaker].append((turn.start, turn.end))
    
    return speakers


def get_audio_embedding(video_path: str) -> torch.Tensor:
    """
    Generate audio speaker embedding for entire video.
    Returns tensor of shape (256,) - speaker embedding vector
    """
    from pyannote.audio import Model, Inference
    
    hf_token = get_hf_token()
    
    # Load embedding model (native pyannote)
    embedding_model = Model.from_pretrained(
        "pyannote/wespeaker-voxceleb-resnet34-LM",
        token=hf_token,
    )
    embedding_inference = Inference(embedding_model, window="whole")
    
    # Extract audio waveform
    waveform, sample_rate = extract_audio_waveform(video_path)
    
    # Generate embedding
    embedding = embedding_inference({
        "waveform": waveform.unsqueeze(0),
        "sample_rate": sample_rate,
    })
    
    return embedding


def get_speaker_for_segment(
    diarization: Dict[str, list[tuple[float, float]]],
    start_sec: float,
    end_sec: float,
    confidence_threshold: float = 0.5
) -> str:
    """
    Determine primary speaker for a segment based on diarization.
    Returns speaker label (e.g., 'SPEAKER_00') or 'UNKNOWN' if no clear speaker
    
    diarization: dict from diarize_audio(), {speaker_label: [(start, end), ...]}
    start_sec, end_sec: segment time bounds
    confidence_threshold: minimum overlap ratio to consider speaker
    """
    segment_duration = end_sec - start_sec
    speaker_durations = {}
    
    for speaker, segments in diarization.items():
        total_overlap = 0.0
        for seg_start, seg_end in segments:
            # Calculate overlap between speaker segment and target segment
            overlap_start = max(start_sec, seg_start)
            overlap_end = min(end_sec, seg_end)
            if overlap_end > overlap_start:
                total_overlap += overlap_end - overlap_start
        
        if total_overlap > 0:
            coverage = total_overlap / segment_duration
            if coverage >= confidence_threshold:
                speaker_durations[speaker] = total_overlap
    
    if not speaker_durations:
        return "UNKNOWN"
    
    # Return speaker with most overlap time
    return max(speaker_durations, key=speaker_durations.get)
