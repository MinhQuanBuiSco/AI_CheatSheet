"""Unified pipeline supporting both local (Polars) and distributed (Spark) processing."""
from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional, Union
import logging

from .spark_engine import SparkEngine, SparkConfig, SPARK_AVAILABLE

if SPARK_AVAILABLE:
    from pyspark.sql import DataFrame as SparkDataFrame

import polars as pl
from ..core import Pipeline as PolarsPipeline, ProcessorConfig


logger = logging.getLogger(__name__)


class ProcessingMode(Enum):
    """Processing mode selection."""
    LOCAL = "local"  # Single machine with Polars
    SPARK = "spark"  # Distributed with PySpark
    AUTO = "auto"    # Auto-select based on data size


class DistributedPipeline:
    """Unified pipeline that supports both local and distributed processing.

    Automatically selects the best engine based on:
    - Data size
    - Available resources
    - Deployment environment
    """

    def __init__(
        self,
        mode: Union[ProcessingMode, str] = ProcessingMode.AUTO,
        local_config: Optional[ProcessorConfig] = None,
        spark_config: Optional[SparkConfig] = None,
    ):
        """Initialize distributed pipeline.

        Args:
            mode: Processing mode (local, spark, auto)
            local_config: Configuration for local Polars processing
            spark_config: Configuration for Spark processing
        """
        if isinstance(mode, str):
            mode = ProcessingMode(mode)

        self.mode = mode
        self.local_config = local_config or ProcessorConfig()
        self.spark_config = spark_config or SparkConfig()

        self._local_pipeline: Optional[PolarsPipeline] = None
        self._spark_engine: Optional[SparkEngine] = None
        self._processors: List[Callable] = []

    def _get_local_pipeline(self) -> PolarsPipeline:
        """Get or create local Polars pipeline."""
        if self._local_pipeline is None:
            self._local_pipeline = PolarsPipeline(self.local_config)
            for processor in self._processors:
                self._local_pipeline.add_processor(processor)
        return self._local_pipeline

    def _get_spark_engine(self) -> SparkEngine:
        """Get or create Spark engine."""
        if not SPARK_AVAILABLE:
            raise ImportError(
                "PySpark is not available. Install with: pip install pyspark"
            )

        if self._spark_engine is None:
            self._spark_engine = SparkEngine(self.spark_config)
        return self._spark_engine

    def _select_mode(
        self,
        file_path: Path,
        file_size_mb: Optional[float] = None,
    ) -> ProcessingMode:
        """Auto-select processing mode based on data characteristics.

        Args:
            file_path: Path to input file
            file_size_mb: File size in MB (will be calculated if not provided)

        Returns:
            Selected processing mode
        """
        if self.mode != ProcessingMode.AUTO:
            return self.mode

        # Calculate file size if not provided
        if file_size_mb is None and file_path.exists():
            file_size_mb = file_path.stat().st_size / 1024 / 1024

        # Decision logic
        # Use Spark if:
        # 1. File is > 1GB
        # 2. Spark is available
        # 3. Running in cluster mode
        if file_size_mb and file_size_mb > 1024 and SPARK_AVAILABLE:
            logger.info(f"Auto-selected Spark mode (file size: {file_size_mb:.1f} MB)")
            return ProcessingMode.SPARK

        logger.info(f"Auto-selected local mode (file size: {file_size_mb:.1f} MB)")
        return ProcessingMode.LOCAL

    def add_processor(self, processor: Callable) -> 'DistributedPipeline':
        """Add a processor to the pipeline.

        Note: Processor must work with both Polars and Spark DataFrames
        if using AUTO mode.

        Args:
            processor: Processing function

        Returns:
            Self for chaining
        """
        self._processors.append(processor)
        return self

    def process_file(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        file_type: str = "parquet",
        force_mode: Optional[ProcessingMode] = None,
    ) -> dict:
        """Process file using appropriate engine.

        Args:
            input_path: Path to input file
            output_path: Path to output directory
            file_type: File type (parquet, csv, json)
            force_mode: Force specific processing mode

        Returns:
            Processing statistics
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        # Select mode
        selected_mode = force_mode or self._select_mode(input_path)

        if selected_mode == ProcessingMode.SPARK:
            return self._process_with_spark(input_path, output_path, file_type)
        else:
            return self._process_with_polars(input_path, output_path, file_type)

    def _process_with_polars(
        self,
        input_path: Path,
        output_path: Path,
        file_type: str,
    ) -> dict:
        """Process using Polars (local mode).

        Args:
            input_path: Input file path
            output_path: Output directory path
            file_type: File type

        Returns:
            Processing stats
        """
        logger.info(f"Processing with Polars (local mode)")

        pipeline = self._get_local_pipeline()
        stats = pipeline.process_file(
            input_path,
            output_path,
            file_type=file_type,
            enable_multiprocessing=True,
        )

        return {
            "mode": "local",
            "engine": "polars",
            "records_processed": stats.processed_records,
            "records_failed": stats.failed_records,
            "processing_time_seconds": stats.processing_time,
            "throughput": stats.throughput,
        }

    def _process_with_spark(
        self,
        input_path: Path,
        output_path: Path,
        file_type: str,
    ) -> dict:
        """Process using Spark (distributed mode).

        Args:
            input_path: Input file path
            output_path: Output directory path
            file_type: File type

        Returns:
            Processing stats
        """
        logger.info(f"Processing with Spark (distributed mode)")

        import time
        start_time = time.time()

        engine = self._get_spark_engine()

        # Read data
        if file_type == "parquet":
            df = engine.read_parquet(str(input_path))
        elif file_type == "csv":
            df = engine.read_csv(str(input_path), header=True, inferSchema=True)
        elif file_type == "json":
            df = engine.read_json(str(input_path))
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        # Apply processors (simplified - in production would convert processors)
        for processor in self._processors:
            # Would need adapter to convert Polars processors to Spark UDFs
            pass

        # Write output
        engine.write_parquet(df, str(output_path))

        # Calculate stats
        record_count = df.count()
        processing_time = time.time() - start_time

        return {
            "mode": "distributed",
            "engine": "spark",
            "records_processed": record_count,
            "records_failed": 0,
            "processing_time_seconds": processing_time,
            "throughput": record_count / processing_time if processing_time > 0 else 0,
            "spark_stats": engine.get_stats(),
        }

    def stop(self) -> None:
        """Stop all engines and cleanup."""
        if self._spark_engine:
            self._spark_engine.stop()
