"""
Videntia Configuration
Central configuration for paths, API keys, and retrieval parameters.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# Paths
# ============================================================================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
VIDEOS_DIR = DATA_DIR / "videos"
FRAMES_DIR = DATA_DIR / "frames"
SEGMENTS_DIR = DATA_DIR / "segments"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
RECORDS_DIR = DATA_DIR / "records"
MODELS_DIR = DATA_DIR / "models"
DB_DIR = BASE_DIR / "db"
REPORTS_DIR = BASE_DIR / "reports"

# Ensure directories exist
for d in [VIDEOS_DIR, FRAMES_DIR, SEGMENTS_DIR, TRANSCRIPTS_DIR,
          RECORDS_DIR, MODELS_DIR, DB_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================================================
# LLM (Groq)
# ============================================================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.1-8b-instant"  # 500K tokens/day free (vs 100K for 70b)

# ============================================================================
# HuggingFace
# ============================================================================
HF_TOKEN = os.environ.get("HF_TOKEN", "")

# ============================================================================
# Supabase (optional cloud storage)
# ============================================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# ============================================================================
# Embedding Models
# ============================================================================
EMBED_MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"
EMBED_DIMENSION = 768
RERANKER_MODEL_NAME = "BAAI/bge-reranker-v2-m3"

# ============================================================================
# ChromaDB Collections
# ============================================================================
TEXT_COLLECTION = "text_segments"
VISION_COLLECTION = "vision_segments"
CHROMA_DIR = str(DB_DIR / "chroma")

# ============================================================================
# Retrieval Parameters
# ============================================================================
BM25_TOP_K = 50
DENSE_TOP_K = 50
RRF_TOP_K = 20
RERANK_TOP_K = 8
RRF_K = 60  # RRF fusion constant

# ============================================================================
# Agent Loop Control
# ============================================================================
MAX_ITERATIONS = 5
MIN_CONFIDENCE = 0.75

# ============================================================================
# Video Processing
# ============================================================================
SEGMENT_DURATION = 10  # seconds per chunk
WHISPER_MODEL = "base"
CAPTION_MODEL = "Salesforce/blip2-opt-2.7b"
