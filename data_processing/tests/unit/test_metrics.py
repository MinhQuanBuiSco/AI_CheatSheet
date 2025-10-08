"""Tests for monitoring/metrics module."""


from data_processing.monitoring.metrics import MetricsCollector


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    def setup_method(self):
        """Setup test collector."""
        self.collector = MetricsCollector(job_name="test_job")

    def test_collector_initialization(self):
        """Test MetricsCollector initialization."""
        assert self.collector.job_name == "test_job"
        assert self.collector.records_processed is not None
        assert self.collector.processing_duration is not None

    def test_record_processed(self):
        """Test recording processed records."""
        self.collector.record_processed(count=100, stage="test")
        # Metrics are recorded, exact value checking requires querying Prometheus registry

    def test_record_failed(self):
        """Test recording failed records."""
        self.collector.record_failed(count=5, error="TestError", stage="validation")

    def test_record_pii_detected(self):
        """Test recording PII detection."""
        self.collector.record_pii_detected("email", count=10)
        self.collector.record_pii_detected("phone", count=5)

    def test_record_anonymization(self):
        """Test recording anonymization operations."""
        self.collector.record_anonymization("hash", count=15, success=True)
        self.collector.record_anonymization("mask", count=3, success=False)

    def test_record_audit_log(self):
        """Test recording audit log operations."""
        self.collector.record_audit_log("data_access", success=True)
        self.collector.record_audit_log("data_modification", success=False)

    def test_record_quality_score(self):
        """Test recording data quality score."""
        self.collector.record_quality_score("test_dataset", 0.95)
        self.collector.record_quality_score("test_dataset", 0.88)

    def test_initialization_with_job_name(self):
        """Test MetricsCollector initialization with custom job name."""
        collector = MetricsCollector(job_name="custom_job")
        assert collector.job_name == "custom_job"
        collector.record_processed(count=50)
