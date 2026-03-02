"""
Videntia REST API - FastAPI wrapper for orchestration backend
Exposes endpoints for video ingestion, querying, and results retrieval
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form
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
    processing_mode: str = Form("balanced"),
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
        
        mode = (processing_mode or "balanced").lower()
        if mode not in ["fast", "balanced", "full"]:
            mode = "balanced"

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
        
        enable_diarization = mode in ["balanced", "full"]
        enable_captioning = mode == "full"

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
    """List all uploaded videos"""
    return {
        "videos": [v.dict() for v in state.videos.values()]
    }

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

        async def advance_query_progress():
            while query_id in state.queries and state.queries[query_id].status == "processing":
                await asyncio.sleep(2)
                current = state.queries[query_id].progress
                if current < 90.0:
                    state.queries[query_id].progress = min(90.0, current + 4.0)
                    if state.queries[query_id].progress < 40:
                        state.queries[query_id].stage = "Retrieving evidence"
                    elif state.queries[query_id].progress < 75:
                        state.queries[query_id].stage = "Running multi-agent analysis"
                    else:
                        state.queries[query_id].stage = "Synthesizing report"

        progress_task = asyncio.create_task(advance_query_progress())
        
        # Run analysis directly
        final_state = await asyncio.to_thread(analyze_video, query, max_iter)
        state.queries[query_id].progress = 95.0
        state.queries[query_id].stage = "Finalizing response"
        
        if final_state:
            state.queries[query_id].status = "complete"
            state.queries[query_id].progress = 100.0
            state.queries[query_id].stage = "Complete"
            state.queries[query_id].result = {
                "query": query,
                "final_report": final_state.get('report', 'No report generated'),
                "evidence_segments": final_state.get('evidence', []),
                "contradictions": final_state.get('contradictions', []),
                "metadata": {
                    "iterations": final_state.get('iteration', 0),
                    "evidence_count": len(final_state.get('evidence', [])),
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
