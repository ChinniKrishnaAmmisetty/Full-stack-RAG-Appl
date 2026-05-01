"""Shared logging configuration for API and CLI entrypoints."""

import logging
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(level: int | str = logging.INFO) -> None:
    """Configure root logging explicitly so app logs are always visible."""
    resolved_level = getattr(logging, str(level).upper(), logging.INFO) if isinstance(level, str) else level
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
        root_logger.addHandler(handler)
    root_logger.setLevel(resolved_level)
    logging.getLogger("app").setLevel(resolved_level)
    for logger_name in ("uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.disabled = False
        uvicorn_logger.setLevel(resolved_level)
    logging.captureWarnings(True)
