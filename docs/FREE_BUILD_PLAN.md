# Videntia Free Build Plan (Student Edition)

This document translates the architecture into a **$0-cost implementation path**.

## 1) Free Accounts to Create First

1. Google account (Colab + Drive storage)
2. Kaggle account (free weekly GPU hours)
3. Hugging Face account (model downloads/tokens)
4. GitHub account (code hosting)
5. Optional: Groq account (free-tier hosted inference)

## 2) Free Compute Strategy

- **Primary ingestion:** Kaggle notebooks (stable free GPU allotment)
- **Interactive experiments:** Google Colab free tier
- **Local dev / debugging:** CPU-only laptop + smaller models
- **Persistence:** Save artifacts/DB under Google Drive or repository-managed local volumes

## 3) 100% Free Toolchain

- **Segmentation:** FFmpeg, MoviePy
- **ASR:** faster-whisper
- **Diarization:** pyannote.audio
- **Captions:** BLIP-2 / LLaVA / Moondream (choose by hardware)
- **OCR:** Tesseract
- **Embeddings:** nomic-embed-text or BGE + CLIP + CLAP
- **Vector store:** ChromaDB (persistent local path)
- **Agents:** LangGraph + local Ollama or free-tier hosted LLM endpoint
- **Reports:** Markdown + JSON output

## 4) Recommended Free Model Matrix

### CPU-Limited
- Whisper model: `small` or `base`
- Agent LLM: `phi3:mini`
- Vision model: `moondream2`

### Single 8–16GB GPU
- Whisper model: `large-v3`
- Agent LLM: `mistral:7b-instruct` or `qwen2.5:7b`
- Vision model: `llava:7b`

## 5) Incremental Build Milestones

### Milestone A — Ingestion
- Segment input video into 10s windows with 2s overlap
- Generate transcript + diarization
- Extract keyframes + OCR + captions
- Emit per-segment JSON records

### Milestone B — Embeddings + Index
- Encode transcript / vision / audio separately
- Create dedicated Chroma collections per modality
- Store full metadata payload with every record

### Milestone C — Hybrid Retrieval
- Implement BM25 candidate retrieval
- Add dense retrieval across all modalities
- Fuse rankings (RRF)
- Add reranking for top candidates

### Milestone D — Multi-Agent Reasoning
- Implement typed shared state
- Add Lead Detective, Retriever, Verifier, Memory Manager, Report Scribe
- Enforce loop stop conditions and confidence thresholds

### Milestone E — Evaluation
- Annotate query relevance set (Precision@K, Recall@K, MRR, nDCG)
- Build contradiction benchmark (Precision/Recall/F1)
- Measure citation faithfulness and hallucination rate

## 6) Practical Cost-Control Rules

- Prefer local inference whenever possible.
- Batch ingestion jobs to maximize free GPU sessions.
- Cache model directories to persistent storage.
- Keep embeddings/versioned artifacts so you avoid re-processing videos.
- Degrade gracefully to smaller models for iteration; reserve large models for final evaluation.

## 7) Minimum Viable Demo Goal

A valid thesis demo at zero cost should support:

1. Upload one public-domain test video
2. Ask a forensic query
3. Return top evidence segments with timestamp + modality sources
4. Output a short structured report with confidence and contradiction notes

That single end-to-end path is enough to prove architecture viability before scaling.
