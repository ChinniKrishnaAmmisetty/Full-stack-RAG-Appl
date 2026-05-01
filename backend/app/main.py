"""FastAPI application entry point with CORS, rate limiting, and lifespan."""

import asyncio
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import select, text

from app.config import get_settings
from app.database import AsyncSessionLocal, init_db
from app.logging_utils import configure_logging
from app.models import DocumentChunk
from app.routers import auth_router, chat_router, document_router
from app.services.embedding_service import diagnose_embedding_model
from app.services.rag_service import diagnose_generation_model

logger = logging.getLogger(__name__)

settings = get_settings()
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle events."""
    configure_logging(logging.INFO)
    logger.info("Starting RAG Chatbot API...")
    logger.info(
        "Runtime config | upload_dir=%s | embedding_model=%s | llm_model=%s | ollama_base=%s",
        settings.resolved_upload_dir,
        settings.OLLAMA_EMBEDDING_MODEL,
        settings.OLLAMA_LLM_MODEL,
        settings.OLLAMA_BASE_URL,
    )
    os.makedirs(settings.resolved_upload_dir, exist_ok=True)
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down RAG Chatbot API...")


app = FastAPI(
    title="Multi-RAG Chatbot API",
    description="A production-grade RAG chatbot with user-isolated document knowledge bases",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/api")
app.include_router(document_router.router, prefix="/api")
app.include_router(chat_router.router, prefix="/api")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Emit one start log and one completion log for every HTTP request."""
    request_id = uuid.uuid4().hex[:8]
    started_at = time.perf_counter()
    client_host = request.client.host if request.client else "unknown"
    origin = request.headers.get("origin", "-")
    user_agent = request.headers.get("user-agent", "-")
    logger.info(
        "[req:%s] Started %s %s from %s | origin=%s | ua=%s",
        request_id,
        request.method,
        request.url.path,
        client_host,
        origin,
        user_agent[:120],
    )
    try:
        response = await call_next(request)
    except Exception:
        elapsed = time.perf_counter() - started_at
        logger.exception(
            "[req:%s] Failed %s %s after %.3fs",
            request_id,
            request.method,
            request.url.path,
            elapsed,
        )
        raise
    elapsed = time.perf_counter() - started_at
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "[req:%s] Completed %s %s -> %s in %.3fs",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response


@app.get("/api/health")
async def health_check():
    """Health check endpoint for the local database and vector store."""
    logger.info("Running /api/health checks")
    health = {"status": "healthy", "service": "Multi-RAG Chatbot API", "checks": {}}

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        health["checks"]["database"] = "connected"
    except Exception as exc:
        health["checks"]["database"] = f"error: {str(exc)[:100]}"
        health["status"] = "unhealthy"

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(select(DocumentChunk.id).limit(1))
        health["checks"]["vector_store"] = "ready"
    except Exception as exc:
        health["checks"]["vector_store"] = f"error: {str(exc)[:100]}"
        health["status"] = "unhealthy"

    if health["status"] == "unhealthy":
        return JSONResponse(content=health, status_code=503)

    return health


@app.get("/api/health/ollama")
async def ollama_health_check():
    """Diagnostic endpoint that checks Ollama generation and embedding access separately."""
    logger.info("Running /api/health/ollama checks")
    generation_check, embedding_check = await asyncio.gather(
        asyncio.to_thread(diagnose_generation_model),
        asyncio.to_thread(diagnose_embedding_model),
    )

    statuses = {generation_check["status"], embedding_check["status"]}
    overall_status = "healthy" if statuses == {"ok"} else "degraded"

    payload = {
        "status": overall_status,
        "service": "Ollama",
        "checks": {
            "generation": generation_check,
            "embedding": embedding_check,
        },
    }

    if overall_status != "healthy":
        return JSONResponse(content=payload, status_code=503)

    return payload
