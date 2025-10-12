from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict
from logging.handlers import RotatingFileHandler

import structlog


def configure_logging(level: str = "INFO") -> None:
    # Create logs directory if it doesn't exist
    log_dir = Path(__file__).resolve().parents[2] / "logs"
    log_dir.mkdir(exist_ok=True)
    
    # Log file path
    log_file = log_dir / "backend.log"
    
    # Configure handlers
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level, logging.INFO))
    
    # File handler with rotation (max 10MB, keep 5 backup files)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, level, logging.INFO))
    
    # Configure logging with both handlers
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=getattr(logging, level, logging.INFO),
        handlers=[console_handler, file_handler]
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level, logging.INFO)),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured - Console: {level}, File: {log_file}")


def get_logger() -> structlog.stdlib.BoundLogger:
    return structlog.get_logger()


# Optional Langfuse integration
try:
    from langfuse import Langfuse
    from langfuse.decorators import observe as lf_observe  # re-exportable
except Exception:  # pragma: no cover
    Langfuse = None  # type: ignore
    lf_observe = None  # type: ignore

_langfuse_client: Any | None = None


def init_langfuse_if_configured(settings: Any) -> Any | None:
    global _langfuse_client
    if Langfuse is None:
        return None
    if _langfuse_client is not None:
        return _langfuse_client
    if not getattr(settings, "langfuse_public_key", None) or not getattr(settings, "langfuse_secret_key", None):
        return None
    _langfuse_client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host or os.getenv("LANGFUSE_HOST"),
    )
    return _langfuse_client


def log_custom_event(event: str, properties: Dict[str, Any] | None = None) -> None:
    client = _langfuse_client
    if client is None:
        return
    try:
        client.event(name=event, data=properties or {})
    except Exception:
        pass


def create_trace(name: str, input_data: Dict[str, Any], metadata: Dict[str, Any] | None = None):
    """Create a new Langfuse trace (generation) if client is configured and enabled.

    For the installed SDK version, we use start_generation / update_current_generation API.
    Returns True if started, else None.
    """
    try:
        from app.config import get_settings
        settings = get_settings()
        if not settings.langfuse_enabled:
            return None
    except Exception:
        # If settings import fails, be safe and do not emit
        return None

    client = _langfuse_client
    if client is None:
        try:
            logger = get_logger().bind(component="langfuse")
            logger.warning("Langfuse enabled but client is not initialized; skipping trace creation")
        except Exception:
            pass
        return None
    try:
        # Start a generation which acts as a trace for this request
        client.start_generation(
            name=name,
            input=input_data,
            metadata=metadata or {},
        )
        return True
    except Exception as e:
        # Surface why trace creation failed to logs for debugging
        try:
            logger = get_logger().bind(component="langfuse")
            logger.warning(f"Failed to create Langfuse trace '{name}': {e}")
        except Exception:
            pass
        return None


def update_generation_output(output: Dict[str, Any]) -> None:
    """Update the current generation with output payload, if client available."""
    client = _langfuse_client
    if client is None:
        return
    try:
        client.update_current_generation(output=output)
    except Exception:
        pass


def flush_langfuse() -> None:
    """Flush pending telemetry to Langfuse, if client available."""
    client = _langfuse_client
    if client is None:
        return
    try:
        client.flush()
    except Exception:
        pass


def maybe_observe():
    """Return a decorator that observes function execution if Langfuse is available.

    Usage:
        @maybe_observe()
        async def handler(...):
            ...
    """
    def identity(fn):
        return fn

    if lf_observe is None:
        return identity
    return lf_observe()
