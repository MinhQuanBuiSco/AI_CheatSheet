"""Memory management utilities."""
import gc
import sys
from typing import Optional
import psutil
import polars as pl


class MemoryMonitor:
    """Monitors memory usage during processing."""

    def __init__(self, threshold_mb: float = 20000):
        """Initialize monitor.

        Args:
            threshold_mb: Alert threshold in MB
        """
        self.threshold_mb = threshold_mb
        self._process = psutil.Process()
        self._peak_memory = 0.0

    def get_current_mb(self) -> float:
        """Get current memory usage in MB."""
        memory_info = self._process.memory_info()
        current_mb = memory_info.rss / 1024 / 1024
        self._peak_memory = max(self._peak_memory, current_mb)
        return current_mb

    def get_available_mb(self) -> float:
        """Get available system memory in MB."""
        return psutil.virtual_memory().available / 1024 / 1024

    def get_peak_mb(self) -> float:
        """Get peak memory usage in MB."""
        return self._peak_memory

    def check_threshold(self) -> bool:
        """Check if memory usage exceeds threshold.

        Returns:
            True if threshold exceeded
        """
        current = self.get_current_mb()
        return current > self.threshold_mb

    def force_gc(self) -> int:
        """Force garbage collection.

        Returns:
            Number of objects collected
        """
        return gc.collect()

    def get_memory_stats(self) -> dict:
        """Get comprehensive memory statistics.

        Returns:
            Dictionary of memory stats
        """
        vm = psutil.virtual_memory()
        return {
            "current_mb": self.get_current_mb(),
            "peak_mb": self._peak_memory,
            "available_mb": vm.available / 1024 / 1024,
            "total_mb": vm.total / 1024 / 1024,
            "percent_used": vm.percent,
            "threshold_mb": self.threshold_mb,
            "threshold_exceeded": self.check_threshold(),
        }


def estimate_dataframe_memory(df: pl.DataFrame) -> float:
    """Estimate memory usage of a Polars DataFrame.

    Args:
        df: DataFrame to estimate

    Returns:
        Estimated memory in MB
    """
    # Polars is more memory-efficient than Pandas
    # Estimate based on number of rows and columns
    num_rows = len(df)
    num_cols = len(df.columns)

    total_bytes = 0

    for col in df.columns:
        dtype = df[col].dtype

        if dtype in [pl.Int8, pl.UInt8]:
            col_bytes = num_rows * 1
        elif dtype in [pl.Int16, pl.UInt16]:
            col_bytes = num_rows * 2
        elif dtype in [pl.Int32, pl.UInt32, pl.Float32]:
            col_bytes = num_rows * 4
        elif dtype in [pl.Int64, pl.UInt64, pl.Float64]:
            col_bytes = num_rows * 8
        elif dtype == pl.Boolean:
            col_bytes = num_rows * 1
        elif dtype == pl.Utf8:
            # Estimate 50 bytes per string on average
            col_bytes = num_rows * 50
        else:
            # Default estimate
            col_bytes = num_rows * 8

        total_bytes += col_bytes

    return total_bytes / 1024 / 1024  # Convert to MB


def get_optimal_chunk_size(
    total_rows: int,
    available_memory_mb: float,
    safety_factor: float = 0.5,
) -> int:
    """Calculate optimal chunk size based on available memory.

    Args:
        total_rows: Total number of rows
        available_memory_mb: Available memory in MB
        safety_factor: Safety factor (0.5 = use 50% of available)

    Returns:
        Optimal chunk size
    """
    # Assume ~1KB per row as baseline
    bytes_per_row = 1024

    # Calculate how many rows fit in available memory
    available_bytes = available_memory_mb * 1024 * 1024 * safety_factor
    max_rows = int(available_bytes / bytes_per_row)

    # Ensure reasonable bounds
    min_chunk = 1000
    max_chunk = 1_000_000

    chunk_size = min(max(min_chunk, max_rows), max_chunk)

    return chunk_size
