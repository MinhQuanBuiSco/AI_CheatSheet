"""Data quality checking and reporting."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import polars as pl
import numpy as np


@dataclass
class QualityReport:
    """Report of data quality metrics."""
    total_records: int
    total_columns: int
    null_counts: Dict[str, int] = field(default_factory=dict)
    null_percentages: Dict[str, float] = field(default_factory=dict)
    duplicate_count: int = 0
    unique_counts: Dict[str, int] = field(default_factory=dict)
    data_types: Dict[str, str] = field(default_factory=dict)
    numeric_stats: Dict[str, Dict[str, float]] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    quality_score: float = 100.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_records": self.total_records,
            "total_columns": self.total_columns,
            "null_counts": self.null_counts,
            "null_percentages": self.null_percentages,
            "duplicate_count": self.duplicate_count,
            "unique_counts": self.unique_counts,
            "data_types": self.data_types,
            "numeric_stats": self.numeric_stats,
            "quality_score": self.quality_score,
            "issues_count": len(self.issues),
            "issues": self.issues[:10],  # Include first 10 issues
        }


class DataQualityChecker:
    """Checks data quality and generates reports."""

    def __init__(
        self,
        null_threshold: float = 0.5,  # Flag if > 50% nulls
        duplicate_threshold: float = 0.1,  # Flag if > 10% duplicates
    ):
        self.null_threshold = null_threshold
        self.duplicate_threshold = duplicate_threshold

    def check(self, df: pl.DataFrame) -> QualityReport:
        """Perform comprehensive quality check on DataFrame.

        Args:
            df: Input DataFrame

        Returns:
            Quality report
        """
        report = QualityReport(
            total_records=len(df),
            total_columns=len(df.columns),
        )

        # Check null values
        self._check_nulls(df, report)

        # Check duplicates
        self._check_duplicates(df, report)

        # Check unique values
        self._check_uniqueness(df, report)

        # Get data types
        self._check_data_types(df, report)

        # Compute numeric statistics
        self._check_numeric_stats(df, report)

        # Calculate quality score
        self._calculate_quality_score(report)

        return report

    def _check_nulls(self, df: pl.DataFrame, report: QualityReport) -> None:
        """Check for null values."""
        for col in df.columns:
            null_count = df[col].null_count()
            report.null_counts[col] = null_count

            null_pct = (null_count / report.total_records) * 100
            report.null_percentages[col] = null_pct

            # Flag high null percentage
            if null_pct > self.null_threshold * 100:
                report.issues.append(
                    f"Column '{col}' has {null_pct:.1f}% null values (threshold: {self.null_threshold * 100}%)"
                )

    def _check_duplicates(self, df: pl.DataFrame, report: QualityReport) -> None:
        """Check for duplicate rows."""
        unique_count = df.unique().height
        duplicate_count = report.total_records - unique_count
        report.duplicate_count = duplicate_count

        duplicate_pct = (duplicate_count / report.total_records) if report.total_records > 0 else 0

        if duplicate_pct > self.duplicate_threshold:
            report.issues.append(
                f"Found {duplicate_count:,} duplicate rows ({duplicate_pct * 100:.1f}% of data)"
            )

    def _check_uniqueness(self, df: pl.DataFrame, report: QualityReport) -> None:
        """Check unique value counts per column."""
        for col in df.columns:
            unique_count = df[col].n_unique()
            report.unique_counts[col] = unique_count

            # Flag low cardinality (might be categorical)
            if unique_count == 1:
                report.issues.append(f"Column '{col}' has only one unique value (constant)")
            elif unique_count == report.total_records and report.total_records > 100:
                report.issues.append(f"Column '{col}' has all unique values (possible ID column)")

    def _check_data_types(self, df: pl.DataFrame, report: QualityReport) -> None:
        """Record data types."""
        for col in df.columns:
            report.data_types[col] = str(df[col].dtype)

    def _check_numeric_stats(self, df: pl.DataFrame, report: QualityReport) -> None:
        """Compute statistics for numeric columns."""
        numeric_types = [pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float32, pl.Float64]

        for col in df.columns:
            if df[col].dtype in numeric_types:
                try:
                    stats = {
                        "mean": float(df[col].mean()),
                        "std": float(df[col].std()),
                        "min": float(df[col].min()),
                        "max": float(df[col].max()),
                        "median": float(df[col].median()),
                    }
                    report.numeric_stats[col] = stats

                    # Check for outliers using IQR method
                    q1 = df[col].quantile(0.25)
                    q3 = df[col].quantile(0.75)
                    iqr = q3 - q1
                    lower_bound = q1 - 1.5 * iqr
                    upper_bound = q3 + 1.5 * iqr

                    outliers = df.filter(
                        (pl.col(col) < lower_bound) | (pl.col(col) > upper_bound)
                    ).height

                    if outliers > 0:
                        outlier_pct = (outliers / report.total_records) * 100
                        report.issues.append(
                            f"Column '{col}' has {outliers:,} outliers ({outlier_pct:.1f}%)"
                        )

                except Exception:
                    # Skip if statistics cannot be computed
                    pass

    def _calculate_quality_score(self, report: QualityReport) -> None:
        """Calculate overall quality score (0-100)."""
        penalties = 0

        # Penalize for null values (max 30 points)
        avg_null_pct = sum(report.null_percentages.values()) / len(report.null_percentages) if report.null_percentages else 0
        penalties += min(30, avg_null_pct * 0.3)

        # Penalize for duplicates (max 20 points)
        duplicate_pct = (report.duplicate_count / report.total_records * 100) if report.total_records > 0 else 0
        penalties += min(20, duplicate_pct * 2)

        # Penalize for issues (max 50 points)
        penalties += min(50, len(report.issues) * 5)

        report.quality_score = max(0, 100 - penalties)

    def validate_schema(
        self,
        df: pl.DataFrame,
        expected_columns: List[str],
        expected_types: Optional[Dict[str, type]] = None,
    ) -> tuple[bool, List[str]]:
        """Validate DataFrame schema.

        Args:
            df: Input DataFrame
            expected_columns: List of expected column names
            expected_types: Optional dict mapping column names to expected types

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check for missing columns
        missing_cols = set(expected_columns) - set(df.columns)
        if missing_cols:
            errors.append(f"Missing columns: {missing_cols}")

        # Check for extra columns
        extra_cols = set(df.columns) - set(expected_columns)
        if extra_cols:
            errors.append(f"Unexpected columns: {extra_cols}")

        # Check types if provided
        if expected_types:
            for col, expected_type in expected_types.items():
                if col in df.columns:
                    actual_type = df[col].dtype
                    if actual_type != expected_type:
                        errors.append(
                            f"Column '{col}' has type {actual_type}, expected {expected_type}"
                        )

        return (len(errors) == 0, errors)
