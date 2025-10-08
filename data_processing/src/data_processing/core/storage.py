"""Efficient storage handlers for large-scale data processing."""

import hashlib
from pathlib import Path
from typing import Any

import blake3
import orjson
import polars as pl
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]


class StorageHandler:
    """Handles efficient data storage with compression and checksums."""

    def __init__(self, base_path: str | Path, enable_compression: bool = True):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.enable_compression = enable_compression

    def write_parquet(
        self, data: pl.DataFrame | pa.Table, filename: str, compression: str = "zstd"
    ) -> Path:
        """Write data to Parquet format with compression.

        Args:
            data: DataFrame or Arrow Table to write
            filename: Output filename
            compression: Compression codec (zstd, snappy, gzip)

        Returns:
            Path to written file
        """
        output_path = self.base_path / filename

        if isinstance(data, pl.DataFrame):
            data.write_parquet(
                output_path,
                compression=compression if self.enable_compression else "uncompressed",  # type: ignore[arg-type]
                statistics=True,
                use_pyarrow=True,
            )
        else:  # Arrow Table
            pq.write_table(
                data,
                output_path,
                compression=compression if self.enable_compression else None,
                use_dictionary=True,
                write_statistics=True,
            )

        return output_path

    def read_parquet(self, filename: str, use_polars: bool = True) -> pl.DataFrame | pa.Table:
        """Read Parquet file.

        Args:
            filename: Input filename
            use_polars: Return Polars DataFrame if True, Arrow Table if False

        Returns:
            Loaded data
        """
        file_path = self.base_path / filename

        if use_polars:
            return pl.read_parquet(file_path)
        else:
            return pq.read_table(file_path)

    def write_json(self, data: Any, filename: str) -> Path:
        """Write data to JSON format using orjson for speed.

        Args:
            data: Data to write (dict, list, etc.)
            filename: Output filename

        Returns:
            Path to written file
        """
        output_path = self.base_path / filename

        with open(output_path, "wb") as f:
            f.write(orjson.dumps(data, option=orjson.OPT_INDENT_2))

        return output_path

    def read_json(self, filename: str) -> Any:
        """Read JSON file using orjson for speed.

        Args:
            filename: Input filename

        Returns:
            Loaded data
        """
        file_path = self.base_path / filename

        with open(file_path, "rb") as f:
            return orjson.loads(f.read())

    def compute_checksum(self, filepath: str | Path, algorithm: str = "blake3") -> str:
        """Compute file checksum.

        Args:
            filepath: Path to file
            algorithm: Hash algorithm (blake3, sha256)

        Returns:
            Hexadecimal checksum string
        """
        filepath = Path(filepath)

        if algorithm == "blake3":
            hasher = blake3.blake3()  # type: ignore[assignment]
        elif algorithm == "sha256":
            hasher = hashlib.sha256()  # type: ignore[assignment]
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)

        return hasher.hexdigest()


class ChunkWriter:
    """Manages writing data in chunks with automatic file rotation."""

    def __init__(
        self,
        storage: StorageHandler,
        prefix: str = "chunk",
        max_records_per_file: int = 1_000_000,
    ):
        self.storage = storage
        self.prefix = prefix
        self.max_records_per_file = max_records_per_file
        self.current_chunk = 0
        self.current_records = 0
        self._buffer: list[dict] = []

    def add_records(self, records: list[dict]) -> None:
        """Add records to buffer and flush when necessary.

        Args:
            records: List of record dictionaries
        """
        self._buffer.extend(records)
        self.current_records += len(records)

        if self.current_records >= self.max_records_per_file:
            self.flush()

    def flush(self) -> Path | None:
        """Flush buffer to disk.

        Returns:
            Path to written file, or None if buffer was empty
        """
        if not self._buffer:
            return None

        # Convert to Polars DataFrame
        df = pl.DataFrame(self._buffer)

        # Write to file
        filename = f"{self.prefix}_{self.current_chunk:06d}.parquet"
        output_path = self.storage.write_parquet(df, filename)

        # Reset state
        self._buffer.clear()
        self.current_chunk += 1
        self.current_records = 0

        return output_path

    def finalize(self) -> list[Path]:
        """Finalize writing and flush remaining data.

        Returns:
            List of all written file paths
        """
        paths = []
        if self._buffer:
            path = self.flush()
            if path:
                paths.append(path)
        return paths
