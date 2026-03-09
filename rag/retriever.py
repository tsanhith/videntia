"""
Hybrid Retriever — 5-Stage Retrieval Pipeline.

Stages:
  1a. BM25 sparse search (top 50)
  1b. Dense text semantic search (top 50)
  1c. Dense vision cross-modal search (top 50)
  2.  RRF (Reciprocal Rank Fusion) merge (top 20)
  3.  Cross-encoder reranking (top 8)
  4a. Emotion boosting (if emotion query)
  4b. Sliding-window temporal context (if temporal query)
  5.  Final results (8-12 segments)

Resilience: if ChromaDB is empty, falls back to BM25-only by loading
segment data from disk records so BM25 matches are never silently dropped.
"""

from __future__ import annotations

import re
from rich import print

from embed.bm25_index import bm25_search
from embed.store import dense_search
from rag.reranker import rerank
from config import (
    BM25_TOP_K,
    DENSE_TOP_K,
    RRF_TOP_K,
    RERANK_TOP_K,
    RRF_K,
    TEXT_COLLECTION,
    VISION_COLLECTION,
)


# -- Synonym Map -------------------------------------------------------------
SYNONYM_MAP = {
    # Emotions
    "surprised": "surprised shocked stunned astonished amazed",
    "shocked": "shocked surprised stunned astonished",
    "laughed": "laughed chuckled giggled amused cracked up",
    "happy": "happy joyful excited pleased delighted",
    "sad": "sad upset disappointed dejected",
    "angry": "angry furious mad annoyed irritated",
    "worried": "worried concerned anxious nervous uneasy",
    "confused": "confused puzzled perplexed baffled",
    "celebrating": "celebrating cheering jubilant rejoicing",
    "fearful": "fearful scared afraid frightened terrified",
    # Political / conflict content
    "war": "war conflict strikes bombing military attack",
    "strikes": "strikes bombing attacks airstrikes military operations",
    "control": "control domination regime change occupation",
    "strategy": "strategy plan approach tactic policy",
    "survival": "survival resistance endurance withstand",
    "casualties": "casualties deaths civilian victims killed",
    "sanctions": "sanctions pressure economic punishment penalties",
    "nuclear": "nuclear program weapons missile proliferation",
    "iran": "iran iranian tehran regime irgc",
    "trump": "trump administration washington us policy",
    "allies": "allies partners regional countries arab gulf",
    "civilian": "civilian population people public citizens",
    "resistance": "resistance opposition fighting back pushback",
}


# -- Query Type Detection ----------------------------------------------------
def detect_query_type(query: str) -> dict:
    """Classify the query to choose adaptive retrieval strategy."""
    q = query.lower()

    emotion_kw = [
        "emotion", "feel", "react", "surprise", "laugh", "concern",
        "expression", "facial", "shocked", "angry", "happy", "sad",
        "disbelief", "worried", "crying", "fear", "celebrate", "celebrating",
        "sentiment", "mood", "attitude", "opinion",
    ]
    temporal_kw = [
        "before", "after", "when", "during", "then", "next",
        "sequence", "immediately", "timeline", "first", "later",
        "eventually", "initially", "at the start", "at the end",
    ]
    speaker_kw = [
        "who", "speaker", "person", "says", "said",
        "mentioned", "stated", "told", "according", "bahman",
        "host", "interviewer", "analyst", "expert",
    ]

    return {
        "is_emotion_query": any(kw in q for kw in emotion_kw),
        "is_temporal_query": any(kw in q for kw in temporal_kw),
        "is_speaker_query": any(kw in q for kw in speaker_kw),
        "requires_context": any(kw in q for kw in temporal_kw),
    }


# -- Query Expansion ---------------------------------------------------------
def expand_query(query: str) -> str:
    """Expand query with synonyms for BM25 recall (single match → expand)."""
    q_lower = query.lower()
    expansions = []
    for word, synonyms in SYNONYM_MAP.items():
        if word in q_lower:
            expansions.append(synonyms)

    if expansions:
        return query + " " + " ".join(expansions)
    return query


# -- RRF Fusion --------------------------------------------------------------
def reciprocal_rank_fusion(
    *ranked_lists: list[tuple[str, float]],
    k: int = RRF_K,
) -> list[tuple[str, float]]:
    """
    Merge multiple ranked lists using Reciprocal Rank Fusion.
    score(d) = sum(1/(k + rank))
    """
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, (seg_id, _) in enumerate(ranked, 1):
            scores[seg_id] = scores.get(seg_id, 0.0) + 1.0 / (k + rank)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# -- Emotion Boosting --------------------------------------------------------
def apply_emotion_boost(results: list[dict]) -> list[dict]:
    """Boost rerank scores for segments with high emotion confidence."""
    for r in results:
        metadata = r.get("metadata", {})
        avg_conf = metadata.get("avg_emotion_confidence", 0)
        intensity = metadata.get("emotion_intensity", 0)

        if avg_conf > 0:
            confidence_boost = 1.0 + (0.3 * avg_conf)
            intensity_boost = 1.0 + (0.15 * min(intensity, 3))
            total_boost = confidence_boost * intensity_boost
            r["rerank_score"] = r.get("rerank_score", 0) * total_boost

    return sorted(results, key=lambda x: x.get("rerank_score", 0), reverse=True)


# -- Sliding Window ----------------------------------------------------------
def _extract_index(segment_id: str) -> int | None:
    """Extract numeric index from segment_id like 'test1_seg0003'."""
    m = re.search(r"seg(\d+)$", segment_id)
    return int(m.group(1)) if m else None


def _segment_prefix(segment_id: str) -> str:
    """Get prefix before seg#### for building adjacent IDs."""
    m = re.search(r"^(.+)seg\d+$", segment_id)
    return m.group(1) if m else ""


