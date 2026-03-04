"""Videntia RAG — Retrieval-Augmented Generation for video intelligence."""

__all__ = ["hybrid_retrieve"]


def hybrid_retrieve(*args, **kwargs):
    """Lazy-loaded wrapper for the hybrid retrieval pipeline."""
    from rag.retriever import hybrid_retrieve as _impl
    return _impl(*args, **kwargs)
