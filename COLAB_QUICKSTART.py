"""
QUICK START: Copy-paste this into Google Colab and run!
No installation needed - Colab has everything pre-installed

Instructions:
1. Go to https://colab.research.google.com
2. Create new notebook
3. Copy this entire code
4. Set your environment variables
5. Run the cells
6. Watch your GPU process videos for FREE!
"""

# =====================================================
# CELL 1: Install & Import
# =====================================================

!pip install -q faster-whisper pydantic supabase httpx uvicorn
!pip install -q torch --index-url https://download.pytorch.org/whl/cu118
!pip install -q sentence-transformers FlagEmbedding
!pip install -q "pyannote.audio @ git+https://github.com/pyannote/pyannote-audio.git"
!pip install -q pyngrok

import os
from google.colab import drive

# Mount Google Drive (for long-term storage)
drive.mount('/content/drive')

# =====================================================
# CELL 2: Setup Environment
# =====================================================

# Set your credentials (get from Supabase dashboard)
os.environ["SUPABASE_URL"] = "https://your-project.supabase.co"
os.environ["SUPABASE_KEY"] = "your-anon-key-here"
os.environ["API_BASE"] = "https://your-huggingface-space.hf.space"
os.environ["NGROK_TOKEN"] = "your-ngrok-token"
os.environ["HF_TOKEN"] = "hf_your-huggingface-token"

# Accept HuggingFace agreements (required for pyannote)
from huggingface_hub import accept_agreement
try:
    accept_agreement("https://huggingface.co/pyannote/segmentation")
    accept_agreement("https://huggingface.co/pyannote/speaker-diarization-3.0")
    print("✓ HuggingFace licenses accepted")
except:
    print("⚠ HuggingFace agreement issue (may not matter)")

# =====================================================
# CELL 3: Setup Ngrok Tunnel (for webhooks)
# =====================================================

from pyngrok import ngrok
import time

# Create tunnel to localhost:8000
public_url = ngrok.connect(8000)
print(f"🌐 Public URL for webhooks: {public_url}")

# Save for later use
WEBHOOK_URL = str(public_url)

# =====================================================
# CELL 4: Load Models (GPU-accelerated)
# =====================================================

import torch
from faster_whisper import WhisperModel
from sentence_transformers import SentenceTransformer
from FlagEmbedding import FlagReranker
from pyannote.audio import Pipeline

print(f"GPU Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU Name: {torch.cuda.get_device_name(0)}")

print("Loading models (first time ~2-3 min)...")

# Transcription model (base, faster)
whisper = WhisperModel("base", device="cuda", compute_type="float16")
print("✓ Whisper loaded")

# Embeddings (local, fast)
embed_model = SentenceTransformer(
    "nomic-ai/nomic-embed-text-v1.5",
    device="cuda"
)
print("✓ Embeddings model loaded")

# Reranker
reranker = FlagReranker(
    "BAAI/bge-reranker-v2-m3",
    use_fp16=True,
    query_instruction_length=4
)
print("✓ Reranker loaded")

# Speaker diarization (requires GPU)
diarization = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.0",
    token=os.environ.get("HF_TOKEN")
)
print("✓ Speaker diarization loaded")

print("\n✅ All models loaded! Ready to process videos.")

# =====================================================
# CELL 5: Download & Process Your Video
# =====================================================

# Option 1: Download from URL
VIDEO_URL = "https://your-video-url.mp4"

# Option 2: Upload from your computer
from google.colab import files
print("Upload a video file:")
uploaded = files.upload()
video_path = list(uploaded.keys())[0] if uploaded else None

if not video_path:
    print(f"Using: {VIDEO_URL}")
    import subprocess
    video_path = "/tmp/video.mp4"
    subprocess.run(["wget", "-q", VIDEO_URL, "-O", video_path], check=True)

print(f"Processing: {video_path}")

# =====================================================
# CELL 6: Transcribe Video
# =====================================================

print("\n🎙️ Transcribing video (GPU)...")
segments = []

for segment in whisper.transcribe(video_path, language="en"):
    segments.append({
        "start_sec": float(segment.start),
        "end_sec": float(segment.end),
        "transcript": segment.text
    })
    if len(segments) <= 3:
        print(f"  [{segment.start:.1f}s] {segment.text[:50]}...")

