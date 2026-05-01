"""RAG pipeline: hybrid search, cross-encoder reranking, and Ollama generation."""

import logging
from typing import Any

from app.config import get_settings
from app.services.embedding_service import generate_query_embedding_async
from app.services.ollama_service import (
    OllamaServiceError,
    get_async_client,
    get_sync_client,
    normalize_ollama_exception,
)
from app.services.vector_service import query_keyword_chunks, query_similar_chunks

logger = logging.getLogger(__name__)
settings = get_settings()

STREAM_STATUS_STEPS = {
    "queued": "Preparing request",
    "embedding": "Building query embedding",
    "retrieving": "Running hybrid search",
    "matching": "Extracting matching chunks",
    "generating": "Generating grounded answer",
}

# ─── Strict retrieval-grounded system prompt ──────────────────

SYSTEM_PROMPT = """<system_instructions>
You are ACK AI, a retrieval-grounded assistant.

<core_directives>
1. Use ONLY the provided <context>.
2. Do NOT use prior knowledge.
3. If answer not found:
   "I don't have enough information in the retrieved documents."
4. If partial info exists, answer only that part and state missing parts.
5. Prefer HIGH relevance chunks over low-confidence ones.
6. Do NOT mix unrelated chunks.
7. If chunks conflict, state the discrepancy and use the most consistent information.
</core_directives>

<style_and_tone>
- Professional, direct, concise
- Avoid phrases like "based on context"
- Avoid unnecessary wording
</style_and_tone>

<response_framework>

GENERAL:
- Keep answers SHORT and clear
- Prefer 2–5 lines total
- Prioritize most relevant facts first

Definition ("What is"):
- 1–2 simple sentences
- No examples
- No extra explanation

Explanation ("Explain"):
- Use simple bullet-style lines (not markdown symbols)
- Max 4 points
- Each point = 1 idea

Listing:
- Max 5 items
- One per line
- No explanation

Procedural ("How to"):
- Max 4 steps
- Short and direct

Comparative & Negative:
- Direct comparison OR 2–3 points
- If incomplete → state limitation clearly

Conversational:
- Short reply
- Do not repeat last 3 exchanges
- If repeated question → refer to previous answer

</response_framework>
</system_instructions>"""


# ─── Cross-encoder reranker (singleton) ──────────────────────

_RERANKER: Any = None


