"""
Apply Advanced Optimizations to Existing Data
Rebuilds BM25 + ChromaDB indexes with enhanced emotion detection
"""

import os
import sys
from rich import print
from rich.progress import track
from datetime import datetime

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline.ingest import load_records
from pipeline.fuse import extract_emotion_signals
from embed.bm25_index import build_bm25_index
from embed.store import rebuild_dense_index
from config import RECORDS_DIR

def reprocess_emotions():
    """Re-extract emotions with new advanced detection."""
    print("\n[bold cyan]Step 1: Reprocessing emotion signals with advanced detection...[/bold cyan]")
    
    records = load_records()
    if not records:
        print("[red]No records found. Run ingest pipeline first.[/red]")
        return False
    
    print(f"Found {len(records)} segments to reprocess")
    
    updated_records = []
    for record in track(records, description="Extracting emotions..."):
        # Re-extract with new algorithm
        emotion_data = extract_emotion_signals(record.transcript, record.visual_captions)
        
        # Update metadata with new confidence-based data
        record.metadata.update({
            'emotions': emotion_data['detected_emotions'],
            'emotion_scores': emotion_data['emotion_scores'],
            'visual_emotions': emotion_data['visual_emotions'],
            'visual_scores': emotion_data['visual_scores'],
            'emotion_intensity': emotion_data['emotion_intensity'],
            'avg_emotion_confidence': emotion_data['avg_emotion_confidence'],
            'has_reaction': emotion_data['emotion_intensity'] > 0
        })
        
        # Update combined_text with confidence-tagged emotions
        if emotion_data['detected_emotions']:
            emotion_parts = []
            for emo in emotion_data['detected_emotions']:
                conf = emotion_data['emotion_scores'].get(emo, 0)
                emotion_parts.append(f"{emo}({conf:.2f})")
            emotion_str = ", ".join(emotion_parts)
        else:
            emotion_str = "neutral"
        
        # Rebuild combined_text
        transcript_part = f"[TRANSCRIPT] {record.transcript}"
        visual_part = f"[VISUAL] {' | '.join(record.visual_captions)}"
        emotion_part = f"[EMOTIONS] {emotion_str}"
        record.combined_text = f"{transcript_part} {visual_part} {emotion_part}"
        
        updated_records.append(record)
    
    # Save updated records individually
    for record in updated_records:
        record_path = RECORDS_DIR / f"{record.segment_id}.json"
        record_path.write_text(record.model_dump_json(indent=2))
    
    print(f"[green]✓ Updated {len(updated_records)} records with advanced emotion detection[/green]")
    return True

def rebuild_indexes():
    """Rebuild BM25 and ChromaDB with new data."""
    print("\n[bold cyan]Step 2: Rebuilding search indexes...[/bold cyan]")
    
    records = load_records()
    
    # Rebuild BM25
    print("  Building BM25 index...")
    build_bm25_index(records)
    print("  [green]✓ BM25 index rebuilt[/green]")
    
    # Rebuild ChromaDB (both text and vision collections)
    print("  Building ChromaDB embeddings...")
    rebuild_dense_index(records)
    print("  [green]✓ Dense embeddings rebuilt[/green]")

def show_optimization_summary(records):
    """Show summary of optimization improvements."""
    print("\n[bold green]Optimization Summary:[/bold green]")
    
    total_emotions = sum(1 for r in records if r.metadata.get('has_reaction', False))
    avg_confidence = sum(r.metadata.get('avg_emotion_confidence', 0) for r in records) / len(records)
    avg_intensity = sum(r.metadata.get('emotion_intensity', 0) for r in records) / len(records)
    
    # Count emotion types
    emotion_counts = {}
    for r in records:
        for emotion in r.metadata.get('emotions', []):
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
    
    print(f"\n  Total segments: {len(records)}")
    print(f"  Segments with emotions: {total_emotions} ({total_emotions/len(records)*100:.1f}%)")
    print(f"  Average emotion confidence: {avg_confidence:.3f}")
    print(f"  Average emotion intensity: {avg_intensity:.2f}")
    
    if emotion_counts:
        print(f"\n  Emotion distribution:")
        for emotion, count in sorted(emotion_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"    - {emotion}: {count} segments")
    
    print("\n[bold yellow]New Features Enabled:[/bold yellow]")
    print("  ✓ Negation detection ('not surprised' handled correctly)")
    print("  ✓ Emotion confidence scoring (0.0-1.0)")
    print("  ✓ Multi-word emotion phrases detected")
    print("  ✓ Query expansion with synonyms")
    print("  ✓ Sliding window context for temporal queries")
    print("  ✓ Enhanced answer validation/grounding")
    print("  ✓ Confidence-weighted emotion boosting")

if __name__ == "__main__":
    start_time = datetime.now()
    
    print("[bold magenta]VIDENTIA - Advanced Optimizations[/bold magenta]")
    print("=" * 60)
    
    # Step 1: Reprocess emotions
    if not reprocess_emotions():
        sys.exit(1)
    
    # Step 2: Rebuild indexes
    rebuild_indexes()
    
    # Step 3: Show summary
    records = load_records()
    show_optimization_summary(records)
    
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n[bold green]Optimizations applied successfully in {elapsed:.2f}s[/bold green]")
    print("\nTest with: python main.py \"Who showed surprise when hearing about 200 pounds?\"")
