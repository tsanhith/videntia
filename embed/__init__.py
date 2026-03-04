"""Videntia Embed — Vector storage and search modules."""

__all__ = [
    "embed_text",
    "embed_batch",
    "dense_search",
    "rebuild_dense_index",
    "bm25_search",
    "build_bm25_index",
]


def __getattr__(name):
    """Lazy attribute loading to avoid heavy ML imports at module import time."""
    if name in ("embed_text", "embed_batch"):
        from embed.text_embedder import embed_text, embed_batch
        return embed_text if name == "embed_text" else embed_batch
    if name in ("dense_search", "rebuild_dense_index"):
        from embed.store import dense_search, rebuild_dense_index
        return dense_search if name == "dense_search" else rebuild_dense_index
    if name in ("bm25_search", "build_bm25_index"):
        from embed.bm25_index import bm25_search, build_bm25_index
        return bm25_search if name == "bm25_search" else build_bm25_index
    raise AttributeError(f"module 'embed' has no attribute {name!r}")
