"""Document upload, listing, and deletion endpoints."""

import os
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User, Document
from app.schemas import DocumentResponse
from app.auth import get_current_user
from app.config import get_settings
from app.services.document_service import extract_text_from_file, split_text_into_chunks
from app.services.embedding_service import generate_embeddings
from app.services.vector_service import add_document_chunks, delete_document_chunks

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _get_file_extension(filename: str) -> str:
    """Extract and validate the file extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext


async def _process_document(
    document_id: str,
    user_id: str,
    file_path: str,
    file_type: str,
    db_url: str,
):
    """Background task to extract, chunk, embed, and store document vectors."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession as AS
    from app.models import Document

    engine = create_async_engine(db_url)
    SessionLocal = async_sessionmaker(bind=engine, class_=AS, expire_on_commit=False)

    try:
        # 1. Extract text
        logger.info(f"Extracting text from {file_path}")
        text = extract_text_from_file(file_path, file_type)

        if not text.strip():
            raise ValueError("No text content could be extracted from the file")

        # 2. Split into chunks
        chunks = split_text_into_chunks(
            text,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        logger.info(f"Split into {len(chunks)} chunks")

        if not chunks:
            raise ValueError("No chunks produced from the extracted text")

        # 3. Generate embeddings
        embeddings = generate_embeddings(chunks)
        logger.info(f"Generated {len(embeddings)} embeddings")

        # 4. Store in vector database
        add_document_chunks(
            user_id=user_id,
            document_id=document_id,
            chunks=chunks,
            embeddings=embeddings,
        )

        # 5. Update document status
        async with SessionLocal() as session:
            result = await session.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = "ready"
                doc.chunk_count = len(chunks)
                await session.commit()

        logger.info(f"Document {document_id} processed successfully")

    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}", exc_info=True)
        async with SessionLocal() as session:
            result = await session.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = "failed"
                await session.commit()
    finally:
        await engine.dispose()
        # Clean up the uploaded file
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a document (PDF, DOCX, or TXT) for RAG processing."""
    # Validate file extension
    file_ext = _get_file_extension(file.filename or "")
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file content
    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)} MB",
        )

    if file_size == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    # Save file to disk temporarily
    upload_dir = os.path.join(settings.UPLOAD_DIR, current_user.id)
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, f"{file.filename}")
    with open(file_path, "wb") as f:
        f.write(content)

    # Create document record
    document = Document(
        user_id=current_user.id,
        filename=file.filename or "unknown",
        file_type=file_ext,
        file_size=file_size,
        status="processing",
    )
    db.add(document)
    await db.flush()

    # Start background processing
    background_tasks.add_task(
        _process_document,
        document_id=document.id,
        user_id=current_user.id,
        file_path=file_path,
        file_type=file_ext,
        db_url=settings.DATABASE_URL,
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
    return result.scalars().all()


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a document and its associated vector embeddings."""
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == current_user.id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Delete vectors from ChromaDB
    delete_document_chunks(current_user.id, document_id)

    # Delete from database
    await db.delete(document)
