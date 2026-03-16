"""Chat session and message endpoints with RAG integration (streaming + memory)."""

import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User, ChatSession, ChatMessage
from app.schemas import (
    ChatSessionCreate,
    ChatSessionResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatResponse,
)
from app.auth import get_current_user
from app.services.rag_service import generate_rag_response, generate_rag_response_stream

logger = logging.getLogger(__name__)

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
    return result.scalars().all()


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all messages in a chat session."""
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
    return result.scalars().all()


@router.post("/sessions/{session_id}/messages", response_model=ChatResponse)
async def send_message(
    session_id: str,
    data: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message and get a RAG-powered response (non-streaming)."""
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
    logger.info(f"Generating RAG response for user {current_user.id}")
    answer = await generate_rag_response(
        user_id=current_user.id,
        question=data.content,
        chat_history=chat_history,
    )

    # Save assistant message
    assistant_message = ChatMessage(session_id=session_id, role="assistant", content=answer)
    db.add(assistant_message)
    await db.flush()

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
        async for text_chunk in generate_rag_response_stream(
            user_id=current_user.id,
            question=data.content,
            chat_history=chat_history,
        ):
            full_response += text_chunk
            yield f"data: {json.dumps({'type': 'chunk', 'data': text_chunk})}\n\n"

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


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a chat session and all its messages."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    await db.delete(session)

