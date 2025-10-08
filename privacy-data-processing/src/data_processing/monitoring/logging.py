"""Structured logging for data processing operations."""

import logging
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import orjson


class LogLevel(Enum):
    """Log levels."""

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class StructuredLogger:
    """Provides structured JSON logging for operations."""

    def __init__(
        self,
        name: str = "data_processing",
        log_file: str | Path | None = None,
        level: LogLevel = LogLevel.INFO,
        enable_console: bool = True,
    ):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level.value)
        self.logger.handlers.clear()

        # JSON formatter
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"logger": "%(name)s", "message": "%(message)s"}'
        )

        # Console handler
        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level.value)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        # File handler
        if log_file:
            log_file = Path(log_file)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(level.value)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def _log(
        self,
        level: LogLevel,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Log a structured message.

        Args:
            level: Log level
            message: Log message
            extra: Additional structured data
        """
        log_data = {
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if extra:
            log_data.update(extra)

        # Serialize to JSON
        log_message = orjson.dumps(log_data).decode()

        # Log at appropriate level
        self.logger.log(level.value, log_message)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self._log(LogLevel.INFO, message, kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._log(LogLevel.WARNING, message, kwargs)

    def error(self, message: str, error: Exception | None = None, **kwargs: Any) -> None:
        """Log error message."""
        extra = kwargs.copy()
        if error:
            extra["error_type"] = type(error).__name__
            extra["error_message"] = str(error)
        self._log(LogLevel.ERROR, message, extra)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message."""
        self._log(LogLevel.CRITICAL, message, kwargs)

    def log_operation_start(self, operation: str, **kwargs: Any) -> None:
        """Log the start of an operation."""
        self.info(f"Starting {operation}", operation=operation, status="started", **kwargs)

    def log_operation_complete(self, operation: str, duration_seconds: float, **kwargs: Any) -> None:
        """Log the completion of an operation."""
        self.info(
            f"Completed {operation}",
            operation=operation,
            status="completed",
            duration_seconds=duration_seconds,
            **kwargs,
        )

    def log_operation_failed(self, operation: str, error: Exception, **kwargs: Any) -> None:
        """Log a failed operation."""
        self.error(
            f"Failed {operation}", error=error, operation=operation, status="failed", **kwargs
        )
