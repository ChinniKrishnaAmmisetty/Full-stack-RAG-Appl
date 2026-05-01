from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE_PATH = (BASE_DIR / "data" / "rag_chatbot.db").resolve()
_env_path = BASE_DIR / "environment" / ".env"
load_dotenv(_env_path, override=True)


def _resolve_path(value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str((BASE_DIR / path).resolve())


def _resolve_database_url(value: str) -> str:
    for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
        if value.startswith(prefix):
            db_path = Path(value[len(prefix):])
            if not db_path.is_absolute():
                db_path = (BASE_DIR / db_path).resolve()
            return f"{prefix}{db_path.as_posix()}"
    return value


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = f"sqlite+aiosqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"

    # JWT
    SECRET_KEY: str = "change-this-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Ollama
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_LLM_MODEL: str = "qwen2.5:1.5b"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_REQUEST_TIMEOUT: int = 300
    OLLAMA_EMBED_BATCH_SIZE: int = 4

    # Uploads
    UPLOAD_DIR: str = "./uploads"

    # Rate limiting
    RATE_LIMIT: str = "100/minute"

    # RAG settings
    CHUNK_SIZE: int = 256
    CHUNK_OVERLAP: int = 40
    TOP_K_RESULTS: int = 5
    CANDIDATE_TOP_K: int = 20
    VECTOR_WEIGHT: float = 0.65
    KEYWORD_WEIGHT: float = 0.35

    model_config = {"env_file": str(_env_path), "extra": "ignore"}

    @property
    def resolved_database_url(self) -> str:
        return _resolve_database_url(self.DATABASE_URL)

    @property
    def resolved_upload_dir(self) -> str:
        return _resolve_path(self.UPLOAD_DIR)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