def _load_reranker() -> Any:
    """Load the cross-encoder reranker model (singleton, lazy-loaded)."""
    global _RERANKER
    if _RERANKER is None:
        from sentence_transformers import CrossEncoder

        _RERANKER = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")
        logger.info("Loaded cross-encoder reranker: cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _RERANKER


# ─── Helpers ─────────────────────────────────────────────────

def detect_mode(query: str) -> str:
    """Infer a response mode from the question."""
    lowered = query.lower()
    if any(word in lowered for word in ["list", "points", "key points", "main points"]):
        return "main_points"
    if any(word in lowered for word in ["explain", "detail", "deep", "why", "how"]):
        return "detailed"
    return "summary"


def _format_user_error(message: str) -> str:
    """Format a frontend-safe error message."""
    return f"Warning: {message}"


def _build_status_event(stage: str, detail: str | None = None) -> dict[str, str]:
    """Create a stream status event without changing the RAG pipeline logic."""
    return {
        "type": "status",
        "stage": stage,
        "step": STREAM_STATUS_STEPS[stage],
        "detail": detail or "",
    }


def _unique_context_chunks(chunks: list[dict]) -> list[dict]:
    """Drop duplicate chunks by normalized text to keep prompts smaller on CPU-only inference."""
    seen_texts: set[str] = set()
    unique_chunks: list[dict] = []
    for chunk in chunks:
        normalized = " ".join(chunk.get("text", "").split())
        if normalized in seen_texts:
            continue
        seen_texts.add(normalized)
        unique_chunks.append(chunk)
    return unique_chunks


# ─── Prompt construction ─────────────────────────────────────

def build_rag_prompt(
    question: str,
    context_chunks: list[dict],
    chat_history: list[dict] | None = None,
    mode: str | None = None,
) -> str:
    """Build the full prompt with retrieved context, chat history, and user question."""
    unique_chunks = _unique_context_chunks(context_chunks)
    if not unique_chunks:
        context_text = "_No relevant document context was found for this query._"
    else:
        parts = []
        for index, chunk in enumerate(unique_chunks, 1):
            doc_name = chunk.get("document_name", "Unknown")
            confidence = chunk.get("confidence", 0.0)
            parts.append(
                f"**[Chunk {index}]** (source: {doc_name}, relevance: {confidence:.0%})\n{chunk['text']}"
            )
        context_text = "\n\n---\n\n".join(parts)

    history_text = ""
    if chat_history:
        history_parts = []
        for msg in chat_history:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            content = msg["content"][:500] + "..." if len(msg["content"]) > 500 else msg["content"]
            history_parts.append(f"**{role_label}:** {content}")
        history_text = "\n\n".join(history_parts)

    prompt = f"""## DOCUMENT CONTEXT
{context_text}

"""
    if history_text:
        prompt += f"""## RECENT CHAT HISTORY
{history_text}

"""
    if mode:
        prompt += f"""## RESPONSE STYLE
Use a `{mode}` response style while staying faithful to the retrieved documents.

"""
    prompt += f"""## CURRENT QUESTION
{question}

Answer strictly from the document context above. If the context does not contain the answer, say so clearly."""

    return prompt


# ─── Hybrid merge ────────────────────────────────────────────

def merge_and_rerank(
    vector_results: list[dict],
    keyword_results: list[dict],
    query: str,
) -> list[dict]:
    """Merge vector and keyword results using configurable weighted scoring.

    Vector results carry a similarity/distance score.
    Keyword results carry a normalized keyword_score in [0, 1].
    """
    vector_weight = settings.VECTOR_WEIGHT
    keyword_weight = settings.KEYWORD_WEIGHT
    merged: dict[str, dict] = {}

    for result in vector_results:
        chunk_id = result.get("id")
        similarity = result.get("similarity", 1.0 - result.get("distance", 1.0))
        merged[chunk_id] = {
            "id": chunk_id,
            "text": result.get("text", ""),
            "document_id": result.get("document_id", ""),
            "doc_id": result.get("doc_id", result.get("document_id", "")),
            "chunk_index": result.get("chunk_index", 0),
            "vector_score": max(0.0, min(similarity, 1.0)),
            "keyword_score": 0.0,
        }

    for result in keyword_results:
        chunk_id = result.get("id")
        kw_score = result.get("keyword_score", 0.0)
        if chunk_id in merged:
            merged[chunk_id]["keyword_score"] = kw_score
        else:
            merged[chunk_id] = {
                "id": chunk_id,
                "text": result.get("text", ""),
                "document_id": result.get("document_id", ""),
                "doc_id": result.get("doc_id", result.get("document_id", "")),
                "chunk_index": result.get("chunk_index", 0),
                "vector_score": 0.0,
                "keyword_score": kw_score,
            }

    chunks = []
    for chunk in merged.values():
        final_score = (vector_weight * chunk["vector_score"]) + (keyword_weight * chunk["keyword_score"])
        chunks.append(
            {
                "id": chunk["id"],
                "text": chunk["text"],
                "document_id": chunk["document_id"],
                "doc_id": chunk["doc_id"],
                "chunk_index": chunk["chunk_index"],
                "score": final_score,
                "vector_score": chunk["vector_score"],
                "keyword_score": chunk["keyword_score"],
            }
        )

    chunks.sort(key=lambda item: item["score"], reverse=True)

    if chunks:
        logger.info(
            "Hybrid merge completed | total=%s | weights=%.2f/%.2f (vec/kw) | top_score=%.4f",
            len(chunks),
            vector_weight,
            keyword_weight,
            chunks[0]["score"],
        )
        # Log top 5 for debugging
        for i, c in enumerate(chunks[:5]):
            logger.debug(
                "  hybrid[%s] score=%.4f vec=%.4f kw=%.4f chunk_id=%s",
                i, c["score"], c["vector_score"], c["keyword_score"], c["id"][:30],
            )

    return chunks


# ─── Cross-encoder reranking ─────────────────────────────────

def apply_cross_encoder_reranking(chunks: list[dict], query: str, final_k: int | None = None) -> list[dict]:
    """Rerank chunks using a cross-encoder model for precise relevance scoring.

    This replaces the lightweight word-overlap bonus with a proper neural reranker.
    Falls back to score-based truncation if the reranker model is unavailable.
    """
    if final_k is None:
        final_k = settings.TOP_K_RESULTS

    if not chunks:
        return []

    try:
        reranker = _load_reranker()
        pairs = [[query, chunk.get("text", "")] for chunk in chunks]
        rerank_scores = reranker.predict(pairs)

        for chunk, score in zip(chunks, rerank_scores):
            chunk["rerank_score"] = float(score)

        chunks.sort(key=lambda item: item["rerank_score"], reverse=True)

        logger.info(
            "Cross-encoder reranking completed | input=%s | output=%s | top_rerank_score=%.4f",
            len(chunks),
            min(len(chunks), final_k),
            chunks[0]["rerank_score"] if chunks else 0.0,
        )
        for i, c in enumerate(chunks[:final_k]):
            logger.debug(
                "  reranked[%s] rerank=%.4f hybrid=%.4f chunk_id=%s",
                i, c.get("rerank_score", 0), c.get("score", 0), c["id"][:30],
            )

    except Exception as exc:
        logger.warning("Cross-encoder reranking failed, falling back to hybrid scores: %s", exc)

    return chunks[:final_k]


# ─── Source building ─────────────────────────────────────────

async def build_sources_with_db(final_chunks: list[dict]) -> tuple[list[dict], list[dict]]:
    """Fetch document names from the database and build a sources list."""
    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models import Document

    final_chunks = _unique_context_chunks(final_chunks)
    doc_ids = list({str(chunk["document_id"]) for chunk in final_chunks})
    id_to_name: dict[str, str] = {}

    if doc_ids:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Document).where(Document.id.in_(doc_ids)))
            for document in result.scalars().all():
                id_to_name[str(document.id)] = document.filename

    sources = []
    seen_ids = set()
    for chunk in final_chunks:
        score = chunk.get("score", 0.0)
        chunk["confidence"] = max(0.0, min(score, 1.0))
        chunk["document_name"] = id_to_name.get(str(chunk["document_id"]), "Unknown")

        if chunk["id"] in seen_ids:
            continue

        seen_ids.add(chunk["id"])
        sources.append(
            {
                "document_name": chunk["document_name"],
                "chunk_index": chunk["chunk_index"],
                "preview": chunk["text"][:150],
                "confidence": round(chunk["confidence"], 2),
            }
        )

    return final_chunks, sources


