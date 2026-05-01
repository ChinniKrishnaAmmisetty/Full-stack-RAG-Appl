"""Document upload, listing, and deletion endpoints."""

import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import Document, User
from app.schemas import DocumentResponse
from app.services.document_service import (
    extract_text_from_file,
    split_text_into_chunks,
    validate_file_content,
)
from app.services.embedding_service import generate_embeddings_async
from app.services.ollama_service import OllamaServiceError
from app.services.vector_service import add_document_chunks, delete_document_chunks

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "csv", "xlsx", "md"}
MAX_FILE_SIZE = 50 * 1024 * 1024


def _get_file_extension(filename: str) -> str:
    """Extract and validate the file extension."""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


async def _process_document(
    document_id: str,
    user_id: str,
    file_path: str,
    file_type: str,
):
    """Background task to extract, chunk, embed, and store document vectors."""
    from app.database import AsyncSessionLocal
    from app.models import Document

    async def mark_document_failed(message: str):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = "failed"
                doc.error_message = message[:500]
                await session.commit()

    try:
        logger.info(
            "Starting document processing | document_id=%s | user_id=%s | file_type=%s | path=%s",
            document_id,
            user_id,
            file_type,
            file_path,
        )
        if not validate_file_content(file_path, file_type):
            raise ValueError(
                f"File content does not match the claimed type '{file_type}'. "
                "File may be corrupted or misnamed."
            )

        logger.info("Extracting text from %s", file_path)
        text = extract_text_from_file(file_path, file_type)

        if not text.strip():
            raise ValueError("No text content could be extracted from the file")

        chunks = split_text_into_chunks(
            text,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        logger.info("Split into %s chunks", len(chunks))

        if not chunks:
            raise ValueError("No chunks produced from the extracted text")

        embeddings = await generate_embeddings_async(chunks)
        logger.info("Generated %s embeddings", len(embeddings))

        await add_document_chunks(
            user_id=user_id,
            document_id=document_id,
            chunks=chunks,
            embeddings=embeddings,
        )

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = "ready"
                doc.chunk_count = len(chunks)
                await session.commit()

        logger.info("Document %s processed successfully", document_id)

    except OllamaServiceError as exc:
        logger.warning("Document %s processing stopped: %s", document_id, exc)
        await mark_document_failed(exc.user_message)
    except Exception as exc:
        logger.error("Error processing document %s: %s", document_id, exc, exc_info=True)
        await mark_document_failed(str(exc))
    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info("Removed temporary upload file for document %s", document_id)
        except Exception:
            pass


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a document for RAG processing."""
    logger.info(
        "Upload request received | user_id=%s | filename=%s",
        current_user.id,
        file.filename or "unknown",
    )
    file_ext = _get_file_extension(file.filename or "")
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)} MB",
        )

    if file_size == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    logger.info(
        "Validated upload | user_id=%s | filename=%s | file_type=%s | size_bytes=%s",
        current_user.id,
        file.filename or "unknown",
        file_ext,
        file_size,
    )

    upload_dir = os.path.join(settings.resolved_upload_dir, current_user.id)
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, file.filename or "upload.bin")
    with open(file_path, "wb") as saved_file:
        saved_file.write(content)

    document = Document(
        user_id=current_user.id,
        filename=file.filename or "unknown",
        file_type=file_ext,
        file_size=file_size,
        status="processing",
    )
    db.add(document)
    await db.flush()

    background_tasks.add_task(
        _process_document,
        document_id=document.id,
        user_id=current_user.id,
        file_path=file_path,
        file_type=file_ext,
    )
    logger.info(
        "Queued background processing | document_id=%s | user_id=%s | filename=%s",
        document.id,
        current_user.id,
        document.filename,
    )

    return document


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all documents for the current user."""
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    documents = result.scalars().all()
    logger.info("Listed %s documents for user %s", len(documents), current_user.id)
    return documents


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a document and its associated indexed chunks."""
    logger.info("Delete document request | user_id=%s | document_id=%s", current_user.id, document_id)
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == current_user.id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    await delete_document_chunks(current_user.id, document_id)
    await db.delete(document)
    logger.info("Deleted document metadata | user_id=%s | document_id=%s", current_user.id, document_id)
