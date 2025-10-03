"""Complete demonstration of the data processing pipeline.

This demonstrates all major features:
1. High-performance data processing
2. PII detection and anonymization
3. Monitoring and metrics
4. Data clustering
5. Quality checks
6. Mac M4 optimizations
"""
import time
from pathlib import Path
import polars as pl

from data_processing.core import Pipeline, ProcessorConfig
from data_processing.privacy import Anonymizer, AnonymizationConfig, AuditLogger
from data_processing.monitoring import MetricsCollector, StructuredLogger, ProgressTracker
from data_processing.analytics import DataClusterer, ClusteringConfig, DataQualityChecker
from data_processing.utils import MemoryMonitor, get_optimal_workers


# Define processor at module level for multiprocessing compatibility
def add_processing_timestamp(df: pl.DataFrame) -> pl.DataFrame:
    """Add processing timestamp to dataframe."""
    return df.with_columns(
        pl.lit(time.time()).alias("processed_at")
    )


def main():
    """Run complete demonstration pipeline."""
    print("=" * 80)
    print("ANTHROPIC-LEVEL DATA PROCESSING DEMONSTRATION")
    print("=" * 80)
    print()

    # Setup
    input_file = Path("demo_data/customers_large.parquet")
    output_dir = Path("demo_output")
    output_dir.mkdir(exist_ok=True)

    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}")
        print("Please run: python examples/generate_synthetic_data.py")
        return

    # Load data
    print("📊 Loading data...")
    df = pl.read_parquet(input_file)
    print(f"  Records: {len(df):,}")
    print(f"  Columns: {len(df.columns)}")
    print(f"  Size: {input_file.stat().st_size / 1024 / 1024:.1f} MB")
    print()

    # ==========================================================================
    # 1. DATA QUALITY CHECK
    # ==========================================================================
    print("1️⃣  DATA QUALITY CHECK")
    print("-" * 80)

    checker = DataQualityChecker()
    report = checker.check(df)

    print(f"Quality Score: {report.quality_score:.1f}/100")
    print(f"Null Values: {sum(report.null_counts.values()):,}")
    print(f"Duplicate Rows: {report.duplicate_count:,}")
    print(f"Issues Found: {len(report.issues)}")

    if report.issues:
        print("\nTop Issues:")
        for issue in report.issues[:5]:
            print(f"  • {issue}")

    print()

    # ==========================================================================
    # 2. PRIVACY & ANONYMIZATION
    # ==========================================================================
    print("2️⃣  PRIVACY & ANONYMIZATION")
    print("-" * 80)

    # Initialize privacy components
    anon_config = AnonymizationConfig(anonymization_method="hash")
    anonymizer = Anonymizer(anon_config)
    audit_logger = AuditLogger(output_dir / "audit.log")

    # Anonymize PII
    print("Detecting PII in text columns...")
    text_columns = ["customer_name", "email", "phone", "message"]

    start_time = time.time()
    anonymized_df, anon_stats = anonymizer.anonymize_dataframe(df, text_columns)
    elapsed = time.time() - start_time

    total_pii = sum(anon_stats.values())
    print(f"  PII Instances Found: {total_pii:,}")
    print(f"  Anonymization Time: {elapsed:.2f}s")
    print(f"  Throughput: {len(df) / elapsed:,.0f} records/sec")

    for col, count in anon_stats.items():
        if count > 0:
            print(f"    - {col}: {count:,}")

    # Log to audit trail
    audit_logger.log_pii_anonymization(str(input_file), total_pii)

    print()

    # ==========================================================================
    # 3. HIGH-PERFORMANCE PROCESSING
    # ==========================================================================
    print("3️⃣  HIGH-PERFORMANCE PROCESSING")
    print("-" * 80)

    # Get optimal workers for Mac M4
    optimal_workers = get_optimal_workers("cpu")
    print(f"Optimal Workers (Mac M4): {optimal_workers}")

    # Initialize pipeline
    config = ProcessorConfig(
        chunk_size=10_000,
        num_workers=optimal_workers,
        enable_pii_detection=True,
    )

    pipeline = Pipeline(config)
    metrics = MetricsCollector()
    memory_monitor = MemoryMonitor()

    # Add custom processor (defined at module level for pickling)
    pipeline.add_processor(add_processing_timestamp)

    # Save anonymized data for processing
    temp_file = output_dir / "temp_input.parquet"
    anonymized_df.write_parquet(temp_file)

    # Process
    print("\nProcessing data...")
    metrics.start_processing()

    stats = pipeline.process_file(
        temp_file,
        output_dir / "processed",
        file_type="parquet",
        enable_multiprocessing=True,
    )

    final_metrics = metrics.finish_processing()

    print(f"\n  Records Processed: {final_metrics.records_processed:,}")
    print(f"  Processing Time: {final_metrics.processing_time_seconds:.2f}s")
    print(f"  Throughput: {final_metrics.throughput_records_per_sec:,.0f} records/sec")
    print(f"  Peak Memory: {final_metrics.peak_memory_mb:.1f} MB")
    print(f"  CPU Usage: {final_metrics.cpu_percent:.1f}%")

    print()

    # ==========================================================================
    # 4. DATA CLUSTERING
    # ==========================================================================
    print("4️⃣  DATA CLUSTERING & ANALYTICS")
    print("-" * 80)

    # Use smaller sample for clustering (embeddings are expensive)
    sample_df = anonymized_df.sample(n=min(1000, len(anonymized_df)))

    cluster_config = ClusteringConfig(num_clusters=5)
    clusterer = DataClusterer(cluster_config)

    print("Generating embeddings and clustering messages...")
    start_time = time.time()

    clustered_df = clusterer.cluster_dataframe(sample_df, "message")

    elapsed = time.time() - start_time
    print(f"  Clustering Time: {elapsed:.2f}s")

    # Get cluster summaries
    summaries = clusterer.get_cluster_summaries(clustered_df, "message")

    print(f"\nClusters Created: {len(summaries)}")
    for cluster_id, summary in summaries.items():
        print(f"\n  Cluster {cluster_id}:")
        print(f"    Size: {summary['size']} ({summary['percentage']:.1f}%)")
        print(f"    Sample: {summary['samples'][0][:80]}...")

    print()

    # ==========================================================================
    # 5. MONITORING & METRICS SUMMARY
    # ==========================================================================
    print("5️⃣  MONITORING & METRICS SUMMARY")
    print("-" * 80)

    print(metrics.get_summary())
    print()

    # ==========================================================================
    # 6. AUDIT TRAIL
    # ==========================================================================
    print("6️⃣  AUDIT TRAIL")
    print("-" * 80)

    events = audit_logger.query_events()
    print(f"Total Audit Events: {len(events)}")

    if events:
        print("\nRecent Events:")
        for event in events[-5:]:
            print(f"  [{event.timestamp}] {event.event_type.value}: {event.action}")

    print()

    # ==========================================================================
    # CLEANUP & RESULTS
    # ==========================================================================
    print("=" * 80)
    print("✅ DEMONSTRATION COMPLETE")
    print("=" * 80)
    print()
    print(f"Output Directory: {output_dir.absolute()}")
    print(f"  - Processed data: {output_dir / 'processed'}")
    print(f"  - Audit log: {output_dir / 'audit.log'}")
    print()
    print("Key Achievements:")
    print(f"  ✓ Processed {final_metrics.records_processed:,} records")
    print(f"  ✓ Detected and anonymized {total_pii:,} PII instances")
    print(f"  ✓ Quality score: {report.quality_score:.1f}/100")
    print(f"  ✓ Throughput: {final_metrics.throughput_records_per_sec:,.0f} records/sec")
    print(f"  ✓ Created {len(summaries)} data clusters")
    print()


if __name__ == "__main__":
    main()
