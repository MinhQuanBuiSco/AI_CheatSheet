"""Configuration management for CLI."""
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
import orjson


@dataclass
class Config:
    """Application configuration."""
    # Processing
    num_workers: int = 10
    chunk_size: int = 10_000
    max_memory_mb: int = 16_000

    # Privacy
    enable_pii_detection: bool = True
    enable_encryption: bool = False
    anonymization_method: str = "hash"

    # Monitoring
    enable_metrics: bool = True
    enable_logging: bool = True
    log_level: str = "INFO"

    # Analytics
    enable_clustering: bool = False
    num_clusters: int = 5

    # Output
    output_format: str = "parquet"
    output_compression: str = "zstd"

    @classmethod
    def load(cls, path: Path) -> 'Config':
        """Load configuration from file.

        Args:
            path: Path to config file

        Returns:
            Config instance
        """
        with open(path, 'rb') as f:
            data = orjson.loads(f.read())
        return cls(**data)

    def save(self, path: Path) -> None:
        """Save configuration to file.

        Args:
            path: Path to config file
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wb') as f:
            f.write(orjson.dumps(asdict(self), option=orjson.OPT_INDENT_2))

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)
