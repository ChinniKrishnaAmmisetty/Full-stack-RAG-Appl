# Requirements: sentence-transformers
from __future__ import annotations

import asyncio
import os
from typing import Any

from app.services.embedding_service import generate_query_embedding_async
from app.services.vector_service import query_similar_chunks

ACTIONS: dict[int, dict[str, Any]] = {
    0: {"top_k": 3, "use_reranker": False},
    1: {"top_k": 5, "use_reranker": False},
    2: {"top_k": 5, "use_reranker": True},
    3: {"top_k": 8, "use_reranker": True},
}
_RERANKER: Any = None


def action_config(action_id: int) -> dict[str, Any]:
    return ACTIONS[action_id]


def _clip(value: float) -> float:
    return max(0.0, min(value, 1.0))


def _metric_type(chunk: dict[str, Any]) -> str:
    return str(chunk.get("metric_type") or os.getenv("MILVUS_METRIC_TYPE", "IP")).upper()


def similarity_from_chunk(chunk: dict[str, Any]) -> float:
    if "similarity" in chunk:
        return _clip(float(chunk["similarity"]))
    if "score" in chunk and _metric_type(chunk) == "IP":
        return _clip(float(chunk["score"]))
    distance = max(float(chunk.get("distance", 1.0)), 0.0)
    if _metric_type(chunk) == "L2":
        return _clip(1.0 / (1.0 + distance))
    return _clip(1.0 - distance)


def _bin_query_length(query: str) -> int:
    size = len(query)
    if size < 50:
        return 0
    if size <= 150:
        return 1
    return 2


def _bin_score(value: float, low: float, high: float) -> int:
    if value < low:
        return 0
    if value <= high:
        return 1
    return 2


def _load_reranker() -> Any:
    global _RERANKER
    if _RERANKER is None:
        from sentence_transformers import CrossEncoder

        _RERANKER = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")
    return _RERANKER


async def _base_retrieval(user_id: str, query: str, top_k: int) -> list[dict[str, Any]]:
    embedding = await generate_query_embedding_async(query)
    chunks = await query_similar_chunks(user_id=user_id, query_embedding=embedding, top_k=top_k)
    for chunk in chunks:
        chunk["similarity"] = similarity_from_chunk(chunk)
    chunks.sort(key=lambda item: item["similarity"], reverse=True)
    return chunks


async def build_state(user_id: str, query: str) -> tuple[int, int, int]:
    probe_chunks = await _base_retrieval(user_id=user_id, query=query, top_k=3)
    scores = [chunk["similarity"] for chunk in probe_chunks] or [0.0]
    avg_similarity = _clip(sum(scores) / len(scores))
    max_similarity = _clip(max(scores))
    return (
        _bin_query_length(query),
        _bin_score(avg_similarity, 0.4, 0.7),
        _bin_score(max_similarity, 0.5, 0.8),
    )


async def retrieve_chunks(
    user_id: str,
    query: str,
    top_k: int,
    use_reranker: bool,
) -> list[dict[str, Any]]:
    chunks = await _base_retrieval(user_id=user_id, query=query, top_k=top_k)
    if not use_reranker or not chunks:
        return chunks
    reranker = _load_reranker()
    pairs = [[query, chunk.get("text", "")] for chunk in chunks]
    rerank_scores = await asyncio.to_thread(reranker.predict, pairs)
    for chunk, score in zip(chunks, rerank_scores):
        chunk["rerank_score"] = float(score)
    chunks.sort(key=lambda item: item["rerank_score"], reverse=True)
    return chunks