def apply_sliding_window(
    results: list[dict],
    all_segments: dict[str, dict],
    window: int = 1,
) -> list[dict]:
    """Add +-1 adjacent segments with 0.6x score for temporal context."""
    expanded = []
    seen = set()

    for seg in results:
        seg_id = seg.get("segment_id", "")
        idx = _extract_index(seg_id)
        prefix = _segment_prefix(seg_id)

        if idx is None:
            if seg_id not in seen:
                expanded.append(seg)
                seen.add(seg_id)
            continue

        for offset in range(-window, window + 1):
            neighbor_id = f"{prefix}seg{idx + offset:04d}"
            if neighbor_id in seen:
                continue

            if offset == 0:
                expanded.append(seg)
                seen.add(seg_id)
            elif neighbor_id in all_segments:
                neighbor = dict(all_segments[neighbor_id])
                neighbor["rerank_score"] = seg.get("rerank_score", 0) * 0.6
                expanded.append(neighbor)
                seen.add(neighbor_id)

    return sorted(expanded, key=lambda x: x.get("rerank_score", 0), reverse=True)


# -- Main Retrieval Function -------------------------------------------------
def hybrid_retrieve(query: str, top_k: int = 8, video_id: str | None = None) -> list[dict]:
    """
    Execute the full 5-stage hybrid retrieval pipeline.

    Returns a list of segment dicts, each containing:
      segment_id, transcript, visual_captions, start_sec, end_sec,
      metadata, combined_text, rrf_score, rerank_score

    Resilience: if ChromaDB is empty, BM25 results are loaded from disk
    records so the pipeline always returns something useful.
    """
    query_type = detect_query_type(query)

    print(f"  Query type: emotion={query_type['is_emotion_query']}, "
          f"temporal={query_type['is_temporal_query']}, "
          f"speaker={query_type['is_speaker_query']}")

    # -- Stage 1a: BM25 sparse search ----------------------------------------
    expanded_query = expand_query(query)
    bm25_results = bm25_search(expanded_query, top_k=BM25_TOP_K, video_id=video_id)
    print(f"  BM25: {len(bm25_results)} results")

    # -- Stage 1b: Dense text search -----------------------------------------
    dense_text = dense_search(query, TEXT_COLLECTION, top_k=DENSE_TOP_K, video_id=video_id)
    dense_text_ranked = [(r["segment_id"], r["score"]) for r in dense_text]
    print(f"  Dense text: {len(dense_text)} results")

    # -- Stage 1c: Dense vision search ---------------------------------------
    dense_vision = dense_search(query, VISION_COLLECTION, top_k=DENSE_TOP_K, video_id=video_id)
    dense_vision_ranked = [(r["segment_id"], r["score"]) for r in dense_vision]

    # -- Stage 2: RRF Fusion -------------------------------------------------
    fused = reciprocal_rank_fusion(
        bm25_results,
        dense_text_ranked,
        dense_vision_ranked,
    )[:RRF_TOP_K]

    # Normalize RRF scores to 0-1 range
    # Theoretical max: found at rank 1 in all 3 lists -> 3 * (1 / (RRF_K + 1))
    max_rrf = 3.0 / (RRF_K + 1)
    fused = [(seg_id, min(1.0, score / max_rrf)) for seg_id, score in fused]

    # Build lookup from dense results
    all_segments: dict[str, dict] = {}
    for r in dense_text + dense_vision:
        seg_id = r["segment_id"]
        if seg_id not in all_segments:
            all_segments[seg_id] = r

    # -- Resilience: load BM25-only hits from disk ---------------------------
    # When ChromaDB is empty, BM25 may have found segments that aren't in
    # all_segments. Load them from disk records so they are not dropped.
    fused_ids = {seg_id for seg_id, _ in fused}
    missing_ids = fused_ids - set(all_segments.keys())

    if missing_ids:
        print(f"  Loading {len(missing_ids)} BM25-only segments from disk records")
        try:
            from pipeline.ingest import load_records
            disk_records = load_records(video_id=video_id)
            for rec in disk_records:
                if rec.segment_id in missing_ids:
                    all_segments[rec.segment_id] = {
                        "segment_id": rec.segment_id,
                        "transcript": rec.transcript,
                        "visual_captions": rec.visual_captions,
                        "combined_text": rec.combined_text,
                        "start_sec": rec.start_sec,
                        "end_sec": rec.end_sec,
                        "speaker": rec.speaker or "",
                        "score": 0.0,
                        "metadata": rec.metadata,
                    }
        except Exception as e:
            print(f"  [yellow]Warning: could not load disk records: {e}[/yellow]")

    # Collect full segment data for fused results
    candidates = []
    for seg_id, rrf_score in fused:
        if seg_id in all_segments:
            seg = dict(all_segments[seg_id])
            seg["rrf_score"] = rrf_score
            candidates.append(seg)

    print(f"  Candidates after RRF: {len(candidates)}")

    # -- Stage 3: Cross-encoder reranking ------------------------------------
    reranked = rerank(query, candidates, top_k=RERANK_TOP_K)

    # -- Stage 4a: Emotion boosting ------------------------------------------
    if query_type["is_emotion_query"]:
        print("  Applying emotion boosting")
        reranked = apply_emotion_boost(reranked)

    # -- Stage 4b: Sliding window context ------------------------------------
    if query_type["requires_context"]:
        print("  Adding sliding window context (+-1 segment per match)")
        reranked = apply_sliding_window(reranked, all_segments, window=1)

    # -- Stage 5: Final results ----------------------------------------------
    final = reranked[:top_k]
    print(f"  -> Returning {len(final)} segments")

    return final
