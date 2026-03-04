"""
BM25 Sparse Search — Keyword-based retrieval using BM25Okapi.

Builds and queries a BM25 index backed by a pickle file at ``db/bm25.pkl``.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import nltk
from rank_bm25 import BM25Okapi

from config import DB_DIR

# Ensure punkt tokenizer is available
try:
    nltk.data.find("tokenizers/punkt_tab")
except LookupError:
    nltk.download("punkt_tab", quiet=True)

BM25_PATH = Path(DB_DIR) / "bm25.pkl"

# ── In-memory cache ────────────────────────────────────────────────────────
_index: dict | None = None  # {"bm25": BM25Okapi, "ids": [...], "corpus": [...]}


def _load_index() -> dict | None:
    global _index
    if _index is not None:
        return _index
    if BM25_PATH.exists():
        with open(BM25_PATH, "rb") as f:
            _index = pickle.load(f)
        return _index
    return None


def build_bm25_index(records) -> None:
    """
    Build a BM25 index from segment records and persist to disk.

    Parameters
    ----------
    records : list
        Pydantic SegmentRecord instances or dicts with
        ``segment_id`` and ``combined_text`` fields.
    """
    global _index

    corpus_ids = []
    tokenized_corpus = []

    for rec in records:
        if hasattr(rec, "segment_id"):
            seg_id = rec.segment_id
            text = rec.combined_text
        else:
            seg_id = rec["segment_id"]
            text = rec.get("combined_text", rec.get("transcript", ""))

        tokens = nltk.word_tokenize(text.lower())
        corpus_ids.append(seg_id)
        tokenized_corpus.append(tokens)

    bm25 = BM25Okapi(tokenized_corpus)

    _index = {
        "bm25": bm25,
        "ids": corpus_ids,
        "corpus": tokenized_corpus,
    }

    with open(BM25_PATH, "wb") as f:
        pickle.dump(_index, f)


def bm25_search(query: str, top_k: int = 50, video_id: str | None = None) -> list[tuple[str, float]]:
    """
    Search the BM25 index.

    Returns
    -------
    list[tuple[str, float]]
        Top-k (segment_id, score) pairs sorted by score descending.
    """
    index = _load_index()
    if index is None:
        return []

    bm25: BM25Okapi = index["bm25"]
    ids: list[str] = index["ids"]

    tokens = nltk.word_tokenize(query.lower())
    scores = bm25.get_scores(tokens)

    # Pair IDs with scores, sort descending
    paired = sorted(zip(ids, scores), key=lambda x: x[1], reverse=True)

    if video_id:
        paired = [p for p in paired if p[0].startswith(video_id)]

    return paired[:top_k]
