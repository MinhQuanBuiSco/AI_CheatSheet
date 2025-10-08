"""Custom exceptions for data processing operations.

Anthropic-level error handling: explicit, actionable, context-rich.
"""

from typing import Any


class DataProcessingError(Exception):
    """Base exception for all data processing errors.

    All custom exceptions inherit from this to allow catching all
    application-specific errors with a single except clause.
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        context: dict[str, Any] | None = None,
        recoverable: bool = False,
    ):
        """Initialize error with rich context.

        Args:
            message: Human-readable error description
            error_code: Machine-readable error code (e.g., "STORAGE_001")
            context: Additional context for debugging
            recoverable: Whether the operation can be retried
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        self.recoverable = recoverable

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for structured logging."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "context": self.context,
            "recoverable": self.recoverable,
        }


# === Storage Errors ===


class StorageError(DataProcessingError):
    """Base class for storage-related errors."""

    pass


class FileNotFoundError(StorageError):
    """File or object not found in storage."""

    def __init__(self, path: str, storage_type: str = "unknown"):
        super().__init__(
            f"File not found: {path}",
            error_code="STORAGE_001",
            context={"path": path, "storage_type": storage_type},
            recoverable=False,
        )


class FileReadError(StorageError):
    """Error reading file from storage."""

    def __init__(self, path: str, reason: str):
        super().__init__(
            f"Failed to read file {path}: {reason}",
            error_code="STORAGE_002",
            context={"path": path, "reason": reason},
            recoverable=True,
        )


class FileWriteError(StorageError):
    """Error writing file to storage."""

    def __init__(self, path: str, reason: str):
        super().__init__(
            f"Failed to write file {path}: {reason}",
            error_code="STORAGE_003",
            context={"path": path, "reason": reason},
            recoverable=True,
        )


class S3ConnectionError(StorageError):
    """Error connecting to S3/MinIO."""

    def __init__(self, endpoint: str, reason: str):
        super().__init__(
            f"Failed to connect to S3 endpoint {endpoint}: {reason}",
            error_code="STORAGE_004",
            context={"endpoint": endpoint, "reason": reason},
            recoverable=True,
        )


# === Processing Errors ===


class ProcessingError(DataProcessingError):
    """Base class for data processing errors."""

    pass


class InvalidDataFormatError(ProcessingError):
    """Data format is invalid or unsupported."""

    def __init__(self, format_type: str, expected: str, actual: str):
        super().__init__(
            f"Invalid data format: expected {expected}, got {actual}",
            error_code="PROCESSING_001",
            context={"format_type": format_type, "expected": expected, "actual": actual},
            recoverable=False,
        )


class DataValidationError(ProcessingError):
    """Data failed validation checks."""

    def __init__(self, field: str, reason: str, value: Any = None):
        super().__init__(
            f"Validation failed for field '{field}': {reason}",
            error_code="PROCESSING_002",
            context={"field": field, "reason": reason, "value": str(value) if value else None},
            recoverable=False,
        )


class ProcessorError(ProcessingError):
    """Error in data processor."""

    def __init__(self, processor_name: str, reason: str, record_index: int | None = None):
        super().__init__(
            f"Processor '{processor_name}' failed: {reason}",
            error_code="PROCESSING_003",
            context={"processor": processor_name, "reason": reason, "record_index": record_index},
            recoverable=True,
        )


# === Privacy Errors ===


class PrivacyError(DataProcessingError):
    """Base class for privacy-related errors."""

    pass


class PIIDetectionError(PrivacyError):
    """Error detecting PII in data."""

    def __init__(self, reason: str, text_snippet: str | None = None):
        super().__init__(
            f"PII detection failed: {reason}",
            error_code="PRIVACY_001",
            context={"reason": reason, "text_length": len(text_snippet) if text_snippet else 0},
            recoverable=True,
        )


class AnonymizationError(PrivacyError):
    """Error anonymizing data."""

    def __init__(self, method: str, reason: str, entity_type: str | None = None):
        super().__init__(
            f"Anonymization failed using method '{method}': {reason}",
            error_code="PRIVACY_002",
            context={"method": method, "reason": reason, "entity_type": entity_type},
            recoverable=True,
        )


class EncryptionError(PrivacyError):
    """Error encrypting data."""

    def __init__(self, reason: str):
        super().__init__(
            f"Encryption failed: {reason}",
            error_code="PRIVACY_003",
            context={"reason": reason},
            recoverable=False,
        )


