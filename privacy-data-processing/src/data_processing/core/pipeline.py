"""High-performance data processing pipeline with streaming and multiprocessing."""

import logging
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import polars as pl
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from ..utils.s3 import S3Storage, resolve_path
from .processor import ProcessorConfig
from .storage import ChunkWriter, StorageHandler

logger = logging.getLogger(__name__)


@dataclass
class PipelineStats:
    """Statistics for pipeline execution."""

    total_records: int = 0
    processed_records: int = 0
    failed_records: int = 0
    processing_time: float = 0.0
    throughput: float = 0.0  # records/second
    chunks_processed: int = 0


class StreamProcessor:
    """Streaming data processor with memory-efficient chunking."""

    def __init__(self, config: ProcessorConfig):
        self.config = config
        self.stats = PipelineStats()

    def stream_parquet(
        self,
        file_path: str | Path,
        chunk_size: int | None = None,
    ) -> Iterator[pl.DataFrame]:
        """Stream Parquet file in chunks.

        Supports both local files and S3/MinIO paths (s3://bucket/path).

        Args:
            file_path: Path to Parquet file (local or s3://)
            chunk_size: Records per chunk (uses config if not specified)

        Yields:
            DataFrame chunks
        """
        chunk_size = chunk_size or self.config.chunk_size

        # Resolve path (handles S3 if needed)
        resolved_path, storage_options = resolve_path(file_path)

        if storage_options:
            # S3/MinIO path - use pyarrow with storage options
            logger.info(f"Streaming from S3: {resolved_path}")
            import pyarrow.fs as pafs  # type: ignore[import-untyped]

            # Create S3 filesystem
            s3fs = pafs.S3FileSystem(
                access_key=storage_options["key"],
                secret_key=storage_options["secret"],
                endpoint_override=storage_options.get("endpoint_url"),
                region=storage_options.get("client_kwargs", {}).get("region_name", "us-east-1"),
            )

            # Parse S3 path
            bucket, key = S3Storage.parse_s3_path(resolved_path)
            s3_path = f"{bucket}/{key}"

            # Open and stream Parquet file
            parquet_file = pq.ParquetFile(s3fs.open_input_file(s3_path))
        else:
            # Local file
            file_path = Path(file_path)
            logger.debug(f"Streaming from local file: {file_path}")
            parquet_file = pq.ParquetFile(file_path)

        for batch in parquet_file.iter_batches(batch_size=chunk_size):
            # Convert to Polars for efficient processing
            yield pl.from_arrow(batch)  # type: ignore[misc]
            self.stats.chunks_processed += 1

    def stream_json(
        self,
        file_path: str | Path,
        chunk_size: int | None = None,
    ) -> Iterator[pl.DataFrame]:
        """Stream JSON file in chunks.

        Args:
            file_path: Path to JSON file
            chunk_size: Records per chunk (uses config if not specified)

        Yields:
            DataFrame chunks
        """
        chunk_size = chunk_size or self.config.chunk_size
        file_path = Path(file_path)

        # Read JSON in batches (Polars handles streaming efficiently)
        try:
            df = pl.read_ndjson(file_path)

            # Yield in chunks
            total_rows = len(df)
            for i in range(0, total_rows, chunk_size):
                yield df.slice(i, chunk_size)
                self.stats.chunks_processed += 1

        except Exception:
            # Fall back to regular JSON if not NDJSON
            df = pl.read_json(file_path)
            total_rows = len(df)
            for i in range(0, total_rows, chunk_size):
                yield df.slice(i, chunk_size)
                self.stats.chunks_processed += 1

    def stream_csv(
        self,
        file_path: str | Path,
        chunk_size: int | None = None,
    ) -> Iterator[pl.DataFrame]:
        """Stream CSV file in chunks.

        Args:
            file_path: Path to CSV file
            chunk_size: Records per chunk (uses config if not specified)

        Yields:
            DataFrame chunks
        """
        chunk_size = chunk_size or self.config.chunk_size

        # Polars can efficiently read CSV in batches
        reader = pl.read_csv_batched(
            file_path,
            batch_size=chunk_size,
            infer_schema_length=10000,
        )

        while True:
            batch = reader.next_batches(1)
            if not batch:
                break
            yield batch[0]
            self.stats.chunks_processed += 1


