"""FastAPI application entry point with CORS, rate limiting, and lifespan."""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.config import get_settings
from app.database import init_db
from app.routers import auth_router, document_router, chat_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle events."""
    logger.info("Starting RAG Chatbot API...")
    # Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    # Initialize database tables
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

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router.router, prefix="/api")
app.include_router(document_router.router, prefix="/api")
app.include_router(chat_router.router, prefix="/api")


@app.get("/api/health")
async def health_check():
    """Health check endpoint — verifies database and vector DB connectivity."""
    health = {"status": "healthy", "service": "Multi-RAG Chatbot API", "checks": {}}

    # Check PostgreSQL
    try:
        from app.database import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        health["checks"]["postgresql"] = "connected"
    except Exception as e:
        health["checks"]["postgresql"] = f"error: {str(e)[:100]}"
        health["status"] = "unhealthy"

    # Check Milvus
    try:
        from pymilvus import connections
        connections.connect(alias="health_check", host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)
        connections.disconnect("health_check")
        health["checks"]["milvus"] = "connected"
    except Exception as e:
        health["checks"]["milvus"] = f"error: {str(e)[:100]}"
        health["status"] = "unhealthy"

    if health["status"] == "unhealthy":
        from fastapi.responses import JSONResponse
        return JSONResponse(content=health, status_code=503)

    return health
