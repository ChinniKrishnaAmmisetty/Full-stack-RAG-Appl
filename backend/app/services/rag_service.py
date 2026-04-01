"""RAG pipeline: query expansion → hybrid search → reranking → Gemini generation (with streaming & memory)."""

import logging
import google.generativeai as genai
from app.config import get_settings
from app.services.embedding_service import generate_query_embedding
from app.services.vector_service import query_similar_chunks, query_keyword_chunks

logger = logging.getLogger(__name__)
settings = get_settings()

# ───────────────────────────────────────────────────────────────
#  Production-grade system prompt
# ───────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are **ACK AI**, a professional document-analysis assistant. Your sole knowledge source is the DOCUMENT CONTEXT retrieved from the user's uploaded files.

## Core Rules
1. **Strictly use the provided DOCUMENT CONTEXT.** Never use outside knowledge, training data, or assumptions.
2. If the context is empty, irrelevant, or does not contain the answer, respond clearly:
   _"Sorry, please ask only questions related to your uploaded documents only."_
3. If only partial information is available, share what you found and explicitly note what is missing.

## Formatting Guidelines
- Use **Markdown** in every response: headings (`##`, `###`), **bold** for key terms, bullet lists, and numbered lists where appropriate.
- For code or technical content, use fenced code blocks with the correct language identifier.
- Keep paragraphs short (2-3 sentences max). Use whitespace generously for readability.
- When listing items, prefer numbered lists for sequential/ordered content and bullet lists for unordered content.

## Conversation Behavior
- You have access to the recent CHAT HISTORY. Use it to understand follow-up questions like "tell me more", "explain point 3", or "what about X?".
- Never repeat information the user already received unless they explicitly ask.
- If the user asks a question unrelated to their documents, politely redirect them.

## Tone & Quality
- Be concise, accurate, and professional.
- Respond like a senior analyst presenting findings — structured, confident, and data-driven.
- Avoid filler words, unnecessary disclaimers, or overly verbose explanations."""

# Model used for lightweight tasks like query expansion (cheaper and faster)
QUERY_EXPANSION_MODEL = "gemini-2.0-flash"


def build_rag_prompt(question: str, context_chunks: list[dict], chat_history: list[dict] | None = None) -> str:
    """Build the full prompt with retrieved context, chat history, and user question."""

    # 1. Document context
    if not context_chunks:
        context_text = "_No relevant document context was found for this query._"
    else:
        context_parts = []
        for i, chunk in enumerate(context_chunks, 1):
            context_parts.append(f"**[Chunk {i}]**\n{chunk['text']}")
        context_text = "\n\n---\n\n".join(context_parts)

    # 2. Conversation history (last N messages for follow-up context)
    history_text = ""
    if chat_history:
        history_parts = []
        for msg in chat_history:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            # Truncate long past messages to save context window
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
    prompt += f"""## CURRENT QUESTION
{question}

Provide a well-structured, accurate answer based on the document context above."""

    return prompt


async def expand_query(question: str) -> str:
    """Use a lightweight Gemini model to expand a short/ambiguous user question into a better search query.

    Skips expansion for queries that are already well-formed (> 10 words).
    Uses a flash model to minimize latency and cost.
    """
    # Skip expansion for well-formed queries
    word_count = len(question.strip().split())
    if word_count > 10:
        logger.info(f"Query expansion skipped — query already has {word_count} words")
        return question

    try:
        model = genai.GenerativeModel(model_name=QUERY_EXPANSION_MODEL)
        prompt = f"""You are a search query optimizer for a vector database.
Rewrite the user's question into a highly descriptive, keyword-rich search query.
Resolve ambiguity, expand acronyms, and add relevant synonyms.
If the query is already well-formed, return it unchanged.
ONLY return the rewritten query — do NOT answer the question.

