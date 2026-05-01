"""Chat session and message endpoints with RAG integration (streaming + memory)."""

import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ChatMessage, ChatSession, User
from app.schemas import (
    ChatSessionCreate,
    ChatSessionResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatResponse,
    RLQueryRequest,
    RLQueryResponse,
)
from app.auth import get_current_user
from app.config import get_settings
from app.services.ollama_service import get_async_client
from app.services.rag_service import (
    SYSTEM_PROMPT,
    build_rag_prompt,
    build_sources_with_db,
    generate_rag_response,
    generate_rag_response_stream,
)
from retrieval_policy import action_config, build_state, retrieve_chunks
from reward_function import compute_reward
from rl_agent import QLearningAgent

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/chat", tags=["Chat"])

# Max conversation history messages to pass to the LLM
MAX_HISTORY_MESSAGES = 10


async def _get_chat_history(db: AsyncSession, session_id: str) -> list[dict]:
    """Fetch the last N messages from a session for conversation memory."""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(MAX_HISTORY_MESSAGES)
    )
    messages = result.scalars().all()
    # Reverse to chronological order
    messages.reverse()
    return [{"role": m.role, "content": m.content} for m in messages]


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    data: ChatSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new chat session."""
    session = ChatSession(user_id=current_user.id, title=data.title or "New Chat")
    db.add(session)
    await db.flush()
    logger.info("Created chat session | user_id=%s | session_id=%s", current_user.id, session.id)
    return session


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all chat sessions for the current user, most recent first."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.created_at.desc())
    )
    sessions = result.scalars().all()
    logger.info("Listed %s chat sessions for user %s", len(sessions), current_user.id)
    return sessions


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all messages in a chat session."""
    logger.info("Fetching chat messages | user_id=%s | session_id=%s", current_user.id, session_id)
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = result.scalars().all()
    logger.info(
        "Fetched %s chat messages | user_id=%s | session_id=%s",
        len(messages),
        current_user.id,
        session_id,
    )
    return messages


@router.post("/sessions/{session_id}/messages", response_model=ChatResponse)
async def send_message(
    session_id: str,
    data: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message and get a RAG-powered response (non-streaming)."""
    started_at = time.perf_counter()
    logger.info(
        "Chat message request | user_id=%s | session_id=%s | chars=%s | mode=%s",
        current_user.id,
        session_id,
        len(data.content),
        data.mode or "auto",
    )
    # Verify session belongs to user
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Fetch conversation history for memory
    chat_history = await _get_chat_history(db, session_id)

    # Save user message
    user_message = ChatMessage(session_id=session_id, role="user", content=data.content)
    db.add(user_message)
    await db.flush()

    # Update session title on first message
    result = await db.execute(select(ChatMessage).where(ChatMessage.session_id == session_id))
    message_count = len(result.scalars().all())
    if message_count == 1 and session.title == "New Chat":
        session.title = data.content[:50] + ("..." if len(data.content) > 50 else "")

    # Generate RAG response with conversation memory
    logger.info("Generating RAG response | user_id=%s | session_id=%s", current_user.id, session_id)
    answer = await generate_rag_response(
        user_id=current_user.id,
        question=data.content,
        chat_history=chat_history,
        mode=data.mode,
    )

    # Save assistant message
    assistant_message = ChatMessage(session_id=session_id, role="assistant", content=answer)
    db.add(assistant_message)
    await db.flush()
    logger.info(
        "Completed chat response | user_id=%s | session_id=%s | answer_chars=%s | elapsed=%.3fs",
        current_user.id,
        session_id,
        len(answer),
        time.perf_counter() - started_at,
    )

    return ChatResponse(
        user_message=ChatMessageResponse.model_validate(user_message),
        assistant_message=ChatMessageResponse.model_validate(assistant_message),
    )


@router.post("/sessions/{session_id}/messages/stream")
async def send_message_stream(
    session_id: str,
    data: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message and stream the RAG response via Server-Sent Events (SSE)."""
    logger.info(
        "Streaming chat request | user_id=%s | session_id=%s | chars=%s | mode=%s",
        current_user.id,
        session_id,
        len(data.content),
        data.mode or "auto",
    )
    # Verify session belongs to user
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Fetch conversation history
    chat_history = await _get_chat_history(db, session_id)

    # Save user message
    user_message = ChatMessage(session_id=session_id, role="user", content=data.content)
    db.add(user_message)
    await db.flush()

    user_msg_data = ChatMessageResponse.model_validate(user_message).model_dump()
    user_msg_data["created_at"] = user_msg_data["created_at"].isoformat()

    # Update session title on first message
    result = await db.execute(select(ChatMessage).where(ChatMessage.session_id == session_id))
    message_count = len(result.scalars().all())
    if message_count == 1 and session.title == "New Chat":
        session.title = data.content[:50] + ("..." if len(data.content) > 50 else "")
    await db.commit()

    async def event_generator():
        """Yield SSE events: user_message, then streamed text chunks, then done."""
        # Send the saved user message first
        yield f"data: {json.dumps({'type': 'user_message', 'data': user_msg_data})}\n\n"

        # Stream the assistant response
        full_response = ""
        sources_payload = None

        async for item in generate_rag_response_stream(
            user_id=current_user.id,
            question=data.content,
            chat_history=chat_history,
            mode=data.mode,
        ):
            if isinstance(item, dict):
                if item.get("type") == "sources":
                    sources_payload = item["data"]
                    continue
                elif item.get("type") == "mode":
                    yield f"data: [MODE] {json.dumps({'mode': item['data']})}\n\n"
                    continue
                elif item.get("type") == "status":
                    yield f"data: {json.dumps(item)}\n\n"
                    continue

            full_response += item
            yield f"data: {json.dumps({'type': 'chunk', 'data': item})}\n\n"
            
        # Emit the special sources event as completely finished streaming text
        if sources_payload:
            logger.info(
                "Streaming sources ready | user_id=%s | session_id=%s | source_count=%s",
                current_user.id,
                session_id,
                len(sources_payload),
            )
            yield f"data: [SOURCES] {json.dumps({'sources': sources_payload})}\n\n"

        # Save the complete assistant message to DB
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as save_db:
            assistant_message = ChatMessage(
                session_id=session_id, role="assistant", content=full_response
            )
            save_db.add(assistant_message)
            await save_db.commit()
            await save_db.refresh(assistant_message)

            assistant_msg_data = ChatMessageResponse.model_validate(assistant_message).model_dump()
            assistant_msg_data["created_at"] = assistant_msg_data["created_at"].isoformat()
            logger.info(
                "Completed streaming response | user_id=%s | session_id=%s | answer_chars=%s",
                current_user.id,
                session_id,
                len(full_response),
            )

        yield f"data: {json.dumps({'type': 'done', 'data': assistant_msg_data})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/rl/query", response_model=RLQueryResponse)
