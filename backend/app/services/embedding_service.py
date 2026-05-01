"""Embedding generation service backed by Ollama."""

import asyncio
import logging

from app.config import get_settings
from app.services.ollama_service import (
    OllamaServiceError,
    get_sync_client,
    normalize_ollama_exception,
)

logger = logging.getLogger(__name__)
settings = get_settings()


def _embed(input_data: str | list[str]):
    """Call the configured Ollama embedding model."""
    try:
        return get_sync_client().embed(
            model=settings.OLLAMA_EMBEDDING_MODEL,
            input=input_data,
        )
    except Exception as exc:
        raise normalize_ollama_exception(
            exc,
            model_name=settings.OLLAMA_EMBEDDING_MODEL,
            task_type="embedding",
        ) from exc


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of text strings."""
    if not texts:
        return []

    logger.info(
        "Generating embeddings for %s texts via Ollama (%s)",
        len(texts),
        settings.OLLAMA_EMBEDDING_MODEL,
    )
    batch_size = max(1, settings.OLLAMA_EMBED_BATCH_SIZE)
    embeddings: list[list[float]] = []

    for start_index in range(0, len(texts), batch_size):
        batch = texts[start_index:start_index + batch_size]
        batch_number = (start_index // batch_size) + 1
        total_batches = (len(texts) + batch_size - 1) // batch_size
        logger.info(
            "Embedding batch %s/%s with %s chunks",
            batch_number,
            total_batches,
            len(batch),
        )
        response = _embed(batch)
        embeddings.extend(response["embeddings"])

    logger.info("Generated %s embeddings", len(embeddings))
    return embeddings


async def generate_embeddings_async(texts: list[str]) -> list[list[float]]:
    """Async wrapper that runs embedding generation in a worker thread."""
    return await asyncio.to_thread(generate_embeddings, texts)


def generate_query_embedding(query: str) -> list[float]:
    """Generate an embedding for a single search query."""
    response = _embed(query)
    embeddings = response["embeddings"]
    return embeddings[0] if embeddings else []


async def generate_query_embedding_async(query: str) -> list[float]:
    """Async wrapper for query embedding generation."""
    return await asyncio.to_thread(generate_query_embedding, query)


def diagnose_embedding_model() -> dict:
    """Run a lightweight embedding capability check against Ollama."""
    model_name = settings.OLLAMA_EMBEDDING_MODEL

    try:
        embedding = generate_query_embedding("health check")
        return {
            "status": "ok",
            "model": model_name,
            "detail": "Embedding model is reachable.",
            "dimension": len(embedding),
        }
    except OllamaServiceError as exc:
        return {
            "status": exc.status,
            "model": model_name,
            "detail": exc.user_message,
        }
