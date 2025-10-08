"""Shared pytest fixtures for all tests.

This module provides common test fixtures for:
- Sample data generation
- Temporary directories
- Mock services
- Test configuration
"""
import tempfile
from pathlib import Path
from typing import Generator
import uuid

import polars as pl
import pytest
from faker import Faker


@pytest.fixture
def faker_instance() -> Faker:
    """Provide a Faker instance with fixed seed for reproducible tests."""
    fake = Faker()
    Faker.seed(42)
    return fake


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="session")
def test_data_dir(tmp_path_factory):
    """Create a temporary directory for test data (session-scoped)."""
    return tmp_path_factory.mktemp("test_data")


@pytest.fixture
def sample_dataframe() -> pl.DataFrame:
    """Create a small sample DataFrame for testing."""
    return pl.DataFrame({
        "id": list(range(100)),
        "timestamp": pl.datetime_range(
            start=pl.datetime(2024, 1, 1),
            end=pl.datetime(2024, 1, 1, 1, 39),
            interval="1m",
            eager=True
        ),
        "value": list(range(100, 200)),
        "category": ["A", "B", "C"] * 33 + ["A"],
        "text": [f"Sample text {i}" for i in range(100)],
    })


@pytest.fixture
def large_dataframe() -> pl.DataFrame:
    """Create a larger DataFrame for performance testing."""
    size = 10000
    return pl.DataFrame({
        "id": list(range(size)),
        "value": [i * 2 for i in range(size)],
        "text": [f"Text {i}" for i in range(size)],
    })


@pytest.fixture
def pii_dataframe(faker_instance: Faker) -> pl.DataFrame:
    """Create DataFrame with PII for privacy testing."""
    size = 50
    return pl.DataFrame({
        "id": list(range(size)),
        "name": [faker_instance.name() for _ in range(size)],
        "email": [faker_instance.email() for _ in range(size)],
        "phone": [faker_instance.phone_number() for _ in range(size)],
        "ssn": [faker_instance.ssn() for _ in range(size)],
        "address": [faker_instance.address().replace("\n", ", ") for _ in range(size)],
        "message": [
            f"Hi, I'm {faker_instance.name()}. Email me at {faker_instance.email()}"
            for _ in range(size)
        ],
    })


@pytest.fixture
def parquet_file(sample_dataframe: pl.DataFrame, temp_dir: Path) -> Path:
    """Create a temporary Parquet file."""
    file_path = temp_dir / "test_data.parquet"
    sample_dataframe.write_parquet(file_path)
    return file_path


@pytest.fixture
def csv_file(sample_dataframe: pl.DataFrame, temp_dir: Path) -> Path:
    """Create a temporary CSV file."""
    file_path = temp_dir / "test_data.csv"
    sample_dataframe.write_csv(file_path)
    return file_path


@pytest.fixture
def correlation_id() -> str:
    """Generate a correlation ID for tracing."""
    return str(uuid.uuid4())


@pytest.fixture
def job_id() -> str:
    """Generate a job ID for testing."""
    return str(uuid.uuid4())
