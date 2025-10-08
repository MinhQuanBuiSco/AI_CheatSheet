"""Structured logging configuration for Anthropic-level observability.

Features:
- JSON formatting for production
- Correlation IDs for distributed tracing
- Contextual fields (job_id, worker_id, etc.)
- Integration with monitoring/metrics
"""
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Optional
import json


# Context variables for request tracing
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
job_id_var: ContextVar[Optional[str]] = ContextVar("job_id", default=None)
worker_id_var: ContextVar[Optional[str]] = ContextVar("worker_id", default=None)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Base fields
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation IDs if available
        if correlation_id := correlation_id_var.get():
            log_data["correlation_id"] = correlation_id
        if job_id := job_id_var.get():
            log_data["job_id"] = job_id
        if worker_id := worker_id_var.get():
            log_data["worker_id"] = worker_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Add custom fields from extra
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


class HumanReadableFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    # Color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record for human reading."""
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]

        # Build message
        parts = [
            f"{color}{record.levelname}{reset}",
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        ]

        # Add context if available
        if correlation_id := correlation_id_var.get():
            parts.append(f"[{correlation_id[:8]}]")
        if job_id := job_id_var.get():
            parts.append(f"[job:{job_id[:8]}]")
        if worker_id := worker_id_var.get():
            parts.append(f"[worker:{worker_id}]")

        # Add location
        parts.append(f"{record.name}:{record.lineno}")

        # Add message
        parts.append("-")
        parts.append(record.getMessage())

        message = " ".join(parts)

        # Add exception if present
        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)

        return message


def setup_logging(
    *,
    level: str = "INFO",
    format_type: str = "json",  # "json" or "human"
    enable_correlation: bool = True,
) -> logging.Logger:
    """Setup structured logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: "json" for production, "human" for development
        enable_correlation: Enable correlation ID tracking

    Returns:
        Configured root logger
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers = []

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    # Set formatter
    if format_type == "json":
        formatter = StructuredFormatter()
    else:
        formatter = HumanReadableFormatter()

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that adds extra context to all log messages."""

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Add extra fields to log message."""
        # Get existing extra or create new
        extra = kwargs.get("extra", {})

        # Add correlation IDs
        if correlation_id := correlation_id_var.get():
            extra["correlation_id"] = correlation_id
        if job_id := job_id_var.get():
            extra["job_id"] = job_id
        if worker_id := worker_id_var.get():
            extra["worker_id"] = worker_id

        # Merge with any extra_fields
        if hasattr(self, "extra_fields"):
            extra.update(self.extra_fields)

        kwargs["extra"] = {"extra_fields": extra}
        return msg, kwargs


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Set correlation ID for current context.

    Args:
        correlation_id: ID to set, or None to generate new UUID

    Returns:
        The correlation ID that was set
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    correlation_id_var.set(correlation_id)
    return correlation_id


def set_job_id(job_id: str) -> None:
    """Set job ID for current context."""
    job_id_var.set(job_id)


def set_worker_id(worker_id: str) -> None:
    """Set worker ID for current context."""
    worker_id_var.set(worker_id)


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return correlation_id_var.get()


def get_job_id() -> Optional[str]:
    """Get current job ID."""
    return job_id_var.get()


def get_worker_id() -> Optional[str]:
    """Get current worker ID."""
    return worker_id_var.get()


def log_exception(logger: logging.Logger, exc: Exception, **context: Any) -> None:
    """Log exception with structured context.

    Args:
        logger: Logger instance
        exc: Exception to log
        **context: Additional context fields
    """
    from .exceptions import DataProcessingError

    if isinstance(exc, DataProcessingError):
        # Use rich error context
        error_dict = exc.to_dict()
        error_dict.update(context)
        logger.error(
            f"{exc.__class__.__name__}: {exc.message}",
            extra={"extra_fields": error_dict},
            exc_info=True,
        )
    else:
        # Standard exception
        logger.error(
            f"{exc.__class__.__name__}: {str(exc)}",
            extra={"extra_fields": context},
            exc_info=True,
        )


# Initialize default logging
_default_logger = setup_logging(
    level="INFO",
    format_type="human",  # Use "json" in production
)
