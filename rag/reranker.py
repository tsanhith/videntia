"""
Cross-Encoder Reranker — BAAI/bge-reranker-v2-m3.

Provides a singleton reranker that scores (query, passage) pairs
with a cross-encoder model for precision ranking.

Fallback: if the model is unavailable, ranks by rrf_score instead.
"""

from __future__ import annotations

from config import RERANKER_MODEL_NAME

# -- Singleton ---------------------------------------------------------------
_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        from FlagEmbedding import FlagReranker
        _reranker = FlagReranker(
            RERANKER_MODEL_NAME,
            use_fp16=True,
        )
    return _reranker


def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 8,
    text_key: str = "combined_text",
) -> list[dict]:
    """
    Re-rank candidate segments using the cross-encoder.

    Parameters
    ----------
    query : str
        The search query.
    candidates : list[dict]
        Candidate segments, each containing at least ``text_key``.
    top_k : int
        Number of top results to return.
    text_key : str
        Key in each candidate dict that holds the passage text.

    Returns
    -------
    list[dict]
        Top-k candidates sorted by rerank_score (descending),
        with a ``rerank_score`` field added.
    """
    if not candidates:
        return []

    try:
        model = _get_reranker()
        pairs = [[query, c.get(text_key, c.get("transcript", ""))] for c in candidates]
        scores = model.compute_score(pairs, normalize=True)

        # compute_score returns a single float for a single pair
        if isinstance(scores, (int, float)):
            scores = [scores]

        for candidate, score in zip(candidates, scores):
            candidate["rerank_score"] = float(score)

        ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        return ranked[:top_k]

    except Exception as e:
        print(f"  [yellow]Reranker unavailable ({e}), falling back to RRF score order[/yellow]")
        # Fallback: use RRF score as the rerank score so pipeline still works
        for candidate in candidates:
            candidate["rerank_score"] = float(candidate.get("rrf_score", 0))
        ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        return ranked[:top_k]
