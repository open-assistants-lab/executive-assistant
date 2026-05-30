"""Cross-encoder reranking for better relevance.

Uses a lightweight cross-encoder model to rerank search results.
The query and document interact through the transformer, producing
more accurate relevance scores than embedding similarity alone.

Disabled via DISABLE_CROSS_ENCODER=1 env var (needed for eval
scripts running inside asyncio threads to avoid PyTorch deadlocks).
"""

import os
from typing import Any

_cross_encoder: Any = None


def get_cross_encoder() -> Any:
    """Lazy-load the cross-encoder reranker model."""
    global _cross_encoder
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
            _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        except Exception:
            return None
    return _cross_encoder


def rerank(query: str, results: list[Any], top_k: int = 50) -> list[Any]:
    """Rerank results using a lightweight cross-encoder.

    More accurate than embedding similarity because query and document
    interact through the transformer. Applied as post-processing after
    the initial retrieval.

    Args:
        query: The original search query.
        results: List of SearchResult objects to rerank.
        top_k: Number of top results to rerank (default 50).

    Returns:
        Reranked results list.
    """
    if os.environ.get("DISABLE_CROSS_ENCODER"):
        return results

    model = get_cross_encoder()
    if model is None or not results:
        return results

    candidates = results[:top_k]
    pairs = [(query, r.memory.content[:512]) for r in candidates]
    try:
        scores = model.predict(pairs, show_progress_bar=False, batch_size=32)
        for i, r in enumerate(candidates):
            setattr(r, "_ce_score", float(scores[i]))
        candidates.sort(key=lambda r: getattr(r, "_ce_score", r.score), reverse=True)
        return candidates + results[top_k:]
    except Exception:
        return results
