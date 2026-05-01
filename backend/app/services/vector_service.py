"""Local vector store operations backed by the application database."""

import logging
import math

from sqlalchemy import delete, select

from app.database import AsyncSessionLocal
from app.models import DocumentChunk

logger = logging.getLogger(__name__)

STOP_WORDS = {
    "what",
    "is",
    "the",
    "in",
    "a",
    "an",
    "of",
    "and",
    "to",
    "for",
    "with",
    "on",
    "at",
    "by",
    "from",
    "about",
    "as",
    "into",
    "like",
    "through",
    "after",
    "over",
    "between",
    "out",
    "against",
    "during",
    "without",
    "before",
    "under",
    "around",
    "among",
}


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if not left or not right or len(left) != len(right):
        return 0.0

    dot_product = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))

    if left_norm == 0 or right_norm == 0:
        return 0.0

    return dot_product / (left_norm * right_norm)


def _extract_keywords(query: str) -> list[str]:
    """Extract lightweight search keywords from a question."""
    keywords: list[str] = []
    for raw_word in query.split():
        word = raw_word.strip("?,.!;'\"").lower()
        if word and word not in STOP_WORDS and len(word) > 2:
            keywords.append(word)
    return keywords


def _keyword_score(text: str, keywords: list[str]) -> int:
    """Count lightweight keyword matches inside a text chunk."""
    lowered = text.lower()
    return sum(lowered.count(keyword) for keyword in keywords)


async def add_document_chunks(
    user_id: str,
    document_id: str,
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    """Store document chunks and embeddings in the local vector table."""
    if not chunks or not embeddings:
        logger.info(
            "Skipping add_document_chunks because chunks or embeddings are empty | user_id=%s | document_id=%s",
            user_id,
            document_id,
        )
        return

    if len(chunks) != len(embeddings):
        raise ValueError("Chunk count does not match embedding count.")
    logger.info(
        "Persisting document chunks | user_id=%s | document_id=%s | chunk_count=%s",
        user_id,
        document_id,
        len(chunks),
    )

    rows = [
        DocumentChunk(
            id=f"{document_id}_chunk_{index}",
            user_id=user_id,
            document_id=document_id,
            chunk_index=index,
            text=chunk,
            embedding=embedding,
        )
        for index, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]

    async with AsyncSessionLocal() as session:
        session.add_all(rows)
        await session.commit()

    logger.info("Added %s chunks for document %s", len(rows), document_id)


async def query_similar_chunks(
    user_id: str,
    query_embedding: list[float],
    top_k: int = 10,
) -> list[dict]:
    """Query the most similar chunks for a specific user."""
    logger.info(
        "Vector search started | user_id=%s | top_k=%s | embedding_dim=%s",
        user_id,
        top_k,
        len(query_embedding),
    )
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DocumentChunk).where(DocumentChunk.user_id == user_id)
        )
        chunks = result.scalars().all()
    logger.info("Vector search candidate pool | user_id=%s | chunk_count=%s", user_id, len(chunks))

    scored_chunks: list[dict] = []
    for chunk in chunks:
        similarity = _cosine_similarity(query_embedding, chunk.embedding)
        scored_chunks.append(
            {
                "id": chunk.id,
                "text": chunk.text,
                "document_id": chunk.document_id,
                "doc_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "similarity": similarity,
                "distance": 1 - similarity,
            }
        )

    scored_chunks.sort(key=lambda item: item["distance"])
    top_results = scored_chunks[:top_k]
    logger.info(
        "Vector search completed | user_id=%s | returned=%s | best_similarity=%.4f",
        user_id,
        len(top_results),
        top_results[0]["similarity"] if top_results else 0.0,
    )
    return top_results


async def search_vector_ids(
    user_id: str,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[str]:
    """Return deduplicated document IDs from vector retrieval results."""
    results = await query_similar_chunks(
        user_id=user_id,
        query_embedding=query_embedding,
        top_k=top_k,
    )

    seen = set()
    doc_ids: list[str] = []
    for chunk in results:
        doc_id = chunk.get("document_id", "")
        if doc_id and doc_id not in seen:
            seen.add(doc_id)
            doc_ids.append(doc_id)

    logger.info("[search_vector_ids] Retrieved doc_ids: %s", doc_ids)
    return doc_ids


async def query_keyword_chunks(
    user_id: str,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Perform a lightweight keyword search over locally stored chunks.

    Returns chunks with a normalized ``keyword_score`` in [0, 1] so that
    downstream hybrid merge can weight keyword relevance meaningfully.
    """
    keywords = _extract_keywords(query)
    if not keywords:
        logger.info("Keyword search skipped | user_id=%s | reason=no_keywords", user_id)
        return []
    logger.info(
        "Keyword search started | user_id=%s | limit=%s | keywords=%s",
        user_id,
        limit,
        keywords,
    )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DocumentChunk).where(DocumentChunk.user_id == user_id)
        )
        chunks = result.scalars().all()

    scored: list[tuple[int, dict]] = []
    max_hits = 0
    for chunk in chunks:
        hits = _keyword_score(chunk.text, keywords)
        if hits <= 0:
            continue
        max_hits = max(max_hits, hits)
        scored.append((hits, {
            "id": chunk.id,
            "text": chunk.text,
            "document_id": chunk.document_id,
            "doc_id": chunk.document_id,
            "chunk_index": chunk.chunk_index,
            "distance": 0.0,
        }))

    # Normalize scores to [0, 1]
    matches: list[dict] = []
    for hits, entry in scored:
        entry["keyword_score"] = hits / max_hits if max_hits > 0 else 0.0
        matches.append(entry)

    matches.sort(key=lambda item: item["keyword_score"], reverse=True)
    top_matches = matches[:limit]
    logger.info(
        "Keyword search completed | user_id=%s | returned=%s | max_hits=%s",
        user_id,
        len(top_matches),
        max_hits,
    )
    return top_matches


async def delete_document_chunks(user_id: str, document_id: str) -> None:
    """Delete all chunks for a specific document from the local vector table."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(DocumentChunk).where(
                DocumentChunk.user_id == user_id,
                DocumentChunk.document_id == document_id,
            )
        )
        await session.commit()

    logger.info("Deleted chunks for document %s", document_id)
