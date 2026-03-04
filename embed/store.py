"""
ChromaDB Dense Store — Persistent vector search.

Manages two collections:
  - ``text_segments``   : transcript + emotion embeddings
  - ``vision_segments`` : visual caption embeddings

Uses nomic-embed-text-v1.5 via the text_embedder module.
"""

from __future__ import annotations

from embed.text_embedder import embed_text, embed_batch
from config import CHROMA_DIR, TEXT_COLLECTION, VISION_COLLECTION


# ── Singleton client ────────────────────────────────────────────────────────
_client = None


def _get_client():
    global _client
    if _client is None:
        import chromadb
        from chromadb.config import Settings
        _client = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def _get_collection(name: str):
    client = _get_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


# ── Search ──────────────────────────────────────────────────────────────────
def dense_search(
    query: str,
    collection_name: str,
    top_k: int = 50,
    video_id: str | None = None,
) -> list[dict]:
    """
    Semantic search in a ChromaDB collection.

    Returns
    -------
    list[dict]
        Each dict contains: segment_id, text, score, metadata.
    """
    collection = _get_collection(collection_name)

    # Return empty if collection is empty
    if collection.count() == 0:
        return []

    query_embedding = embed_text(query)

    query_kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": min(1000, collection.count()),
        "include": ["documents", "metadatas", "distances"],
    }

    results = collection.query(**query_kwargs)

    output = []
    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    for seg_id, doc, meta, dist in zip(ids, docs, metas, dists):
        # ChromaDB cosine distance → similarity score
        score = 1.0 - dist

        if video_id and not seg_id.startswith(video_id):
            continue

        output.append({
            "segment_id": seg_id,
            "text": doc,
            "score": score,
            "metadata": meta or {},
            # Propagate fields from metadata for downstream use
            "transcript": meta.get("transcript", doc) if meta else doc,
            "visual_captions": _parse_list_field(meta, "visual_captions"),
            "combined_text": meta.get("combined_text", doc) if meta else doc,
            "start_sec": float(meta.get("start_sec", 0)) if meta else 0.0,
            "end_sec": float(meta.get("end_sec", 0)) if meta else 0.0,
            "speaker": meta.get("speaker", "") if meta else "",
        })

    # Ensure top_k after post-filtering
    output.sort(key=lambda x: x["score"], reverse=True)
    return output[:top_k]


def _parse_list_field(meta: dict | None, key: str) -> list[str]:
    """Safely parse a list field from metadata (stored as JSON string or list)."""
    if not meta or key not in meta:
        return []
    val = meta[key]
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        import json
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else [val]
        except (json.JSONDecodeError, TypeError):
            return [val] if val else []
    return []


# ── Index Building ──────────────────────────────────────────────────────────
def rebuild_dense_index(records) -> None:
    """
    Rebuild both text and vision ChromaDB collections from records.

    Parameters
    ----------
    records : list
        SegmentRecord instances or dicts with segment_id, combined_text,
        transcript, visual_captions, start_sec, end_sec, metadata.
    """
    client = _get_client()

    # Delete existing collections to rebuild
    for name in [TEXT_COLLECTION, VISION_COLLECTION]:
        try:
            client.delete_collection(name)
        except Exception:
            pass

    text_col = _get_collection(TEXT_COLLECTION)
    vision_col = _get_collection(VISION_COLLECTION)

    # Prepare data
    text_ids, text_docs, text_metas = [], [], []
    vision_ids, vision_docs, vision_metas = [], [], []

    for rec in records:
        if hasattr(rec, "segment_id"):
            seg_id = rec.segment_id
            combined = rec.combined_text
            transcript = rec.transcript
            captions = rec.visual_captions
            start = rec.start_sec
            end = rec.end_sec
            meta = rec.metadata
            speaker = rec.speaker or ""
        else:
            seg_id = rec["segment_id"]
            combined = rec.get("combined_text", rec.get("transcript", ""))
            transcript = rec.get("transcript", "")
            captions = rec.get("visual_captions", [])
            start = rec.get("start_sec", 0)
            end = rec.get("end_sec", 0)
            meta = rec.get("metadata", {})
            speaker = rec.get("speaker", "")

        import json
        flat_meta = {
            "transcript": transcript,
            "visual_captions": json.dumps(captions),
            "combined_text": combined,
            "start_sec": float(start),
            "end_sec": float(end),
            "speaker": speaker,
            "emotions": json.dumps(meta.get("emotions", [])),
            "emotion_intensity": float(meta.get("emotion_intensity", 0)),
            "avg_emotion_confidence": float(meta.get("avg_emotion_confidence", 0)),
        }

        # Text collection: uses combined_text
        text_ids.append(seg_id)
        text_docs.append(combined)
        text_metas.append(flat_meta)

        # Vision collection: uses visual captions
        if captions:
            vision_text = " | ".join(captions)
            vision_ids.append(seg_id)
            vision_docs.append(vision_text)
            vision_metas.append(flat_meta)

    # Embed and add in batches
    if text_ids:
        text_embeddings = embed_batch(text_docs)
        text_col.add(
            ids=text_ids,
            embeddings=text_embeddings,
            documents=text_docs,
            metadatas=text_metas,
        )

    if vision_ids:
        vision_embeddings = embed_batch(vision_docs)
        vision_col.add(
            ids=vision_ids,
            embeddings=vision_embeddings,
            documents=vision_docs,
            metadatas=vision_metas,
        )
