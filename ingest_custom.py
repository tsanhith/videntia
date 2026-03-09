import json
import uuid
import re
from pathlib import Path

from pydantic import BaseModel, Field

from config import RECORDS_DIR, VIDEOS_DIR
from pipeline.segment import segment_video
from pipeline.fuse import extract_emotion_signals
from pipeline.ingest import SegmentRecord, load_records


def parse_time_srt(time_str):
    # Parse HH:MM:SS,mmm into seconds
    parts = time_str.replace(',', ':').split(':')
    if len(parts) >= 4:
        h, m, s, ms = parts[:4]
        return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000.0
    return 0.0

def parse_srt(srt_path):
    content = Path(srt_path).read_text(encoding='utf-8')
    blocks = content.strip().split('\n\n')
    parsed = []
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            time_line = lines[1]
            if ' --> ' in time_line:
                start_str, end_str = time_line.split(' --> ')
                start_sec = parse_time_srt(start_str)
                end_sec = parse_time_srt(end_str)
                text = " ".join(lines[2:]).strip()
                parsed.append({"start": start_sec, "end": end_sec, "text": text})
    return parsed

def ingest_custom(video_path, srt_path):
    print("Starting custom ingestion...")
    video_path = Path(video_path)
    video_id = f"{uuid.uuid4().hex[:8]}_{video_path.stem}"
    
    # Step 1: Segment video
    print("Segmenting video...")
    segments = segment_video(str(video_path))
    if not segments:
        raise ValueError("No segments produced")
        
    # Step 2: Parse SRT
    print("Parsing SRT...")
    srt_blocks = parse_srt(srt_path)
    
    # Step 3: Map SRT text to segments and create records
    records = []
    print("Mapping text, detecting emotions, building records...")
    
    for seg in segments:
        seg_start = seg["start_sec"]
        seg_end = seg["end_sec"]
        
        # Find overlapping blocks
        overlapping_texts = []
        for block in srt_blocks:
            if block["start"] < seg_end and block["end"] > seg_start:
                overlapping_texts.append(block["text"])
                
        transcript = " ".join(overlapping_texts).strip()
        seg_id = f"{video_id}_seg{seg['index']:04d}"
        
        # Emotions
        emotion_data = extract_emotion_signals(transcript, [])
        emotion_parts = []
        for emo in emotion_data.get("detected_emotions", []):
            conf = emotion_data.get("emotion_scores", {}).get(emo, 0)
            emotion_parts.append(f"{emo}({conf:.2f})")
        emotion_str = ", ".join(emotion_parts) if emotion_parts else "neutral"
        
        combined = f"[TRANSCRIPT] {transcript} [VISUAL]  [EMOTIONS] {emotion_str}"
        
        record = SegmentRecord(
            segment_id=seg_id,
            video_id=video_id,
            start_sec=seg_start,
            end_sec=seg_end,
            transcript=transcript,
            visual_captions=[],
            combined_text=combined,
            frame_paths=[],
            segment_path=seg["segment_path"],
            metadata={
                "index": seg["index"],
                "emotions": emotion_data.get("detected_emotions", []),
                "emotion_scores": emotion_data.get("emotion_scores", {}),
                "visual_emotions": [],
                "visual_scores": {},
                "emotion_intensity": emotion_data.get("emotion_intensity", 0),
                "avg_emotion_confidence": emotion_data.get("avg_emotion_confidence", 0),
                "has_reaction": emotion_data.get("emotion_intensity", 0) > 0,
            },
            speaker="unknown"
        )
        
        record_path = RECORDS_DIR / f"{seg_id}.json"
        record_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        records.append(record)
        
    print(f"Created {len(records)} segments.")
    
    # Step 4: Rebuild indexes
    print("Rebuilding indexes...")
    from embed.bm25_index import build_bm25_index
    from embed.store import rebuild_dense_index
    
    all_records = load_records()
    build_bm25_index(all_records)
    rebuild_dense_index(all_records)
    
    print(f"\nIngestion complete! Video ID: {video_id}")
    return video_id

if __name__ == "__main__":
    video_file = r"C:\Users\abhi\Downloads\Iran_s_survival_strategy_against_US_control_Global_News_Podcast_480P.mp4"
    srt_file = r"C:\Users\abhi\Downloads\NoteGPT_TRANSCRIPT_Iran's survival strategy against US srt.srt"
    ingest_custom(video_file, srt_file)
