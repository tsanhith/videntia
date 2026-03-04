"""
Text Embedder — nomic-ai/nomic-embed-text-v1.5.

Provides singleton SentenceTransformer for generating 768-D embeddings.
"""

from __future__ import annotations

from config import EMBED_MODEL_NAME

# ── Singleton ───────────────────────────────────────────────────────────────
_model = None


def _get_model():
    global _model
    if _model is None:
        import torch
        from sentence_transformers import SentenceTransformer
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _model = SentenceTransformer(EMBED_MODEL_NAME, device=device, trust_remote_code=True)
    return _model


def embed_text(text: str) -> list[float]:
    """Embed a single text string → 768-D float list."""
    model = _get_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_batch(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """Embed multiple texts → list of 768-D float lists."""
    model = _get_model()
    vecs = model.encode(texts, normalize_embeddings=True, batch_size=batch_size)
    return [v.tolist() for v in vecs]
