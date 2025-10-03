"""Metrics collection for monitoring processing performance."""
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import psutil
from prometheus_client import Counter, Gauge, Histogram, Summary, CollectorRegistry


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
    """Collects and exports metrics for monitoring."""

    def __init__(self, job_name: str = "data_processing"):
        self.job_name = job_name
        self.registry = CollectorRegistry()

        # Initialize Prometheus metrics
        self.records_processed = Counter(
            'records_processed_total',
            'Total number of records processed',
            registry=self.registry,
        )
        self.records_failed = Counter(
            'records_failed_total',
            'Total number of records that failed processing',
            registry=self.registry,
        )
        self.bytes_processed = Counter(
            'bytes_processed_total',
            'Total bytes processed',
            registry=self.registry,
        )
        self.processing_duration = Histogram(
            'processing_duration_seconds',
            'Time spent processing data',
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
            registry=self.registry,
        )
        self.cpu_usage = Gauge(
            'cpu_usage_percent',
            'CPU usage percentage',
            registry=self.registry,
        )
        self.memory_usage = Gauge(
            'memory_usage_mb',
            'Memory usage in MB',
            registry=self.registry,
        )
        self.throughput = Gauge(
            'throughput_records_per_second',
            'Processing throughput in records/second',
            registry=self.registry,
        )

        # Internal metrics
        self._metrics = ProcessingMetrics()
        self._process = psutil.Process()
        self._start_time: Optional[float] = None

    def start_processing(self) -> None:
        """Mark the start of processing."""
        self._start_time = time.time()
        self._metrics.timestamps['start'] = self._start_time

    def record_processed(self, count: int = 1, bytes_size: int = 0) -> None:
        """Record successfully processed records.

        Args:
            count: Number of records processed
            bytes_size: Size in bytes
        """
        self._metrics.records_processed += count
        self._metrics.bytes_processed += bytes_size
        self.records_processed.inc(count)
        self.bytes_processed.inc(bytes_size)

    def record_failed(self, count: int = 1, error: Optional[str] = None) -> None:
        """Record failed records.

        Args:
            count: Number of records that failed
            error: Error message
        """
        self._metrics.records_failed += count
        self.records_failed.inc(count)
        if error:
            self._metrics.errors.append(error)

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
        self.memory_usage.set(memory_mb)

        # Track peak memory
        if memory_mb > self._metrics.peak_memory_mb:
            self._metrics.peak_memory_mb = memory_mb

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