# ─── Diagnostics ─────────────────────────────────────────────

def diagnose_generation_model() -> dict:
    """Run a lightweight generation capability check against Ollama."""
    try:
        response = get_sync_client().chat(
            model=settings.OLLAMA_LLM_MODEL,
            messages=[
                {"role": "user", "content": "Reply with OK."},
            ],
        )
        content = response["message"]["content"].strip()
        return {
            "status": "ok",
            "model": settings.OLLAMA_LLM_MODEL,
            "detail": "Generation model is reachable.",
            "sample": content,
        }
    except Exception as exc:
        normalized = normalize_ollama_exception(
            exc,
            model_name=settings.OLLAMA_LLM_MODEL,
            task_type="generation",
        )
        return {
            "status": normalized.status,
            "model": settings.OLLAMA_LLM_MODEL,
            "detail": normalized.user_message,
        }


# ─── Non-streaming RAG pipeline ─────────────────────────────

async def generate_rag_response(
    user_id: str,
    question: str,
    chat_history: list[dict] | None = None,
    mode: str | None = None,
) -> str:
    """Execute the full RAG pipeline for a non-streaming response."""
    try:
        mode = mode or detect_mode(question)
        search_query = question.strip()

        try:
            query_embedding = await generate_query_embedding_async(search_query)
        except OllamaServiceError as exc:
            logger.warning("Query embedding unavailable: %s", exc)
            return _format_user_error(exc.user_message)

        candidate_limit = settings.CANDIDATE_TOP_K
        vector_chunks = await query_similar_chunks(
            user_id=user_id,
            query_embedding=query_embedding,
            top_k=candidate_limit,
        )
        keyword_chunks = await query_keyword_chunks(
            user_id=user_id,
            query=search_query,
            limit=candidate_limit,
        )
        logger.info(
            "Retrieved candidates | user_id=%s | vector=%s | keyword=%s | candidate_limit=%s",
            user_id,
            len(vector_chunks),
            len(keyword_chunks),
            candidate_limit,
        )

        merged_chunks = merge_and_rerank(vector_chunks, keyword_chunks, search_query)
        reranked_chunks = apply_cross_encoder_reranking(
            merged_chunks, search_query, final_k=settings.TOP_K_RESULTS
        )
        final_chunks, _sources = await build_sources_with_db(reranked_chunks)
        logger.info(
            "Prepared final context | user_id=%s | unique_chunks=%s",
            user_id,
            len(final_chunks),
        )

        if not final_chunks:
            return "Sorry, please ask only questions related to your uploaded documents only."

        rag_prompt = build_rag_prompt(question, final_chunks, chat_history, mode=mode)
        logger.info(
            "Sending generation request | user_id=%s | mode=%s | prompt_chars=%s",
            user_id,
            mode,
            len(rag_prompt),
        )

        try:
            response = await get_async_client().chat(
                model=settings.OLLAMA_LLM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": rag_prompt},
                ],
            )
            content = response["message"]["content"]
        except Exception as exc:
            normalized = normalize_ollama_exception(
                exc,
                model_name=settings.OLLAMA_LLM_MODEL,
                task_type="generation",
            )
            logger.warning(
                "Ollama generation unavailable (%s): %s",
                normalized.status,
                normalized.user_message,
            )
            return _format_user_error(normalized.user_message)

        if content:
            logger.info("Generation completed | user_id=%s | answer_chars=%s", user_id, len(content))
            return content
        return "I was unable to generate a response. Please try again."

    except Exception as exc:
        logger.error("Unexpected RAG pipeline error: %s", exc, exc_info=True)
        return "An error occurred while processing your question. Please try again later."


