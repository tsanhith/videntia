"""
FASTAPI SERVER FOR HUGGINGFACE SPACES
Copy to HuggingFace Space as app.py

This handles:
1. Webhook from Google Colab (processing results)
2. API queries to Supabase
3. Streaming responses
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import httpx
from supabase import create_client
from datetime import datetime
import json

app = FastAPI(title="Videntia API")

# Enable CORS (allow frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase
supabase = create_client(
    os.environ.get("SUPABASE_URL", "https://your-project.supabase.co"),
    os.environ.get("SUPABASE_KEY", "your-anon-key")
)

# =====================================================
# MODELS
# =====================================================

class SegmentData(BaseModel):
    segment_id: str
    transcript: str
    emotions: List[str]
    start_sec: float
    end_sec: float

class WebhookPayload(BaseModel):
    video_id: str
    segments: List[SegmentData]
    speakers: dict

class QueryRequest(BaseModel):
    video_id: str
    question: str

class QueryResult(BaseModel):
    question: str
    answer: str
    evidence: List[dict]
    confidence: float

# =====================================================
# ROUTES
# =====================================================

@app.get("/health")
async def health():
    """Check if API is running"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.post("/webhook")
async def receive_processing_results(payload: WebhookPayload):
    """
    Receive processed video from Google Colab
    Called when video processing completes
    """
    try:
        video_id = payload.video_id
        
        # Save segments (already done by Colab, but we can update metadata)
        for segment in payload.segments:
            supabase.table("segments").update({
                "emotions": segment.emotions,
                "updated_at": datetime.now().isoformat()
            }).eq("segment_id", segment.segment_id).execute()
        
        # Update video status
        supabase.table("videos").update({
            "status": "indexed",
            "segment_count": len(payload.segments),
            "processed_at": datetime.now().isoformat()
        }).eq("id", video_id).execute()
        
        return {
            "status": "received",
            "video_id": video_id,
            "segments_updated": len(payload.segments)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query")
async def query_video(request: QueryRequest) -> QueryResult:
    """
    Query a processed video
    
    Example:
    {
        "video_id": "550e8400-e29b-41d4-a716-446655440000",
        "question": "Who showed surprise when hearing about 200 pounds?"
    }
    """
    try:
        video_id = request.video_id
        question = request.question
        
        # Verify video exists
        video = supabase.table("videos").select("*").eq("id", video_id).execute()
        if not video.data:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Get all segments for this video
        segments_result = supabase.table("segments").select("*").eq("video_id", video_id).execute()
        segments = segments_result.data
        
        if not segments:
            raise HTTPException(status_code=404, detail="No segments found")
        
        # Simple relevance matching
        question_lower = question.lower()
        relevant_segments = []
        
        for seg in segments:
            transcript_lower = seg["transcript"].lower()
            
            # Score based on keyword overlap
            score = 0.0
            question_words = question_lower.split()
            
            for word in question_words:
                if len(word) > 3 and word in transcript_lower:
                    score += 1.0
            
            # Emotion matching
            if "surprise" in question_lower and "surprise" in seg.get("emotions", []):
                score += 2.0
            if "laugh" in question_lower and "laughter" in seg.get("emotions", []):
                score += 2.0
            
            if score > 0:
                relevant_segments.append({
                    "segment_id": seg["segment_id"],
                    "transcript": seg["transcript"],
                    "emotions": seg.get("emotions", []),
                    "start_sec": seg["start_sec"],
                    "end_sec": seg["end_sec"],
                    "score": score
                })
        
        # Sort by relevance
        relevant_segments.sort(key=lambda x: x["score"], reverse=True)
        top_segments = relevant_segments[:5]
        
        # Build answer
        if not top_segments:
            answer = f"I couldn't find relevant information about '{question}' in this video."
            confidence = 0.0
        else:
            # Combine findings
            findings = []
            for seg in top_segments:
                findings.append(f"At {seg['start_sec']:.0f}s: {seg['transcript']}")
                if seg["emotions"]:
                    findings.append(f"  Emotions: {', '.join(seg['emotions'])}")
            
            answer = "Based on the video content:\n" + "\n".join(findings[:3])
            confidence = min(0.95, 0.5 + (len(top_segments) * 0.1))
        
        # Save query result
        supabase.table("query_results").insert({
            "video_id": video_id,
            "question": question,
            "answer": answer,
            "confidence": confidence,
            "segment_count": len(top_segments),
            "queried_at": datetime.now().isoformat()
        }).execute()
        
        return QueryResult(
            question=question,
            answer=answer,
            evidence=[
                {
                    "segment_id": seg["segment_id"],
                    "transcript": seg["transcript"],
                    "start_sec": seg["start_sec"],
                    "emotions": seg["emotions"]
                }
                for seg in top_segments
            ],
            confidence=confidence
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/videos")
async def list_videos():
    """List all processed videos"""
    try:
        videos = supabase.table("videos").select("*").execute()
        return {"videos": videos.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/videos/{video_id}")
async def get_video(video_id: str):
    """Get video details and summary"""
    try:
        video = supabase.table("videos").select("*").eq("id", video_id).execute()
        if not video.data:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Get segment count
        segments = supabase.table("segments").select("id").eq("video_id", video_id).execute()
        
        # Get speakers
        speakers = supabase.table("speakers").select("*").eq("video_id", video_id).execute()
        
        video_data = video.data[0]
        video_data["segment_count"] = len(segments.data)
        video_data["speaker_count"] = len(speakers.data)
        video_data["speakers"] = speakers.data
        
        return video_data
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/videos/{video_id}/segments")
async def get_segments(video_id: str, limit: int = 100):
    """Get all segments for a video"""
    try:
        segments = supabase.table("segments").select("*").eq("video_id", video_id).limit(limit).execute()
        return {"segments": segments.data, "count": len(segments.data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# STARTUP
# =====================================================

@app.on_event("startup")
async def startup():
    print("✅ Videntia API started!")
    print("Environment:")
    print(f"  SUPABASE_URL: {os.environ.get('SUPABASE_URL', 'NOT SET')[:20]}...")
    print(f"  Mode: HuggingFace Spaces")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
