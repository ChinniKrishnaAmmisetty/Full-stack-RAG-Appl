"""Embedding generation service using Gemini's text-embedding API."""

import logging
import google.generativeai as genai
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _ensure_configured():
    """Ensure Gemini API is configured."""
    genai.configure(api_key=settings.GEMINI_API_KEY)


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of text strings using Gemini.

    Args:
        texts: List of text strings to embed.

    Returns:
        List of embedding vectors (each a list of floats).
    """
    _ensure_configured()
    logger.info(f"Generating embeddings for {len(texts)} texts via Gemini ({settings.GEMINI_EMBEDDING_MODEL})")

    embeddings = []
    # Process in batches of 100 (Gemini API limit)
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        result = genai.embed_content(
            model=f"models/{settings.GEMINI_EMBEDDING_MODEL}",
            content=batch,
            task_type="retrieval_document",
        )
        embeddings.extend(result["embedding"])

    logger.info(f"Generated {len(embeddings)} embeddings")
    return embeddings


def generate_query_embedding(query: str) -> list[float]:
    """Generate an embedding for a single search query.

    Args:
        query: The search query text.

    Returns:
        The embedding vector as a list of floats.
    """
    _ensure_configured()
    result = genai.embed_content(
        model=f"models/{settings.GEMINI_EMBEDDING_MODEL}",
        content=query,
        task_type="retrieval_query",
    )
    return result["embedding"]