# ─── Streaming RAG pipeline ──────────────────────────────────

async def generate_rag_response_stream(
    user_id: str,
    question: str,
    chat_history: list[dict] | None = None,
    mode: str | None = None,
):
    """Streaming version of the RAG pipeline."""
    try:
        yield _build_status_event("queued", "Request received and pipeline started.")
        mode = mode or detect_mode(question)
        yield {"type": "mode", "data": mode}
        yield _build_status_event("embedding", "Converting your question into an embedding for retrieval.")

        search_query = question.strip()

        try:
            query_embedding = await generate_query_embedding_async(search_query)
        except OllamaServiceError as exc:
            logger.warning("Query embedding unavailable: %s", exc)
            yield _format_user_error(exc.user_message)
            return

        candidate_limit = settings.CANDIDATE_TOP_K
        yield _build_status_event(
            "retrieving",
            f"Searching the vector database and keyword index for up to {candidate_limit} candidates.",
        )
        vector_chunks = await query_similar_chunks(
            user_id=user_id,
            query_embedding=query_embedding,
            top_k=candidate_limit,
        )
        keyword_chunks = await query_keyword_chunks(
            user_id=user_id,
            query=search_query,
            limit=candidate_limit,
        )
        logger.info(
            "Streaming: Retrieved candidates | user_id=%s | vector=%s | keyword=%s",
            user_id,
            len(vector_chunks),
            len(keyword_chunks),
        )

        merged_chunks = merge_and_rerank(vector_chunks, keyword_chunks, search_query)
        reranked_chunks = apply_cross_encoder_reranking(
            merged_chunks, search_query, final_k=settings.TOP_K_RESULTS
        )
        final_chunks, sources = await build_sources_with_db(reranked_chunks)
        matched_documents = list(dict.fromkeys(source["document_name"] for source in sources))
        matched_documents_label = ", ".join(matched_documents[:3])
        if len(matched_documents) > 3:
            matched_documents_label += ", ..."
        matching_detail = (
            f"Selected {len(sources)} chunks from {len(matched_documents)} documents"
            + (f": {matched_documents_label}" if matched_documents_label else ".")
        )
        yield _build_status_event("matching", matching_detail)
        logger.info(
            "Prepared final streaming context | user_id=%s | unique_chunks=%s",
            user_id,
            len(final_chunks),
        )

        if not final_chunks:
            yield _build_status_event("matching", "No matching chunks were found in the retrieved results.")
            yield "Sorry, please ask only questions related to your uploaded documents only."
            return

        yield {"type": "sources", "data": sources}

        rag_prompt = build_rag_prompt(question, final_chunks, chat_history, mode=mode)
        yield _build_status_event("generating", "Generating the response from the selected chunks.")
        logger.info(
            "Starting streaming generation | user_id=%s | mode=%s | prompt_chars=%s",
            user_id,
            mode,
            len(rag_prompt),
        )

        try:
            response = await get_async_client().chat(
                model=settings.OLLAMA_LLM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": rag_prompt},
                ],
                stream=True,
            )
        except Exception as exc:
            normalized = normalize_ollama_exception(
                exc,
                model_name=settings.OLLAMA_LLM_MODEL,
                task_type="generation",
            )
            logger.warning(
                "Ollama streaming unavailable (%s): %s",
                normalized.status,
                normalized.user_message,
            )
            yield _format_user_error(normalized.user_message)
            return

        emitted_chars = 0
        async for chunk in response:
            text = chunk["message"]["content"]
            if text:
                emitted_chars += len(text)
                yield text
        logger.info("Completed streaming generation | user_id=%s | emitted_chars=%s", user_id, emitted_chars)

    except Exception as exc:
        logger.error("Unexpected RAG streaming error: %s", exc, exc_info=True)
        yield "An error occurred while processing your question."
