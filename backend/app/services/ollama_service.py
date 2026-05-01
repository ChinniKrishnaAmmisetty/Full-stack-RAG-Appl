"""Shared Ollama client helpers and normalized error handling."""

import httpx
from ollama import AsyncClient, Client, ResponseError

from app.config import get_settings

settings = get_settings()


class OllamaServiceError(RuntimeError):
    """Base Ollama error with a frontend-safe message."""

    def __init__(self, message: str, user_message: str, status: str = "unavailable"):
        super().__init__(message)
        self.user_message = user_message
        self.status = status


class OllamaConnectionError(OllamaServiceError):
    """Raised when the local Ollama server cannot be reached."""


class OllamaModelNotFoundError(OllamaServiceError):
    """Raised when the requested local model has not been pulled yet."""


class OllamaTemporaryError(OllamaServiceError):
    """Raised for retryable Ollama failures."""


def get_sync_client() -> Client:
    """Create a sync Ollama client."""
    return Client(host=settings.OLLAMA_BASE_URL, timeout=settings.OLLAMA_REQUEST_TIMEOUT)


def get_async_client() -> AsyncClient:
    """Create an async Ollama client."""
    return AsyncClient(host=settings.OLLAMA_BASE_URL, timeout=settings.OLLAMA_REQUEST_TIMEOUT)


def normalize_ollama_exception(exc: Exception, model_name: str, task_type: str) -> OllamaServiceError:
    """Convert raw Ollama/httpx exceptions into app-specific errors."""
    if isinstance(exc, OllamaServiceError):
        return exc

    if isinstance(exc, ResponseError):
        error_text = getattr(exc, "error", str(exc))
        if exc.status_code == 404:
            return OllamaModelNotFoundError(
                f"Ollama model not found: {model_name}",
                (
                    f"Ollama model `{model_name}` is not available locally. "
                    f"Run `ollama pull {model_name}` and try again."
                ),
                status="model_not_found",
            )

        if exc.status_code in {408, 429, 500, 502, 503, 504}:
            return OllamaTemporaryError(
                f"Ollama temporary failure during {task_type}: {error_text}",
                "Ollama is busy or temporarily unavailable. Please try again shortly.",
                status="temporary_failure",
            )

        return OllamaServiceError(
            f"Ollama error during {task_type}: {error_text}",
            f"Ollama returned an error during {task_type}. Please check the local server logs.",
        )

    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return OllamaConnectionError(
            f"Ollama connection failed during {task_type}: {exc}",
            (
                f"Could not connect to Ollama at `{settings.OLLAMA_BASE_URL}`. "
                "Make sure Ollama is installed and running."
            ),
            status="not_running",
        )

    if isinstance(
        exc,
        (httpx.ReadTimeout, httpx.RemoteProtocolError, httpx.WriteError, httpx.ReadError),
    ):
        return OllamaTemporaryError(
            f"Ollama timed out during {task_type}: {exc}",
            "Ollama took too long to respond. Please try again.",
            status="temporary_failure",
        )

    return OllamaServiceError(
        f"Unexpected Ollama error during {task_type}: {exc}",
        "Ollama is currently unavailable. Please try again later.",
    )
