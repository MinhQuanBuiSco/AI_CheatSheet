"""Comprehensive tests for custom exceptions module."""
import pytest

from data_processing.exceptions import (
    # Base
    DataProcessingError,
    # Storage
    StorageError,
    FileNotFoundError,
    FileReadError,
    FileWriteError,
    S3ConnectionError,
    # Processing
    ProcessingError,
    InvalidDataFormatError,
    DataValidationError,
    ProcessorError,
    # Privacy
    PrivacyError,
    PIIDetectionError,
    AnonymizationError,
    EncryptionError,
    AuditLogError,
    # Distributed
    DistributedError,
    SparkConnectionError,
    SparkJobError,
    SparkWorkerError,
    SparkResourceError,
    # Configuration
    ConfigurationError,
    InvalidConfigError,
    MissingConfigError,
    # Resource
    ResourceError,
    OutOfMemoryError,
    TimeoutError,
    # API
    APIError,
    InvalidRequestError,
    JobNotFoundError,
    RateLimitError,
)


class TestBaseException:
    """Tests for DataProcessingError base class."""

    def test_base_exception_creation(self):
        """Test creating base exception with minimal args."""
        error = DataProcessingError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.error_code is None
        assert error.context == {}
        assert error.recoverable is False

    def test_base_exception_with_all_args(self):
        """Test creating exception with all arguments."""
        error = DataProcessingError(
            "Test error",
            error_code="TEST_001",
            context={"key": "value", "count": 42},
            recoverable=True,
        )
        assert error.message == "Test error"
        assert error.error_code == "TEST_001"
        assert error.context == {"key": "value", "count": 42}
        assert error.recoverable is True

    def test_to_dict_serialization(self):
        """Test exception serialization to dictionary."""
        error = DataProcessingError(
            "Serialization test",
            error_code="SER_001",
            context={"file": "test.txt", "line": 42},
            recoverable=True,
        )
        error_dict = error.to_dict()

        assert error_dict["error_type"] == "DataProcessingError"
        assert error_dict["message"] == "Serialization test"
        assert error_dict["error_code"] == "SER_001"
        assert error_dict["context"]["file"] == "test.txt"
        assert error_dict["context"]["line"] == 42
        assert error_dict["recoverable"] is True


class TestStorageExceptions:
    """Tests for storage-related exceptions."""

    def test_file_not_found_error(self):
        """Test FileNotFoundError."""
        error = FileNotFoundError("/path/to/file.txt", storage_type="s3")
        assert "File not found: /path/to/file.txt" in str(error)
        assert error.error_code == "STORAGE_001"
        assert error.context["path"] == "/path/to/file.txt"
        assert error.context["storage_type"] == "s3"
        assert error.recoverable is False

    def test_file_read_error(self):
        """Test FileReadError."""
        error = FileReadError("/data/input.csv", "Permission denied")
        assert "Failed to read file" in str(error)
        assert error.error_code == "STORAGE_002"
        assert error.context["path"] == "/data/input.csv"
        assert error.context["reason"] == "Permission denied"
        assert error.recoverable is True

    def test_file_write_error(self):
        """Test FileWriteError."""
        error = FileWriteError("/output/result.parquet", "Disk full")
        assert "Failed to write file" in str(error)
        assert error.error_code == "STORAGE_003"
        assert error.recoverable is True

    def test_s3_connection_error(self):
        """Test S3ConnectionError."""
        error = S3ConnectionError("s3.amazonaws.com", "Connection timeout")
        assert "Failed to connect to S3 endpoint" in str(error)
        assert error.error_code == "STORAGE_004"
        assert error.context["endpoint"] == "s3.amazonaws.com"
        assert error.recoverable is True


class TestProcessingExceptions:
    """Tests for data processing exceptions."""

    def test_invalid_data_format_error(self):
        """Test InvalidDataFormatError."""
        error = InvalidDataFormatError("parquet", "parquet", "csv")
        assert "Invalid data format" in str(error)
        assert error.error_code == "PROCESSING_001"
        assert error.context["format_type"] == "parquet"
        assert error.context["expected"] == "parquet"
        assert error.context["actual"] == "csv"
        assert error.recoverable is False

    def test_data_validation_error(self):
        """Test DataValidationError."""
        error = DataValidationError("email", "Invalid format", "not-an-email")
        assert "Validation failed for field 'email'" in str(error)
        assert error.error_code == "PROCESSING_002"
        assert error.context["field"] == "email"
        assert error.context["reason"] == "Invalid format"
        assert error.context["value"] == "not-an-email"
        assert error.recoverable is False

    def test_processor_error(self):
        """Test ProcessorError."""
        error = ProcessorError("text_cleaner", "Regex compilation failed", record_index=42)
        assert "Processor 'text_cleaner' failed" in str(error)
        assert error.error_code == "PROCESSING_003"
        assert error.context["processor"] == "text_cleaner"
        assert error.context["record_index"] == 42
        assert error.recoverable is True


class TestPrivacyExceptions:
    """Tests for privacy-related exceptions."""

    def test_pii_detection_error(self):
        """Test PIIDetectionError."""
        error = PIIDetectionError("Model not loaded", text_snippet="Sample text here")
        assert "PII detection failed" in str(error)
        assert error.error_code == "PRIVACY_001"
        assert error.context["text_length"] == len("Sample text here")
        assert error.recoverable is True

    def test_anonymization_error(self):
        """Test AnonymizationError."""
        error = AnonymizationError("hash", "Invalid hash algorithm", entity_type="email")
        assert "Anonymization failed using method 'hash'" in str(error)
        assert error.error_code == "PRIVACY_002"
        assert error.context["method"] == "hash"
        assert error.context["entity_type"] == "email"
        assert error.recoverable is True

    def test_encryption_error(self):
        """Test EncryptionError."""
        error = EncryptionError("Key not found")
        assert "Encryption failed" in str(error)
        assert error.error_code == "PRIVACY_003"
        assert error.recoverable is False

    def test_audit_log_error(self):
        """Test AuditLogError."""
        error = AuditLogError("data_access", "Write failed")
        assert "Failed to write audit log for operation 'data_access'" in str(error)
        assert error.error_code == "PRIVACY_004"
        assert error.recoverable is True