User Question: {question}
Optimized Query:"""

        response = model.generate_content(prompt)
        expanded = response.text.strip() if response and response.text else question
        logger.info(f"Query Expansion: '{question}' -> '{expanded}'")
        return expanded
    except Exception as e:
        logger.warning(f"Query expansion failed: {e}. Using original query.")
        return question


def merge_and_rerank(vector_results: list[dict], keyword_results: list[dict], query: str) -> list[dict]:
    """Merge vector and keyword results, deduplicate, and re-rank using normalized weighted scoring.

    Uses a weighted combination:
    - 70% vector similarity (cosine distance already in 0-1 range)
    - 30% keyword density (normalized count of query words found in chunk)
    """
    unique_chunks = {}
    for res in vector_results + keyword_results:
        chunk_id = res.get("id")
        if chunk_id not in unique_chunks:
            unique_chunks[chunk_id] = res

    chunks = list(unique_chunks.values())
    query_words = set([w.strip("?,.!;'\"").lower() for w in query.split() if len(w) > 2])

    if not query_words:
        return chunks[:5]

    for chunk in chunks:
        text_lower = chunk["text"].lower()

        # Keyword density: fraction of query words found in the chunk (0.0 to 1.0)
        matched_words = sum(1 for qw in query_words if qw in text_lower)
        keyword_score = matched_words / len(query_words)

        # Vector similarity: cosine similarity is already 0-1 for normalized vectors
        vector_score = chunk.get("distance", 0.0)

        # Weighted combination
        chunk["rerank_score"] = (0.7 * vector_score) + (0.3 * keyword_score)

    chunks.sort(key=lambda x: x["rerank_score"], reverse=True)
    return chunks[:5]


async def generate_rag_response(
    user_id: str,
    question: str,
    chat_history: list[dict] | None = None,
) -> str:
    """Execute the full RAG pipeline: expand → embed → search → rerank → generate."""
    try:
        if not settings.GEMINI_API_KEY:
            return "⚠️ No Gemini API key configured. Please set GEMINI_API_KEY in `backend/environment/.env`."

        genai.configure(api_key=settings.GEMINI_API_KEY)

        # 1. Query Expansion
        expanded_query = await expand_query(question)

        # 2. Embed the expanded query
        query_embedding = generate_query_embedding(expanded_query)

        # 3. Hybrid Search — Vector (top 10)
        vector_chunks = query_similar_chunks(user_id=user_id, query_embedding=query_embedding, top_k=10)

        # 4. Hybrid Search — Keyword LIKE (top 10)
        keyword_chunks = query_keyword_chunks(user_id=user_id, query=expanded_query, limit=10)

        logger.info(f"Retrieved {len(vector_chunks)} vector + {len(keyword_chunks)} keyword chunks for user {user_id}")

        # 5. Merge, deduplicate, rerank → top 5
        reranked_chunks = merge_and_rerank(vector_chunks, keyword_chunks, expanded_query)

        # 6. Build prompt with context + history
        rag_prompt = build_rag_prompt(question, reranked_chunks, chat_history)

        # 7. Generate via Gemini
        logger.info(f"Calling Gemini ({settings.GEMINI_MODEL}) for response generation...")
        model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
        )

        response = model.generate_content(
            rag_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=4096,
            ),
        )

        if response and response.text:
            return response.text
        else:
            return "I was unable to generate a response. Please try again."

    except Exception as e:
        error_msg = str(e)
        if "API_KEY_INVALID" in error_msg or "API Key not found" in error_msg:
            logger.error("Invalid Gemini API key")
            return "⚠️ The Gemini API key is invalid. Please update it in `backend/environment/.env`."
        elif "quota" in error_msg.lower() or "rate" in error_msg.lower() or "Resource" in error_msg:
            logger.warning(f"Gemini rate limit hit: {e}")
            return "⚠️ Gemini API rate limit reached. Please wait a moment and try again."
        else:
            logger.error(f"RAG pipeline error: {e}", exc_info=True)
            return "An error occurred while processing your question. Please try again later."


async def generate_rag_response_stream(
    user_id: str,
    question: str,
    chat_history: list[dict] | None = None,
):
    """Streaming version of the RAG pipeline — yields text chunks as they arrive from Gemini."""
    try:
        if not settings.GEMINI_API_KEY:
            yield "⚠️ No Gemini API key configured."
            return

        genai.configure(api_key=settings.GEMINI_API_KEY)

        expanded_query = await expand_query(question)
        query_embedding = generate_query_embedding(expanded_query)
        vector_chunks = query_similar_chunks(user_id=user_id, query_embedding=query_embedding, top_k=10)
        keyword_chunks = query_keyword_chunks(user_id=user_id, query=expanded_query, limit=10)
        reranked_chunks = merge_and_rerank(vector_chunks, keyword_chunks, expanded_query)
        rag_prompt = build_rag_prompt(question, reranked_chunks, chat_history)

        logger.info(f"Streaming Gemini ({settings.GEMINI_MODEL}) response...")
        model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
        )

        response = model.generate_content(
            rag_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=4096,
            ),
            stream=True,
        )

        for chunk in response:
            if chunk.text:
                yield chunk.text

    except Exception as e:
        error_msg = str(e)
        if "API_KEY_INVALID" in error_msg or "API Key not found" in error_msg:
            yield "⚠️ The Gemini API key is invalid."
        elif "quota" in error_msg.lower() or "rate" in error_msg.lower() or "Resource" in error_msg:
            yield "⚠️ Gemini API rate limit reached. Please wait and try again."
        else:
            logger.error(f"RAG streaming error: {e}", exc_info=True)
            yield "An error occurred while processing your question."

