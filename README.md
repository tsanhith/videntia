# Videntia: Multimodal Forensic Video Intelligence

**"When one sense isn't enough — fuse them all."**

Videntia is a local-first, multimodal forensic analysis system that turns long-form video into searchable, evidence-linked findings.

## What Videntia Does

- Splits video into overlapping forensic segments.
- Extracts and aligns transcript, speaker, visual, OCR, and metadata signals.
- Indexes each modality for hybrid retrieval.
- Runs a multi-agent reasoning loop to verify claims and produce structured reports.

## Zero-Cost Build Commitment

This project is designed to be built with **free/open-source software and free-tier infrastructure**:

- **LLMs:** Ollama local models (`mistral`, `qwen2.5`, `phi3`) or free-tier hosted inference (e.g., Groq).
- **Speech-to-text:** `faster-whisper` (local).
- **Diarization:** `pyannote.audio` (free model weights with HF acceptance).
- **Vision understanding:** BLIP-2, CLIP, LLaVA (open models).
- **Vector DB:** ChromaDB local persistent mode.
- **Orchestration:** LangGraph.
- **Video tooling:** FFmpeg + MoviePy.

See [`docs/FREE_BUILD_PLAN.md`](docs/FREE_BUILD_PLAN.md) for a full student-focused implementation plan with free compute options.

## Architecture (High-Level)

1. **Ingestion Pipeline**
   - Video segmentation (10s windows, 2s overlap)
   - Audio transcription + diarization
   - Keyframe extraction + captioning + OCR
2. **Multimodal Indexing**
   - Separate vector collections for text / vision / audio
   - Metadata-rich segment records for forensic traceability
3. **Multi-Agent Reasoning Loop**
   - Lead Detective (orchestration)
   - Retriever (hybrid RAG)
   - Verifier (cross-check + contradiction detection)
   - Memory Manager (session + long-term context)
   - Report Scribe (JSON + Markdown report output)

## Retrieval Strategy

- Stage 1: BM25 sparse recall
- Stage 2: Dense multimodal ANN retrieval
- Stage 3: Cross-encoder reranking
- Stage 4: Agentic verification and contradiction scoring

## Current Status

Repository currently contains architecture and planning documentation. Implementation modules can be scaffolded incrementally from the free build plan.