class TestDistributedExceptions:
    """Tests for distributed computing exceptions."""

    def test_spark_connection_error(self):
        """Test SparkConnectionError."""
        error = SparkConnectionError("spark://master:7077", "Timeout")
        assert "Failed to connect to Spark master" in str(error)
        assert error.error_code == "SPARK_001"
        assert error.context["master_url"] == "spark://master:7077"
        assert error.recoverable is True

    def test_spark_job_error(self):
        """Test SparkJobError."""
        error = SparkJobError("job_123", "map", "Out of memory")
        assert "Spark job job_123 failed at stage 'map'" in str(error)
        assert error.error_code == "SPARK_002"
        assert error.context["job_id"] == "job_123"
        assert error.context["stage"] == "map"
        assert error.recoverable is False

    def test_spark_worker_error(self):
        """Test SparkWorkerError."""
        error = SparkWorkerError("worker-01", "Lost connection")
        assert "Spark worker worker-01 error" in str(error)
        assert error.error_code == "SPARK_003"
        assert error.recoverable is True

    def test_spark_resource_error(self):
        """Test SparkResourceError."""
        error = SparkResourceError("memory", "8GB", "4GB")
        assert "Insufficient memory: requested 8GB, available 4GB" in str(error)
        assert error.error_code == "SPARK_004"
        assert error.context["resource_type"] == "memory"
        assert error.recoverable is True


class TestConfigurationExceptions:
    """Tests for configuration exceptions."""

    def test_invalid_config_error(self):
        """Test InvalidConfigError."""
        error = InvalidConfigError("batch_size", "Must be positive", value=-10)
        assert "Invalid configuration for 'batch_size'" in str(error)
        assert error.error_code == "CONFIG_001"
        assert error.context["param_name"] == "batch_size"
        assert error.context["value"] == "-10"
        assert error.recoverable is False

    def test_missing_config_error(self):
        """Test MissingConfigError."""
        error = MissingConfigError("api_key", context_info="Required for authentication")
        assert "Missing required configuration: api_key" in str(error)
        assert "Required for authentication" in str(error)
        assert error.error_code == "CONFIG_002"
        assert error.recoverable is False


class TestResourceExceptions:
    """Tests for resource-related exceptions."""

    def test_out_of_memory_error(self):
        """Test OutOfMemoryError."""
        error = OutOfMemoryError("large_sort", required_mb=8192, available_mb=4096)
        assert "Out of memory during large_sort" in str(error)
        assert "required 8192MB, available 4096MB" in str(error)
        assert error.error_code == "RESOURCE_001"
        assert error.recoverable is False

    def test_timeout_error(self):
        """Test TimeoutError."""
        error = TimeoutError("database_query", timeout_seconds=30)
        assert "Operation 'database_query' timed out after 30s" in str(error)
        assert error.error_code == "RESOURCE_002"
        assert error.recoverable is True


class TestAPIExceptions:
    """Tests for API-related exceptions."""

    def test_invalid_request_error(self):
        """Test InvalidRequestError."""
        error = InvalidRequestError("Missing required field", field="input_path")
        assert "Invalid request: Missing required field" in str(error)
        assert error.error_code == "API_001"
        assert error.context["field"] == "input_path"
        assert error.recoverable is False

    def test_job_not_found_error(self):
        """Test JobNotFoundError."""
        error = JobNotFoundError("job-12345")
        assert "Job not found: job-12345" in str(error)
        assert error.error_code == "API_002"
        assert error.context["job_id"] == "job-12345"
        assert error.recoverable is False

    def test_rate_limit_error(self):
        """Test RateLimitError."""
        error = RateLimitError(limit=100, window_seconds=60)
        assert "Rate limit exceeded: 100 requests per 60s" in str(error)
        assert error.error_code == "API_003"
        assert error.context["limit"] == 100
        assert error.context["window_seconds"] == 60
        assert error.recoverable is True


class TestExceptionInheritance:
    """Tests for exception inheritance hierarchy."""

    def test_all_inherit_from_base(self):
        """Test that all custom exceptions inherit from DataProcessingError."""
        exceptions_to_test = [
            FileNotFoundError("/test", "local"),
            InvalidDataFormatError("test", "a", "b"),
            PIIDetectionError("test"),
            SparkConnectionError("url", "reason"),
            InvalidConfigError("param", "reason"),
            OutOfMemoryError("op", 100, 50),
            InvalidRequestError("reason"),
        ]

        for exc in exceptions_to_test:
            assert isinstance(exc, DataProcessingError)
            assert isinstance(exc, Exception)

    def test_category_inheritance(self):
        """Test that exceptions inherit from their category."""
        assert isinstance(FileNotFoundError("/test", "local"), StorageError)
        assert isinstance(InvalidDataFormatError("t", "a", "b"), ProcessingError)
        assert isinstance(PIIDetectionError("test"), PrivacyError)
        assert isinstance(SparkConnectionError("url", "r"), DistributedError)
        assert isinstance(InvalidConfigError("p", "r"), ConfigurationError)
        assert isinstance(OutOfMemoryError("o", 1, 2), ResourceError)
        assert isinstance(InvalidRequestError("r"), APIError)
