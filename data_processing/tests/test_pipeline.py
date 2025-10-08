"""Tests for core pipeline functionality."""
import tempfile
from pathlib import Path

import polars as pl
import pytest

from data_processing.core import Pipeline, ProcessorConfig


@pytest.fixture
def sample_data():
    """Create sample data for testing."""
    return pl.DataFrame({
        "id": list(range(1000)),
        "value": list(range(1000, 2000)),
        "text": [f"Sample text {i}" for i in range(1000)],
    })


@pytest.fixture
def temp_output_dir():
    """Create temporary output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_pipeline_creation():
    """Test pipeline can be created."""
    config = ProcessorConfig(chunk_size=1000, batch_size=100, num_workers=2)
    pipeline = Pipeline(config)
    assert pipeline is not None
    assert len(pipeline.processors) == 0


def test_pipeline_add_processor():
    """Test adding processors to pipeline."""
    config = ProcessorConfig()
    pipeline = Pipeline(config)

    def sample_processor(df: pl.DataFrame) -> pl.DataFrame:
        return df.with_columns(pl.col("value") * 2)

    pipeline.add_processor(sample_processor)
    assert len(pipeline.processors) == 1


def test_pipeline_process_file(sample_data, temp_output_dir):
    """Test processing a file through pipeline."""
    # Create input file
    input_file = temp_output_dir / "input.parquet"
    sample_data.write_parquet(input_file)

    # Create pipeline
    config = ProcessorConfig(chunk_size=1000, batch_size=100, num_workers=2)
    pipeline = Pipeline(config)

    # Add simple processor
    def double_values(df: pl.DataFrame) -> pl.DataFrame:
        return df.with_columns(pl.col("value") * 2)

    pipeline.add_processor(double_values)

    # Process file
    stats = pipeline.process_file(
        input_file,
        temp_output_dir / "output",
        file_type="parquet",
        enable_multiprocessing=False,  # Disable for testing
    )

    # Verify stats
    assert stats.processed_records == len(sample_data)
    assert stats.failed_records == 0


def test_pipeline_multiprocessing(sample_data, temp_output_dir):
    """Test multiprocessing pipeline."""
    input_file = temp_output_dir / "input.parquet"
    sample_data.write_parquet(input_file)

    config = ProcessorConfig(chunk_size=2000, batch_size=200, num_workers=2)
    pipeline = Pipeline(config)

    stats = pipeline.process_file(
        input_file,
        temp_output_dir / "output",
        file_type="parquet",
        enable_multiprocessing=True,
    )

    assert stats.processed_records == len(sample_data)
