"""
Cross-Encoder Reranker — cross-encoder/ms-marco-MiniLM-L-6-v2.

Uses transformers directly (no sentence-transformers / datasets dependency).
Scores are sigmoid-normalized to 0-1 range.
GPU-accelerated via CUDA when available.

Fallback: if the model is unavailable, ranks by rrf_score instead.
"""

from __future__ import annotations

import math
import torch

RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# -- Singleton ---------------------------------------------------------------
_model = None
_tokenizer = None


def _get_reranker():
    global _model, _tokenizer
    if _model is None:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _tokenizer = AutoTokenizer.from_pretrained(RERANKER_MODEL_NAME)
        _model = AutoModelForSequenceClassification.from_pretrained(RERANKER_MODEL_NAME)
        _model = _model.to(device)
        _model.eval()
        print(f"  [green]Reranker loaded on {device.upper()}[/green]")
    return _model, _tokenizer


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
        model, tokenizer = _get_reranker()
        texts = [c.get(text_key, c.get("transcript", "")) for c in candidates]
        device = next(model.parameters()).device

        # Tokenize all (query, passage) pairs in one batch
        inputs = tokenizer(
            [query] * len(texts),
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            logits = model(**inputs).logits.squeeze(-1)

        # Min-max normalize across the batch so the best result = 1.0, worst = 0.0.
        # This gives meaningful relative relevance for display and confidence scoring.
        raw = logits.cpu().float()
        lo, hi = raw.min().item(), raw.max().item()
        if hi > lo:
            normalized = ((raw - lo) / (hi - lo)).tolist()
        else:
            normalized = [0.5] * len(candidates)

        if isinstance(normalized, float):
            normalized = [normalized]

        for candidate, score in zip(candidates, normalized):
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
