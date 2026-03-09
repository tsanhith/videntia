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

    # When filtering by video_id, fetch more candidates because many results
    # will be discarded after the per-segment filter. Without video_id, top_k is enough.
    fetch_k = min(top_k * 20 if video_id else top_k, collection.count())

    query_kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": max(1, fetch_k),
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

        # Use substring match: ingest video_ids embed the upload video_id
        # e.g. segment "a084d88d_5f9d743f_example_seg0001" contains upload id "5f9d743f"
        if video_id and video_id not in seg_id:
            continue

        # Normalize metadata: decode JSON-encoded list/dict fields from ChromaDB
        normalized_meta = _normalize_metadata(meta)

        output.append({
            "segment_id": seg_id,
            "text": doc,
            "score": score,
            "metadata": normalized_meta,
            # Propagate fields from metadata for downstream use
            "transcript": normalized_meta.get("transcript", doc),
            "visual_captions": _parse_list_field(normalized_meta, "visual_captions"),
            "combined_text": normalized_meta.get("combined_text", doc),
            "start_sec": float(normalized_meta.get("start_sec", 0)),
            "end_sec": float(normalized_meta.get("end_sec", 0)),
            "speaker": normalized_meta.get("speaker", ""),
        })

    # Ensure top_k after post-filtering
    output.sort(key=lambda x: x["score"], reverse=True)
    return output[:top_k]


_JSON_LIST_FIELDS = {"visual_captions", "emotions", "visual_emotions"}
_JSON_DICT_FIELDS = {"emotion_scores", "visual_scores"}


def _normalize_metadata(meta: dict | None) -> dict:
    """
    Normalize ChromaDB metadata by parsing JSON-encoded list/dict fields
    back into their Python equivalents.

    ChromaDB requires flat string/int/float/bool metadata values, so list and
    dict fields are stored as JSON strings and must be decoded on read.
    """
    if not meta:
        return {}
    import json as _json
    result = dict(meta)
    for key in _JSON_LIST_FIELDS:
        if key in result and isinstance(result[key], str):
            try:
                parsed = _json.loads(result[key])
                result[key] = parsed if isinstance(parsed, list) else []
            except (ValueError, TypeError):
                result[key] = []
    for key in _JSON_DICT_FIELDS:
        if key in result and isinstance(result[key], str):
            try:
                parsed = _json.loads(result[key])
                result[key] = parsed if isinstance(parsed, dict) else {}
            except (ValueError, TypeError):
                result[key] = {}
    return result


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
            "emotion_scores": json.dumps(meta.get("emotion_scores", {})),
            "visual_emotions": json.dumps(meta.get("visual_emotions", [])),
            "visual_scores": json.dumps(meta.get("visual_scores", {})),
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