async def run_rl_query(
    data: RLQueryRequest,
    current_user: User = Depends(get_current_user),
):
    """Run Variant 3 with optional online Q-table updates for evaluation/training."""
    logger.info(
        "RL query request | user_id=%s | chars=%s | evaluation=%s",
        current_user.id,
        len(data.query),
        data.evaluation,
    )
    agent = QLearningAgent("qtable.json")
    if data.evaluation:
        agent.epsilon = 0.0

    started_at = time.perf_counter()
    state = await build_state(current_user.id, data.query)
    action_id = agent.select_action(state)
    config = action_config(action_id)
    logger.info(
        "RL selected action | user_id=%s | state=%s | action_id=%s | top_k=%s | reranker=%s",
        current_user.id,
        state,
        action_id,
        config["top_k"],
        config["use_reranker"],
    )
    chunks = await retrieve_chunks(current_user.id, data.query, config["top_k"], config["use_reranker"])
    final_chunks, sources = await build_sources_with_db(chunks[: config["top_k"]])

    if final_chunks:
        prompt = build_rag_prompt(data.query, final_chunks, chat_history=None, mode="summary")
        response = await get_async_client().chat(
            model=settings.OLLAMA_LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        answer = response["message"]["content"].strip()
    else:
        answer = "Sorry, please ask only questions related to your uploaded documents only."

    latency = time.perf_counter() - started_at
    reward_parts = await compute_reward(
        expected_doc_ids=data.expected_doc_ids,
        retrieved_chunks=final_chunks,
        generated_answer=answer,
        expected_answer=data.expected_answer,
        response_time_seconds=latency,
    )

    if not data.evaluation:
        agent.update(state, action_id, reward_parts["reward"])
        agent.decay_epsilon()
        agent.save()
        logger.info(
            "RL qtable updated | user_id=%s | action_id=%s | reward=%.4f | epsilon=%.4f",
            current_user.id,
            action_id,
            reward_parts["reward"],
            agent.epsilon,
        )

    retrieved_doc_ids: list[str] = []
    for chunk in final_chunks:
        doc_id = str(
            chunk.get("doc_id") or chunk.get("document_id") or ""
        ).strip()
        if doc_id and doc_id not in retrieved_doc_ids:
            retrieved_doc_ids.append(doc_id)
    logger.info(
        "RL query completed | user_id=%s | action_id=%s | hits=%s | reward=%.4f | elapsed=%.3fs",
        current_user.id,
        action_id,
        len(retrieved_doc_ids),
        reward_parts["reward"],
        time.perf_counter() - started_at,
    )

    return RLQueryResponse(
        state=state,
        action_id=action_id,
        top_k=config["top_k"],
        reranker=config["use_reranker"],
        answer=answer,
        response_latency_seconds=latency,
        retrieved_doc_ids=retrieved_doc_ids,
        sources=sources,
        **reward_parts,
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a chat session and all its messages."""
    logger.info("Delete session request | user_id=%s | session_id=%s", current_user.id, session_id)
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    await db.delete(session)
    logger.info("Deleted chat session | user_id=%s | session_id=%s", current_user.id, session_id)