print(f"✓ Transcribed {len(segments)} segments")

# =====================================================
# CELL 7: Speaker Diarization
# =====================================================

print("\n👥 Detecting speakers (GPU)...")
speakers_data = diarization(video_path)

speaker_map = {}
for turn, _, speaker in speakers_data.itertracks(yield_label=True):
    if speaker not in speaker_map:
        speaker_map[speaker] = []
    speaker_map[speaker].append({
        "start": float(turn.start),
        "end": float(turn.end)
    })

print(f"✓ Found {len(speaker_map)} speakers")
for speaker_id, times in speaker_map.items():
    total_time = sum(t["end"] - t["start"] for t in times)
    print(f"  {speaker_id}: {total_time:.0f}s speaking time")

# =====================================================
# CELL 8: Emotion Detection
# =====================================================

print("\n😊 Detecting emotions...")

emotion_keywords = {
    'surprise': ['surprised', 'wow', 'really', 'no way', 'what', 'shocked'],
    'laughter': ['haha', 'lol', 'laugh', 'funny', 'hilarious'],
    'concern': ['worried', 'concern', 'problem', 'expensive'],
    'agreement': ['yes', 'exactly', 'right', 'agree']
}

for segment in segments:
    text = segment["transcript"].lower()
    detected = []
    for emotion, keywords in emotion_keywords.items():
        if any(kw in text for kw in keywords):
            detected.append(emotion)
    segment["emotions"] = detected
    if detected:
        print(f"  [{segment['start_sec']:.0f}s] {detected} → {text[:40]}...")

# =====================================================
# CELL 9: Save to Supabase
# =====================================================

print("\n💾 Saving to Supabase...")
from supabase import create_client

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"]
)

# Create video record
video_record = supabase.table("videos").insert({
    "filename": os.path.basename(video_path),
    "duration_seconds": int(max(s["end_sec"] for s in segments)),
    "status": "processing",
    "user_id": "colab-user"  # Change to real user ID
}).execute()

video_id = video_record.data[0]["id"]
print(f"✓ Video {video_id} created")

# Save segments
segment_records = [
    {
        "video_id": video_id,
        "segment_id": f"seg_{i:04d}",
        "start_sec": s["start_sec"],
        "end_sec": s["end_sec"],
        "transcript": s["transcript"],
        "emotions": s.get("emotions", [])
    }
    for i, s in enumerate(segments)
]

for batch in [segment_records[i:i+100] for i in range(0, len(segment_records), 100)]:
    supabase.table("segments").insert(batch).execute()

print(f"✓ Saved {len(segment_records)} segments")

# Save speakers
speaker_records = [
    {
        "video_id": video_id,
        "speaker_id": speaker_id,
        "name": speaker_id,
        "total_duration": int(sum(t["end"] - t["start"] for t in times))
    }
    for speaker_id, times in speaker_map.items()
]

supabase.table("speakers").insert(speaker_records).execute()
print(f"✓ Saved {len(speaker_records)} speakers")

# Update video status
supabase.table("videos").update({
    "status": "ready"
}).eq("id", video_id).execute()

print(f"\n✅ Video {video_id} ready for queries!")
print(f"Video ID: {video_id}")
print(f"Segments: {len(segment_records)}")
print(f"Speakers: {len(speaker_records)}")

# =====================================================
# CELL 10: Test Query
# =====================================================

# Now you can query your video!
print("\n🔍 Testing query...")

query = "Who showed surprise?"

# Retrieve relevant segments
query_embedding = embed_model.encode([query])[0]

# Simple search (in production, use ChromaDB + BM25)
import numpy as np
similarities = []
for seg in segment_records:
    seg_embedding = embed_model.encode([seg["transcript"]])[0]
    score = np.dot(query_embedding, seg_embedding)
    similarities.append((seg, score))

top_segments = sorted(similarities, key=lambda x: x[1], reverse=True)[:3]

print(f"Top results for '{query}':")
for seg, score in top_segments:
    print(f"  Segment {seg['segment_id']}: {seg['transcript'][:60]}...")
    print(f"    Score: {score:.3f}, Emotions: {seg['emotions']}")

print("\n🎉 Processing complete! Your data is in Supabase.")
print(f"Video ID: {video_id}")
print("Use this ID to query via the web interface!")
