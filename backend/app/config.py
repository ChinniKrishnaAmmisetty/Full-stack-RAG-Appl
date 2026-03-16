"""Application configuration loaded from environment variables."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent / "environment" / ".env"
load_dotenv(_env_path, override=True)


class Settings(BaseSettings):
    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "rag_db"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "root"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # JWT
    SECRET_KEY: str = "change-this-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Gemini API
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-pro-preview"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"

    # Google Auth
    GOOGLE_CLIENT_ID: str = ""

    # Milvus Vector Database
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530

    # Uploads
    UPLOAD_DIR: str = "./uploads"

    # Rate limiting
    RATE_LIMIT: str = "100/minute"

    # RAG settings
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    TOP_K_RESULTS: int = 5

    model_config = {"env_file": str(_env_path), "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