class AuditLogError(PrivacyError):
    """Error writing audit log."""

    def __init__(self, operation: str, reason: str):
        super().__init__(
            f"Failed to write audit log for operation '{operation}': {reason}",
            error_code="PRIVACY_004",
            context={"operation": operation, "reason": reason},
            recoverable=True,
        )


# === Distributed Computing Errors ===


class DistributedError(DataProcessingError):
    """Base class for distributed computing errors."""

    pass


class SparkConnectionError(DistributedError):
    """Error connecting to Spark cluster."""

    def __init__(self, master_url: str, reason: str):
        super().__init__(
            f"Failed to connect to Spark master {master_url}: {reason}",
            error_code="SPARK_001",
            context={"master_url": master_url, "reason": reason},
            recoverable=True,
        )


class SparkJobError(DistributedError):
    """Error executing Spark job."""

    def __init__(self, job_id: str, stage: str, reason: str):
        super().__init__(
            f"Spark job {job_id} failed at stage '{stage}': {reason}",
            error_code="SPARK_002",
            context={"job_id": job_id, "stage": stage, "reason": reason},
            recoverable=False,
        )


class SparkWorkerError(DistributedError):
    """Error with Spark worker."""

    def __init__(self, worker_id: str, reason: str):
        super().__init__(
            f"Spark worker {worker_id} error: {reason}",
            error_code="SPARK_003",
            context={"worker_id": worker_id, "reason": reason},
            recoverable=True,
        )


class SparkResourceError(DistributedError):
    """Insufficient resources for Spark operation."""

    def __init__(self, resource_type: str, requested: str, available: str):
        super().__init__(
            f"Insufficient {resource_type}: requested {requested}, available {available}",
            error_code="SPARK_004",
            context={
                "resource_type": resource_type,
                "requested": requested,
                "available": available,
            },
            recoverable=True,
        )


# === Configuration Errors ===


class ConfigurationError(DataProcessingError):
    """Base class for configuration errors."""

    pass


class InvalidConfigError(ConfigurationError):
    """Configuration is invalid."""

    def __init__(self, param_name: str, reason: str, value: Any = None):
        super().__init__(
            f"Invalid configuration for '{param_name}': {reason}",
            error_code="CONFIG_001",
            context={
                "param_name": param_name,
                "reason": reason,
                "value": str(value) if value else None,
            },
            recoverable=False,
        )


class MissingConfigError(ConfigurationError):
    """Required configuration is missing."""

    def __init__(self, param_name: str, context_info: str | None = None):
        super().__init__(
            f"Missing required configuration: {param_name}"
            + (f" ({context_info})" if context_info else ""),
            error_code="CONFIG_002",
            context={"param_name": param_name, "context_info": context_info},
            recoverable=False,
        )


# === Resource Errors ===


class ResourceError(DataProcessingError):
    """Base class for resource-related errors."""

    pass


class OutOfMemoryError(ResourceError):
    """Insufficient memory for operation."""

    def __init__(self, operation: str, required_mb: int, available_mb: int):
        super().__init__(
            f"Out of memory during {operation}: required {required_mb}MB, available {available_mb}MB",
            error_code="RESOURCE_001",
            context={
                "operation": operation,
                "required_mb": required_mb,
                "available_mb": available_mb,
            },
            recoverable=False,
        )


class TimeoutError(ResourceError):
    """Operation timed out."""

    def __init__(self, operation: str, timeout_seconds: int):
        super().__init__(
            f"Operation '{operation}' timed out after {timeout_seconds}s",
            error_code="RESOURCE_002",
            context={"operation": operation, "timeout_seconds": timeout_seconds},
            recoverable=True,
        )


# === API Errors ===


class APIError(DataProcessingError):
    """Base class for API errors."""

    pass


class InvalidRequestError(APIError):
    """API request is invalid."""

    def __init__(self, reason: str, field: str | None = None):
        super().__init__(
            f"Invalid request: {reason}",
            error_code="API_001",
            context={"reason": reason, "field": field},
            recoverable=False,
        )


class JobNotFoundError(APIError):
    """Requested job not found."""

    def __init__(self, job_id: str):
        super().__init__(
            f"Job not found: {job_id}",
            error_code="API_002",
            context={"job_id": job_id},
            recoverable=False,
        )


class RateLimitError(APIError):
    """Rate limit exceeded."""

    def __init__(self, limit: int, window_seconds: int):
        super().__init__(
            f"Rate limit exceeded: {limit} requests per {window_seconds}s",
            error_code="API_003",
            context={"limit": limit, "window_seconds": window_seconds},
            recoverable=True,
        )
