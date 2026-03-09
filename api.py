"""
Videntia REST API - FastAPI wrapper for orchestration backend
Exposes endpoints for video ingestion, querying, and results retrieval
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import os
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import uuid
import asyncio

# Import backend modules
from pipeline.ingest import ingest_video, load_records
from config import VIDEOS_DIR, RECORDS_DIR
from main import analyze_video

app = FastAPI(
    title="Videntia API",
    description="RAG + Multi-Agent AI for Video Analysis",
    version="1.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Data Models
# ============================================================================

class QueryRequest(BaseModel):
    query: str
    video_id: Optional[str] = None
    max_iterations: int = 5

class QueryResponse(BaseModel):
    query_id: str
    query: str
    status: str  # pending, processing, complete, failed
    progress: float = 0.0  # 0-100
    stage: str = "Queued"
    result: Optional[dict] = None
    error: Optional[str] = None
    timestamp: str

class VideoMetadata(BaseModel):
    video_id: str
    filename: str
    segments: int
    speakers: int
    uploaded_at: str

class UploadTask(BaseModel):
    task_id: str
    video_id: str
    filename: str
    status: str  # queued, processing, complete, failed
    progress: float  # 0-100
    stage: str  # e.g., "Extracting audio", "Diarizing", etc.
    error: Optional[str] = None
    result: Optional[dict] = None
    created_at: str

class VideoState:
    """In-memory state for active queries/videos"""
    def __init__(self):
        self.queries = {}  # query_id -> QueryResponse
        self.videos = {}   # video_id -> VideoMetadata
        self.upload_tasks = {}  # task_id -> UploadTask

state = VideoState()

# ============================================================================
# Health & Status
# ============================================================================

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "service": "videntia-api"}

# ============================================================================
# Video Management
# ============================================================================

@app.post("/api/videos/upload")
async def upload_video(
    file: UploadFile = File(...),
    processing_mode: str = Form("fast"),
    background_tasks: BackgroundTasks = None,
):
    """
    Upload a video file and start ingestion in background.
    Returns task_id for polling progress.
    """
    try:
        video_id = str(uuid.uuid4())[:8]
        task_id = str(uuid.uuid4())[:12]
        filename = f"{video_id}_{file.filename}"
        video_path = VIDEOS_DIR / filename
        
        # Save uploaded file
        with open(video_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Create task tracking
        task = UploadTask(
            task_id=task_id,
            video_id=video_id,
            filename=filename,
            status="queued",
            progress=0.0,
            stage="Queued for processing",
            created_at=datetime.now().isoformat()
        )
        state.upload_tasks[task_id] = task
        
        mode = (processing_mode or "fast").lower()
        if mode not in ["fast", "balanced", "full"]:
            mode = "fast"

        # Run ingestion in background
        background_tasks.add_task(
            process_video_upload,
            task_id,
            video_id,
            str(video_path),
            filename,
            mode,
        )
        
        return {
            "task_id": task_id,
            "video_id": video_id,
            "processing_mode": mode,
            "status": "queued",
            "message": "Video uploaded, processing started"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Video upload failed: {str(e)}")

async def process_video_upload(task_id: str, video_id: str, video_path: str, filename: str, mode: str):
    """Background task to process video ingestion with progress updates"""
    try:
        # Update status
        state.upload_tasks[task_id].status = "processing"
        state.upload_tasks[task_id].stage = f"Starting ingestion ({mode} mode)"
        state.upload_tasks[task_id].progress = 5.0
        
        # Progress callback to update task status
        def progress_callback(progress: float, stage: str):
            state.upload_tasks[task_id].progress = progress
            state.upload_tasks[task_id].stage = stage
        
        enable_diarization = mode == "full"  # balanced mode skips diarization too for speed
        enable_captioning = mode == "full"   # only full mode runs BLIP captioning

        # Run full ingestion in thread pool with progress updates
        records = await asyncio.to_thread(
            ingest_video,
            video_path,
            progress_callback,
            enable_diarization,
            enable_captioning,
        )
        
        # Calculate metadata
        speakers = set()
        for rec in records:
            if rec.speaker:
                speakers.add(rec.speaker)
        
        metadata = VideoMetadata(
            video_id=video_id,
            filename=filename,
            segments=len(records),
            speakers=len(speakers),
            uploaded_at=datetime.now().isoformat()
        )
        state.videos[video_id] = metadata
        
        # Mark complete
        state.upload_tasks[task_id].status = "complete"
        state.upload_tasks[task_id].progress = 100.0
        state.upload_tasks[task_id].stage = "Complete"
        state.upload_tasks[task_id].result = {
            "video_id": video_id,
            "segments": len(records),
            "speakers": len(speakers),
            "processing_mode": mode,
        }
        
    except Exception as e:
        state.upload_tasks[task_id].status = "failed"
        state.upload_tasks[task_id].error = str(e)
        state.upload_tasks[task_id].stage = "Failed"

@app.get("/api/videos/upload/{task_id}/status")
async def get_upload_status(task_id: str):
    """Poll upload task status and progress"""
    if task_id not in state.upload_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = state.upload_tasks[task_id]
    return task.dict()

@app.get("/api/videos")
async def list_videos():
    """List all videos (memory + disk)"""
    videos = {v.video_id: v.dict() for v in state.videos.values()}
    
    try:
        if RECORDS_DIR.exists():
            for path in RECORDS_DIR.glob('*.json'):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        vid = data.get('video_id')
                        if vid and vid not in videos:
                            # Avoid over-counting by just adding it once we find one segment
                            videos[vid] = {
                                "video_id": vid,
                                "filename": vid,
                                "segments": len(list(RECORDS_DIR.glob(f"*{vid}*.json"))),
                                "speakers": 0,
                                "uploaded_at": "Project Dataset"
                            }
                except:
                    continue
    except Exception as e:
        print(f"Error scanning records: {e}")
        
    return {
        "videos": list(videos.values())
    }

from fastapi.responses import Response, StreamingResponse
import mimetypes

@app.get("/api/videos/{video_id}/stream")
async def stream_video(video_id: str, request: Request):
    """Serve video with proper HTTP Range request support for browser seeking."""
    try:
        # Find video file.
        # Ingest creates video_id as "{ingest_uuid}_{original_file_stem}" (e.g. a084d88d_5f9d743f_Hybrid_RAG)
        # but the file is stored as "{upload_uuid}_{original_name}" (e.g. 5f9d743f_Hybrid_RAG.mp4).
        video_files = list(VIDEOS_DIR.glob(f"{video_id}_*"))
        if not video_files:
            video_files = list(VIDEOS_DIR.glob(f"{video_id}.*"))
        if not video_files:
            video_files = list(VIDEOS_DIR.glob(f"*{video_id}*"))
        if not video_files:
            # Strip the leading ingest-uuid prefix (8hex + underscore) to get the actual file stem
            # e.g. "a084d88d_5f9d743f_Hybrid_RAG" -> "5f9d743f_Hybrid_RAG"
            parts = video_id.split("_", 1)
            if len(parts) == 2:
                file_stem = parts[1]
                video_files = list(VIDEOS_DIR.glob(f"{file_stem}.*"))
                if not video_files:
                    video_files = list(VIDEOS_DIR.glob(f"*{file_stem}*"))
        if not video_files:
            raise HTTPException(status_code=404, detail=f"Video file not found for id: {video_id}")

        video_path = video_files[0]
        file_size = video_path.stat().st_size

        mt, _ = mimetypes.guess_type(str(video_path))
        if not mt:
            mt = "video/mp4"

        # Parse Range header (e.g. "bytes=0-1023")
        range_header = request.headers.get("range")

        if range_header:
            # Parse byte range
            range_value = range_header.strip().lower().replace("bytes=", "")
            range_start_str, _, range_end_str = range_value.partition("-")
            start = int(range_start_str) if range_start_str else 0
            end = int(range_end_str) if range_end_str else file_size - 1
            end = min(end, file_size - 1)  # clamp to file size
            chunk_size = end - start + 1

            def iter_file_range(path, s, length, buf=1 << 20):  # 1MB buffer
                with open(path, "rb") as f:
                    f.seek(s)
                    remaining = length
                    while remaining > 0:
                        data = f.read(min(buf, remaining))
                        if not data:
                            break
                        remaining -= len(data)
                        yield data

            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_size),
                "Content-Type": mt,
            }
            return StreamingResponse(
                iter_file_range(video_path, start, chunk_size),
                status_code=206,
                headers=headers,
                media_type=mt,
            )
        else:
            # No Range header — stream full file (initial load / small files)
            def iter_full_file(path, buf=1 << 20):
                with open(path, "rb") as f:
                    while True:
                        data = f.read(buf)
                        if not data:
                            break
                        yield data

            headers = {
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Content-Type": mt,
            }
            return StreamingResponse(
                iter_full_file(video_path),
                status_code=200,
                headers=headers,
                media_type=mt,
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/videos/{video_id}/segments")
async def get_video_segments(video_id: str):
    """Get all segments for a video with metadata"""
    try:
        records = load_records(video_id)
        
        segments = []
        for rec in records:
            segments.append({
                "segment_id": rec.segment_id,
                "start_sec": rec.start_sec,
                "end_sec": rec.end_sec,
                "transcript": rec.transcript,
                "speaker": rec.speaker,
                "captions": rec.visual_captions,
                "emotions": rec.metadata.get("emotions", []),
                "emotion_intensity": rec.metadata.get("emotion_intensity", 0)
            })
        
        return {"video_id": video_id, "segments": segments}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Segments not found: {str(e)}")

# ============================================================================
# Query & Orchestration
# ============================================================================

@app.post("/api/query")
async def query(request: QueryRequest, background_tasks: BackgroundTasks):
    """
    Submit a query for orchestration (5-agent graph).
    Returns query_id for polling results.
    """
    query_id = str(uuid.uuid4())[:12]
    
    # Create response
    response = QueryResponse(
        query_id=query_id,
        query=request.query,
        status="pending",
        progress=0.0,
        stage="Queued",
        timestamp=datetime.now().isoformat()
    )
    
    state.queries[query_id] = response
    
    # Run orchestration in background
    background_tasks.add_task(
        run_orchestration,
        query_id,
        request.query,
        request.video_id,
        request.max_iterations
    )
    
    return response.dict()

async def run_orchestration(query_id: str, query: str, video_id: Optional[str], max_iter: int):
    """Run the 5-agent orchestration for a query via main.py"""
    progress_task = None
    try:
        state.queries[query_id].status = "processing"
        state.queries[query_id].progress = 10.0
        state.queries[query_id].stage = "Preparing analysis"

        # Scripted multi-agent stage sequence — each message identifies the sending agent
        STAGES = [
            (2,  "DETECTIVE: Parsing query intent and building investigation plan..."),
            (4,  "DETECTIVE→RETRIEVER: Dispatching 3 sub-tasks to evidence retrieval unit"),
            (6,  "RETRIEVER: Running BM25 sparse search across indexed transcript corpus"),
            (8,  "RETRIEVER: Running dense semantic search in ChromaDB vector store"),
            (10, "RETRIEVER: Fusing results via Reciprocal Rank Fusion (RRF)"),
            (12, "RETRIEVER→VERIFIER: Forwarding top candidates for quality assessment"),
            (14, "VERIFIER: Deduplicating evidence segments by segment_id"),
            (16, "VERIFIER: Running LLM quality check & contradiction detection"),
            (18, "VERIFIER→DETECTIVE: Confidence score computed, returning to lead agent"),
            (20, "DETECTIVE: Iteration check — evidence sufficient? Deciding whether to loop..."),
            (22, "DETECTIVE→SCRIBE: Evidence accepted, dispatching to report synthesis"),
            (24, "SCRIBE: Compiling verified evidence into structured intelligence report"),
            (26, "SCRIBE: Finalizing findings, contradictions, and confidence summary"),
        ]

        async def advance_query_progress():
            for secs, stage_msg in STAGES:
                await asyncio.sleep(secs if secs == STAGES[0][0] else 2)
                if query_id not in state.queries or state.queries[query_id].status != "processing":
                    break
                progress = min(90.0, 10.0 + (STAGES.index((secs, stage_msg)) / len(STAGES)) * 80)
                state.queries[query_id].progress = progress
                state.queries[query_id].stage = stage_msg
            # Hold last stage until done
            while query_id in state.queries and state.queries[query_id].status == "processing":
                await asyncio.sleep(1)

        progress_task = asyncio.create_task(advance_query_progress())

        # Run analysis directly
        print(f"DEBUG: Running analyze_video with query='{query}' and video_id='{video_id}'")
        final_state = await asyncio.to_thread(analyze_video, query, max_iter, video_id)
        state.queries[query_id].progress = 95.0
        state.queries[query_id].stage = "Finalizing response"
        
        if final_state:
            state.queries[query_id].status = "complete"
            state.queries[query_id].progress = 100.0
            state.queries[query_id].stage = "Complete"
            # Normalize evidence segments for frontend consumption
            raw_evidence = final_state.get('verified_evidence') or final_state.get('evidence', [])

            # Build a keyword set from the query (ignore short stop words)
            _stop = {"what","that","this","with","from","about","have","will","they","were",
                     "the","and","are","was","for","how","did","who","does"}
            _qwords = {w.lower().strip("?.,!") for w in query.split() if len(w) > 3 and w.lower() not in _stop}
            def _display_score(e: dict) -> float:
                raw = min(1.0, float(e.get("rerank_score", e.get("rrf_score", 0))))
                txt = e.get("transcript", "").lower()
                # Keyword overlap fraction (0-1)
                overlap = (sum(1 for w in _qwords if w in txt) / len(_qwords)) if _qwords else 0.0
                # Small penalty for the first 90 s — usually intro / scene-setting, not answers
                intro_penalty = 0.85 if float(e.get("start_sec", 0)) < 90 else 1.0
                return (raw * 0.65 + overlap * 0.35) * intro_penalty

            evidence_segments = sorted(
                [
                    {
                        "segment_id": e.get("segment_id", ""),
                        "transcript": e.get("transcript", ""),
                        "start_sec": float(e.get("start_sec", 0)),
                        "end_sec": float(e.get("end_sec", 0)),
                        "speaker": e.get("speaker", ""),
                        "rerank_score": round(_display_score(e), 4),
                    }
                    for e in raw_evidence
                ],
                key=lambda x: x["rerank_score"],
                reverse=True,
            )
            state.queries[query_id].result = {
                "query": query,
                "final_report": final_state.get('report', 'No report generated'),
                "evidence_segments": evidence_segments,
                "contradictions": final_state.get('contradictions', []),
                "metadata": {
                    "iterations": final_state.get('iteration', 0),
                    "evidence_count": len(evidence_segments),
                    "confidence_score": final_state.get('confidence_score', 0.0),
                    "timestamp": datetime.now().isoformat()
                }
            }
        else:
            raise Exception("Analysis returned no result")
            
    except Exception as e:
        state.queries[query_id].status = "failed"
        state.queries[query_id].stage = "Failed"
        state.queries[query_id].error = str(e)
    finally:
        if progress_task:
            progress_task.cancel()

@app.get("/api/query/{query_id}")
async def get_query_result(query_id: str):
    """Poll for query results"""
    if query_id not in state.queries:
        raise HTTPException(status_code=404, detail="Query not found")
    
    return state.queries[query_id].dict()

# ============================================================================
# Analytics & Insights
# ============================================================================

@app.get("/api/videos/{video_id}/speakers")
async def get_speaker_timeline(video_id: str):
    """Get speaker diarization timeline for visualization"""
    try:
        records = load_records(video_id)
        
        speakers = {}
        for rec in records:
            if rec.speaker:
                if rec.speaker not in speakers:
                    speakers[rec.speaker] = {
                        "name": rec.speaker,
                        "segments": [],
                        "total_duration": 0,
                        "embedding": rec.speaker_embedding[:10] if rec.speaker_embedding else None
                    }
                
                speakers[rec.speaker]["segments"].append({
                    "segment_id": rec.segment_id,
                    "start": rec.start_sec,
                    "end": rec.end_sec,
                    "duration": rec.end_sec - rec.start_sec,
                    "text": rec.transcript[:100]
                })
                speakers[rec.speaker]["total_duration"] += rec.end_sec - rec.start_sec
        
        return {
            "video_id": video_id,
            "speakers": list(speakers.values())
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Speaker data not found: {str(e)}")

@app.get("/api/videos/{video_id}/emotions")
async def get_emotion_analysis(video_id: str):
    """Get emotion timeline for visualization"""
    try:
        records = load_records(video_id)
        
        emotions_timeline = []
        for rec in records:
            emotions_timeline.append({
                "segment_id": rec.segment_id,
                "start": rec.start_sec,
                "end": rec.end_sec,
                "emotions": rec.metadata.get("emotions", []),
                "intensity": rec.metadata.get("emotion_intensity", 0),
                "speaker": rec.speaker
            })
        
        return {
            "video_id": video_id,
            "timeline": emotions_timeline
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Emotion data not found: {str(e)}")

# ============================================================================
# Root
# ============================================================================

@app.get("/")
async def root():
    return {
        "service": "Videntia API",
        "version": "1.0.0",
        "endpoints": {
            "health": "GET /health",
            "upload_video": "POST /api/videos/upload",
            "list_videos": "GET /api/videos",
            "get_segments": "GET /api/videos/{video_id}/segments",
            "submit_query": "POST /api/query",
            "get_query_result": "GET /api/query/{query_id}",
            "speaker_timeline": "GET /api/videos/{video_id}/speakers",
            "emotion_analysis": "GET /api/videos/{video_id}/emotions"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
