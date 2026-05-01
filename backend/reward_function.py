# Requirements: ollama
from __future__ import annotations

from app.services.embedding_service import generate_embeddings_async


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return max(0.0, min(dot / (left_norm * right_norm), 1.0))


def _source_doc_id(chunk: dict[str, object]) -> str:
    return str(
        chunk.get("doc_id")
        or chunk.get("document_id")
        or ""
    ).strip()


def retrieval_hit(expected_doc_ids: list[str], retrieved_chunks: list[dict[str, object]]) -> float:
    expected = set(expected_doc_ids)
    return 1.0 if any(_source_doc_id(chunk) in expected for chunk in retrieved_chunks) else 0.0


async def semantic_similarity(generated_answer: str, expected_answer: str) -> float:
    vectors = await generate_embeddings_async([generated_answer or "", expected_answer or ""])
    if len(vectors) != 2:
        return 0.0
    return cosine_similarity(vectors[0], vectors[1])


def latency_penalty(response_time_seconds: float) -> float:
    return min(response_time_seconds * 0.02, 0.5)


async def compute_reward(
    expected_doc_ids: list[str],
    retrieved_chunks: list[dict[str, object]],
    generated_answer: str,
    expected_answer: str,
    response_time_seconds: float,
) -> dict[str, float]:
    hit = retrieval_hit(expected_doc_ids, retrieved_chunks)
    raw_cosine = await semantic_similarity(generated_answer, expected_answer)
    quality = 0.0 if raw_cosine < 0.2 else raw_cosine
    penalty = latency_penalty(response_time_seconds)
    return {
        "retrieval_hit": hit,
        "answer_quality": quality,
        "latency_penalty": penalty,
        "semantic_similarity": raw_cosine,
        "reward": hit + quality - penalty,
    }