class Pipeline:
    """Main data processing pipeline with multiprocessing support."""

    def __init__(self, config: ProcessorConfig):
        self.config = config
        self.stats = PipelineStats()
        self.processors: list[Callable] = []
        self._checkpoints: dict[int, Path] = {}

    def add_processor(self, processor: Callable[[pl.DataFrame], pl.DataFrame]) -> "Pipeline":
        """Add a processing function to the pipeline.

        Args:
            processor: Function that takes and returns a DataFrame

        Returns:
            Self for chaining
        """
        self.processors.append(processor)
        return self

    def _process_chunk(
        self,
        chunk: pl.DataFrame,
        chunk_id: int,
    ) -> tuple[int, pl.DataFrame, Exception | None]:
        """Process a single chunk through all processors.

        Args:
            chunk: Input DataFrame chunk
            chunk_id: Unique chunk identifier

        Returns:
            Tuple of (chunk_id, processed_chunk, error)
        """
        try:
            result = chunk
            for processor in self.processors:
                result = processor(result)
            return (chunk_id, result, None)
        except Exception as e:
            return (chunk_id, chunk, e)

    def process_file(
        self,
        input_path: str | Path,
        output_path: str | Path,
        file_type: str = "parquet",
        enable_multiprocessing: bool = True,
    ) -> PipelineStats:
        """Process a file through the pipeline.

        Args:
            input_path: Path to input file
            output_path: Path to output directory
            file_type: Input file type (parquet, json, csv)
            enable_multiprocessing: Use multiprocessing if True

        Returns:
            Pipeline statistics
        """
        start_time = time.time()
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        # Initialize storage and chunk writer
        storage = StorageHandler(output_path, enable_compression=self.config.enable_compression)
        chunk_writer = ChunkWriter(
            storage,
            prefix=input_path.stem,
            max_records_per_file=self.config.chunk_size * 10,
        )

        # Initialize stream processor
        stream_processor = StreamProcessor(self.config)

        # Select appropriate streaming method
        stream_methods = {
            "parquet": stream_processor.stream_parquet,
            "json": stream_processor.stream_json,
            "csv": stream_processor.stream_csv,
        }

        if file_type not in stream_methods:
            raise ValueError(f"Unsupported file type: {file_type}")

        stream_method = stream_methods[file_type]

        if enable_multiprocessing and self.config.num_workers > 1:
            self._process_multiprocessing(
                input_path,
                stream_method,
                chunk_writer,
            )
        else:
            self._process_single(
                input_path,
                stream_method,
                chunk_writer,
            )

        # Finalize writing
        chunk_writer.finalize()

        # Update stats
        self.stats.processing_time = time.time() - start_time
        if self.stats.processing_time > 0:
            self.stats.throughput = self.stats.processed_records / self.stats.processing_time

        return self.stats

    def _process_single(
        self,
        input_path: Path,
        stream_method: Callable,
        chunk_writer: ChunkWriter,
    ) -> None:
        """Process data in single-threaded mode.

        Args:
            input_path: Path to input file
            stream_method: Method to stream input data
            chunk_writer: Writer for output chunks
        """
        for chunk_id, chunk in enumerate(stream_method(input_path)):
            self.stats.total_records += len(chunk)

            # Process chunk
            _, processed_chunk, error = self._process_chunk(chunk, chunk_id)

            if error:
                self.stats.failed_records += len(chunk)
                continue

            self.stats.processed_records += len(processed_chunk)

            # Write to output
            chunk_writer.add_records(processed_chunk.to_dicts())

            # Checkpoint if needed
            if self.stats.processed_records % self.config.checkpoint_interval == 0:
                self._create_checkpoint(chunk_writer, chunk_id)

    def _process_multiprocessing(
        self,
        input_path: Path,
        stream_method: Callable,
        chunk_writer: ChunkWriter,
    ) -> None:
        """Process data using multiprocessing.

        Args:
            input_path: Path to input file
            stream_method: Method to stream input data
            chunk_writer: Writer for output chunks
        """
        with ProcessPoolExecutor(max_workers=self.config.num_workers) as executor:
            # Submit chunks for processing
            futures = []
            for chunk_id, chunk in enumerate(stream_method(input_path)):
                self.stats.total_records += len(chunk)
                future = executor.submit(self._process_chunk, chunk, chunk_id)
                futures.append((future, len(chunk)))

            # Collect results
            for future, chunk_size in futures:
                chunk_id, processed_chunk, error = future.result()

                if error:
                    self.stats.failed_records += chunk_size
                    continue

                self.stats.processed_records += len(processed_chunk)

                # Write to output
                chunk_writer.add_records(processed_chunk.to_dicts())

                # Checkpoint if needed
                if self.stats.processed_records % self.config.checkpoint_interval == 0:
                    self._create_checkpoint(chunk_writer, chunk_id)

    def _create_checkpoint(self, chunk_writer: ChunkWriter, chunk_id: int) -> None:
        """Create a processing checkpoint.

        Args:
            chunk_writer: Current chunk writer
            chunk_id: Current chunk ID
        """
        checkpoint_path = chunk_writer.flush()
        if checkpoint_path:
            self._checkpoints[chunk_id] = checkpoint_path

    def get_checkpoints(self) -> dict[int, Path]:
        """Get all checkpoint paths.

        Returns:
            Dictionary mapping chunk IDs to checkpoint paths
        """
        return self._checkpoints.copy()
