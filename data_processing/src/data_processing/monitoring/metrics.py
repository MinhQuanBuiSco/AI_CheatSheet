"""Metrics collection for monitoring processing performance.

Anthropic-level monitoring: Privacy-first, research-focused, production-grade.
"""
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import psutil
from prometheus_client import Counter, Gauge, Histogram, Summary, CollectorRegistry, Info


@dataclass
class ProcessingMetrics:
    """Container for processing metrics."""
    records_processed: int = 0
    records_failed: int = 0
    bytes_processed: int = 0
    processing_time_seconds: float = 0.0
    throughput_records_per_sec: float = 0.0
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    peak_memory_mb: float = 0.0
    errors: List[str] = field(default_factory=list)
    timestamps: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "records_processed": self.records_processed,
            "records_failed": self.records_failed,
            "bytes_processed": self.bytes_processed,
            "processing_time_seconds": self.processing_time_seconds,
            "throughput_records_per_sec": self.throughput_records_per_sec,
            "cpu_percent": self.cpu_percent,
            "memory_mb": self.memory_mb,
            "peak_memory_mb": self.peak_memory_mb,
            "error_count": len(self.errors),
            "timestamps": self.timestamps,
        }


class MetricsCollector:
    """Collects and exports metrics for monitoring.

    Anthropic-level metrics: comprehensive, privacy-aware, research-focused.
    """

    def __init__(self, job_name: str = "data_processing"):
        self.job_name = job_name
        self.registry = CollectorRegistry()

        # ============================================================
        # PROCESSING METRICS
        # ============================================================
        self.records_processed = Counter(
            'records_processed_total',
            'Total number of records processed',
            ['stage', 'status'],  # Labels: stage=ingestion/processing/output, status=success/failed
            registry=self.registry,
        )
        self.processing_duration = Histogram(
            'processing_duration_seconds',
            'Time spent processing data by stage',
            ['stage'],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0],
            registry=self.registry,
        )
        self.batch_size = Histogram(
            'batch_size_records',
            'Number of records per batch',
            ['stage'],
            buckets=[10, 50, 100, 500, 1000, 5000, 10000, 50000, 100000],
            registry=self.registry,
        )
        self.pipeline_queue_depth = Gauge(
            'pipeline_queue_depth',
            'Number of items waiting in pipeline queue',
            ['stage'],
            registry=self.registry,
        )
        self.throughput = Gauge(
            'throughput_records_per_second',
            'Processing throughput in records/second',
            ['stage'],
            registry=self.registry,
        )

        # ============================================================
        # DATA QUALITY METRICS (Research-focused)
        # ============================================================
        self.data_quality_score = Gauge(
            'data_quality_score',
            'Overall data quality score (0-1)',
            ['dataset'],
            registry=self.registry,
        )
        self.schema_validation_failures = Counter(
            'schema_validation_failures_total',
            'Number of schema validation failures',
            ['field', 'error_type'],
            registry=self.registry,
        )
        self.duplicate_records = Counter(
            'duplicate_records_total',
            'Number of duplicate records detected',
            ['dedup_method'],
            registry=self.registry,
        )
        self.data_freshness = Gauge(
            'data_freshness_seconds',
            'Age of the most recently processed data',
            ['source'],
            registry=self.registry,
        )

        # ============================================================
        # PRIVACY & AUDIT METRICS (Critical for CLIO)
        # ============================================================
        self.pii_entities_detected = Counter(
            'pii_entities_detected_total',
            'Number of PII entities detected by type',
            ['entity_type'],  # email, phone, name, ssn, etc.
            registry=self.registry,
        )
        self.anonymization_operations = Counter(
            'anonymization_operations_total',
            'Number of anonymization operations by method',
            ['method', 'status'],  # method=hash/mask/redact/synthetic, status=success/failed
            registry=self.registry,
        )
        self.audit_log_writes = Counter(
            'audit_log_writes_total',
            'Number of audit log entries written',
            ['operation', 'status'],  # operation=read/write/delete/export
            registry=self.registry,
        )
        self.privacy_policy_violations = Counter(
            'privacy_policy_violations_total',
            'Number of privacy policy violations detected',
            ['violation_type'],
            registry=self.registry,
        )
        self.encryption_operations = Counter(
            'encryption_operations_total',
            'Number of encryption/decryption operations',
            ['direction', 'status'],  # direction=encrypt/decrypt
            registry=self.registry,
        )

        # ============================================================
        # STORAGE METRICS (MinIO/S3)
        # ============================================================
        self.storage_operations = Counter(
            'storage_operations_total',
            'Number of storage operations',
            ['operation', 'status'],  # operation=upload/download/delete/list
            registry=self.registry,
        )
        self.storage_bytes_transferred = Counter(
            'storage_bytes_transferred_total',
            'Total bytes transferred to/from storage',
            ['direction'],  # upload/download
            registry=self.registry,
        )
        self.storage_latency = Histogram(
            'storage_latency_seconds',
            'Storage operation latency',
            ['operation'],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
            registry=self.registry,
        )
        self.storage_objects_count = Gauge(
            'storage_objects_total',
            'Total number of objects in storage',
            ['bucket'],
            registry=self.registry,
        )

        # ============================================================
        # RESOURCE METRICS
        # ============================================================
        self.cpu_usage = Gauge(
            'cpu_usage_percent',
            'CPU usage percentage',
            registry=self.registry,
        )
        self.memory_usage = Gauge(
            'memory_usage_bytes',
            'Memory usage in bytes',
            ['type'],  # rss, vms
            registry=self.registry,
        )
        self.open_file_descriptors = Gauge(
            'open_file_descriptors',
            'Number of open file descriptors',
            registry=self.registry,
        )
        self.disk_io_bytes = Counter(
            'disk_io_bytes_total',
            'Disk I/O in bytes',
            ['direction'],  # read/write
            registry=self.registry,
        )

        # ============================================================
        # API METRICS
        # ============================================================
        self.http_requests = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status_code'],
            registry=self.registry,
        )
        self.http_request_duration = Histogram(
            'http_request_duration_seconds',
            'HTTP request latency',
            ['method', 'endpoint'],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
            registry=self.registry,
        )
        self.http_requests_in_flight = Gauge(
            'http_requests_in_flight',
            'Number of HTTP requests currently being processed',
            registry=self.registry,
        )

        # ============================================================
        # SYSTEM INFO
        # ============================================================
        self.build_info = Info(
            'build_info',
            'Build information',
            registry=self.registry,
        )
        import sys
        import platform as platform_module
        self.build_info.info({
            'job_name': job_name,
            'python_version': platform_module.python_version(),
            'platform': platform_module.system(),
        })

        # Internal metrics
        self._metrics = ProcessingMetrics()
        self._process = psutil.Process()
        self._start_time: Optional[float] = None
        self._stage_timers: Dict[str, float] = {}

    def start_processing(self) -> None:
        """Mark the start of processing."""
        self._start_time = time.time()
        self._metrics.timestamps['start'] = self._start_time

    def record_processed(self, count: int = 1, bytes_size: int = 0, stage: str = "processing") -> None:
        """Record successfully processed records.

        Args:
            count: Number of records processed
            bytes_size: Size in bytes
            stage: Processing stage (ingestion/processing/output)
        """
        self._metrics.records_processed += count
        self._metrics.bytes_processed += bytes_size
        self.records_processed.labels(stage=stage, status="success").inc(count)

    def record_failed(self, count: int = 1, error: Optional[str] = None, stage: str = "processing") -> None:
        """Record failed records.

        Args:
            count: Number of records that failed
            error: Error message
            stage: Processing stage
        """
        self._metrics.records_failed += count
        self.records_processed.labels(stage=stage, status="failed").inc(count)
        if error:
            self._metrics.errors.append(error)

    # ============================================================
    # PRIVACY & AUDIT METHODS
    # ============================================================

    def record_pii_detected(self, entity_type: str, count: int = 1) -> None:
        """Record PII entity detection.

        Args:
            entity_type: Type of PII (email, phone, name, ssn, etc.)
            count: Number of entities detected
        """
        self.pii_entities_detected.labels(entity_type=entity_type).inc(count)

    def record_anonymization(self, method: str, count: int = 1, success: bool = True) -> None:
        """Record anonymization operation.

        Args:
            method: Anonymization method (hash, mask, redact, synthetic)
            count: Number of operations
            success: Whether operation succeeded
        """
        status = "success" if success else "failed"
        self.anonymization_operations.labels(method=method, status=status).inc(count)

    def record_audit_log(self, operation: str, success: bool = True) -> None:
        """Record audit log write.

        Args:
            operation: Operation type (read, write, delete, export)
            success: Whether write succeeded
        """
        status = "success" if success else "failed"
        self.audit_log_writes.labels(operation=operation, status=status).inc()

    def record_privacy_violation(self, violation_type: str) -> None:
        """Record privacy policy violation.

        Args:
            violation_type: Type of violation
        """
        self.privacy_policy_violations.labels(violation_type=violation_type).inc()

    def record_encryption(self, direction: str, success: bool = True) -> None:
        """Record encryption/decryption operation.

        Args:
            direction: encrypt or decrypt
            success: Whether operation succeeded
        """
        status = "success" if success else "failed"
        self.encryption_operations.labels(direction=direction, status=status).inc()

    # ============================================================
    # STORAGE METHODS
    # ============================================================

    def record_storage_operation(self, operation: str, success: bool = True, bytes_transferred: int = 0, latency: float = 0.0) -> None:
        """Record storage operation.

        Args:
            operation: Operation type (upload, download, delete, list)
            success: Whether operation succeeded
            bytes_transferred: Bytes uploaded or downloaded
            latency: Operation latency in seconds
        """
        status = "success" if success else "failed"
        self.storage_operations.labels(operation=operation, status=status).inc()

        if bytes_transferred > 0:
            direction = "upload" if operation == "upload" else "download"
            self.storage_bytes_transferred.labels(direction=direction).inc(bytes_transferred)

        if latency > 0:
            self.storage_latency.labels(operation=operation).observe(latency)

    def update_storage_objects(self, bucket: str, count: int) -> None:
        """Update storage object count.

        Args:
            bucket: Bucket name
            count: Number of objects
        """
        self.storage_objects_count.labels(bucket=bucket).set(count)

    # ============================================================
    # DATA QUALITY METHODS
    # ============================================================

    def record_quality_score(self, dataset: str, score: float) -> None:
        """Record data quality score.

        Args:
            dataset: Dataset name
            score: Quality score (0-1)
        """
        self.data_quality_score.labels(dataset=dataset).set(score)

    def record_schema_validation_failure(self, field: str, error_type: str) -> None:
        """Record schema validation failure.

        Args:
            field: Field that failed validation
            error_type: Type of validation error
        """
        self.schema_validation_failures.labels(field=field, error_type=error_type).inc()

    def record_duplicate(self, dedup_method: str, count: int = 1) -> None:
        """Record duplicate detection.

        Args:
            dedup_method: Deduplication method used
            count: Number of duplicates
        """
        self.duplicate_records.labels(dedup_method=dedup_method).inc(count)

    def update_data_freshness(self, source: str, age_seconds: float) -> None:
        """Update data freshness metric.

        Args:
            source: Data source
            age_seconds: Age of data in seconds
        """
        self.data_freshness.labels(source=source).set(age_seconds)

    # ============================================================
    # API METHODS
    # ============================================================

    def record_http_request(self, method: str, endpoint: str, status_code: int, duration: float) -> None:
        """Record HTTP request.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            status_code: HTTP status code
            duration: Request duration in seconds
        """
        self.http_requests.labels(method=method, endpoint=endpoint, status_code=str(status_code)).inc()
        self.http_request_duration.labels(method=method, endpoint=endpoint).observe(duration)

    def increment_http_in_flight(self) -> None:
        """Increment in-flight HTTP requests counter."""
        self.http_requests_in_flight.inc()

    def decrement_http_in_flight(self) -> None:
        """Decrement in-flight HTTP requests counter."""
        self.http_requests_in_flight.dec()

    # ============================================================
    # PROCESSING STAGE METHODS
    # ============================================================

    def start_stage(self, stage: str) -> None:
        """Start timing a processing stage.

        Args:
            stage: Stage name
        """
        self._stage_timers[stage] = time.time()

    def end_stage(self, stage: str, record_count: int = 0) -> None:
        """End timing a processing stage.

        Args:
            stage: Stage name
            record_count: Number of records processed in this stage
        """
        if stage in self._stage_timers:
            duration = time.time() - self._stage_timers[stage]
            self.processing_duration.labels(stage=stage).observe(duration)

            if record_count > 0:
                self.batch_size.labels(stage=stage).observe(record_count)
                throughput = record_count / duration if duration > 0 else 0
                self.throughput.labels(stage=stage).set(throughput)

            del self._stage_timers[stage]

    def update_queue_depth(self, stage: str, depth: int) -> None:
        """Update pipeline queue depth.

        Args:
            stage: Stage name
            depth: Queue depth
        """
        self.pipeline_queue_depth.labels(stage=stage).set(depth)

    def update_resource_metrics(self) -> None:
        """Update CPU and memory usage metrics."""
        # CPU usage
        cpu_percent = self._process.cpu_percent(interval=0.1)
        self._metrics.cpu_percent = cpu_percent
        self.cpu_usage.set(cpu_percent)

        # Memory usage
        memory_info = self._process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        self._metrics.memory_mb = memory_mb
        self.memory_usage.labels(type="rss").set(memory_info.rss)
        self.memory_usage.labels(type="vms").set(memory_info.vms)

        # Track peak memory
        if memory_mb > self._metrics.peak_memory_mb:
            self._metrics.peak_memory_mb = memory_mb

        # File descriptors
        try:
            num_fds = self._process.num_fds() if hasattr(self._process, 'num_fds') else 0
            if num_fds > 0:
                self.open_file_descriptors.set(num_fds)
        except (AttributeError, NotImplementedError):
            # num_fds not available on all platforms
            pass

        # Disk I/O
        try:
            io_counters = self._process.io_counters() if hasattr(self._process, 'io_counters') else None
            if io_counters:
                # Note: These are cumulative counters, not rates
                self.disk_io_bytes.labels(direction="read").inc(0)  # Initialize
                self.disk_io_bytes.labels(direction="write").inc(0)  # Initialize
        except (AttributeError, NotImplementedError):
            # io_counters not available on all platforms
            pass

    def finish_processing(self) -> ProcessingMetrics:
        """Mark the end of processing and calculate final metrics.

        Returns:
            Final processing metrics
        """
        end_time = time.time()
        self._metrics.timestamps['end'] = end_time

        if self._start_time:
            self._metrics.processing_time_seconds = end_time - self._start_time
            self.processing_duration.observe(self._metrics.processing_time_seconds)

            # Calculate throughput
            if self._metrics.processing_time_seconds > 0:
                self._metrics.throughput_records_per_sec = (
                    self._metrics.records_processed / self._metrics.processing_time_seconds
                )
                self.throughput.set(self._metrics.throughput_records_per_sec)

        # Final resource update
        self.update_resource_metrics()

        return self._metrics

    def get_metrics(self) -> ProcessingMetrics:
        """Get current metrics.

        Returns:
            Current processing metrics
        """
        return self._metrics

    def get_summary(self) -> str:
        """Get a human-readable summary of metrics.

        Returns:
            Summary string
        """
        m = self._metrics
        lines = [
            "Processing Summary:",
            f"  Records Processed: {m.records_processed:,}",
            f"  Records Failed: {m.records_failed:,}",
            f"  Bytes Processed: {m.bytes_processed:,} ({m.bytes_processed / 1024 / 1024:.2f} MB)",
            f"  Processing Time: {m.processing_time_seconds:.2f}s",
            f"  Throughput: {m.throughput_records_per_sec:,.2f} records/sec",
            f"  Peak Memory: {m.peak_memory_mb:.2f} MB",
            f"  CPU Usage: {m.cpu_percent:.1f}%",
            f"  Errors: {len(m.errors)}",
        ]
        return "\n".join(lines)
