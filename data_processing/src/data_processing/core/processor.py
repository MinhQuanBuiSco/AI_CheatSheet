"""Base processor classes and configuration."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import multiprocessing as mp


@dataclass
class ProcessorConfig:
    """Configuration for data processors.

    Optimized for Mac M4 with 12 cores and 24GB RAM.
    """
    chunk_size: int = 10_000  # Records per chunk
    batch_size: int = 1_000    # Records per batch
    num_workers: int = field(default_factory=lambda: max(1, mp.cpu_count() - 2))  # Leave 2 cores for system
    max_memory_mb: int = 16_000  # Reserve 8GB for system
    enable_compression: bool = True
    enable_encryption: bool = True
    enable_pii_detection: bool = True
    output_format: str = "parquet"  # parquet, json, arrow
    temp_dir: Optional[str] = None
    checkpoint_interval: int = 100_000  # Records between checkpoints
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration."""
        if self.num_workers < 1:
            raise ValueError("num_workers must be at least 1")
        if self.chunk_size < self.batch_size:
            raise ValueError("chunk_size must be >= batch_size")
        if self.max_memory_mb < 1000:
            raise ValueError("max_memory_mb must be at least 1000")


class BaseProcessor(ABC):
    """Abstract base class for data processors."""

    def __init__(self, config: ProcessorConfig):
        self.config = config
        self._processed_count = 0
        self._error_count = 0

    @abstractmethod
    def process_batch(self, batch: Any) -> Any:
        """Process a batch of data.

        Args:
            batch: Input batch data

        Returns:
            Processed batch data
        """
        pass

    @abstractmethod
    def validate(self, data: Any) -> bool:
        """Validate data before processing.

        Args:
            data: Input data to validate

        Returns:
            True if valid, False otherwise
        """
        pass

    def on_error(self, error: Exception, batch: Any) -> None:
        """Handle processing errors.

        Args:
            error: Exception that occurred
            batch: Batch that caused the error
        """
        self._error_count += 1

    def get_stats(self) -> Dict[str, int]:
        """Get processing statistics.

        Returns:
            Dictionary with processing stats
        """
        return {
            "processed": self._processed_count,
            "errors": self._error_count,
        }
