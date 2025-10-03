"""CLI commands for data processing."""
import time
from pathlib import Path
from typing import Optional

import click
import polars as pl
from rich.console import Console

from ..core import Pipeline, ProcessorConfig
from ..privacy import Anonymizer, AnonymizationConfig, AuditLogger, AuditEventType
from ..monitoring import MetricsCollector, StructuredLogger, ProgressTracker, LogLevel
from ..analytics import DataClusterer, ClusteringConfig, DataQualityChecker, HierarchyBuilder
from .config import Config


console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Anthropic-level data processing infrastructure.

    High-performance, privacy-preserving data processing with monitoring,
    analytics, and Mac M4 optimizations.
    """
    pass


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("output_dir", type=click.Path())
@click.option("--format", "file_format", default="parquet", help="Input file format (parquet, json, csv)")
@click.option("--workers", default=10, help="Number of worker processes")
@click.option("--chunk-size", default=10000, help="Records per chunk")
@click.option("--enable-pii", is_flag=True, help="Enable PII detection and anonymization")
@click.option("--enable-clustering", is_flag=True, help="Enable data clustering")
@click.option("--text-column", default=None, help="Text column for clustering")
def process(
    input_file: str,
    output_dir: str,
    file_format: str,
    workers: int,
    chunk_size: int,
    enable_pii: bool,
    enable_clustering: bool,
    text_column: Optional[str],
):
    """Process a data file through the pipeline."""
    input_path = Path(input_file)
    output_path = Path(output_dir)

    console.print(f"[bold cyan]Processing {input_path.name}[/bold cyan]")
    console.print(f"  Format: {file_format}")
    console.print(f"  Workers: {workers}")
    console.print(f"  Chunk size: {chunk_size:,}")
    console.print()

    # Initialize components
    config = ProcessorConfig(
        chunk_size=chunk_size,
        num_workers=workers,
        enable_pii_detection=enable_pii,
    )

    pipeline = Pipeline(config)
    metrics = MetricsCollector()
    logger = StructuredLogger(log_file=output_path / "processing.log")
    progress = ProgressTracker(enable_rich=True)
    audit = AuditLogger(output_path / "audit.log")

    # Start processing
    logger.log_operation_start("data_processing", input_file=str(input_path))
    audit.log_data_access(str(input_path))
    metrics.start_processing()
    progress.start()

    try:
        # Add processors
        if enable_pii:
            console.print("[yellow]Enabling PII detection and anonymization[/yellow]")
            anon_config = AnonymizationConfig()
            anonymizer = Anonymizer(anon_config)

            def anonymize_processor(df: pl.DataFrame) -> pl.DataFrame:
                anon_df, stats = anonymizer.anonymize_dataframe(df)
                total_anon = sum(stats.values())
                if total_anon > 0:
                    audit.log_pii_anonymization(str(input_path), total_anon)
                return anon_df

            pipeline.add_processor(anonymize_processor)

        # Process file
        stats = pipeline.process_file(
            input_path,
            output_path,
            file_type=file_format,
            enable_multiprocessing=(workers > 1),
        )

        # Record metrics
        metrics.record_processed(stats.processed_records)
        metrics.record_failed(stats.failed_records)

        # Clustering (optional)
        if enable_clustering and text_column:
            console.print(f"\n[yellow]Performing clustering on '{text_column}'[/yellow]")

            # Load processed data
            output_files = list(output_path.glob("*.parquet"))
            if output_files:
                df = pl.read_parquet(output_files[0])

                cluster_config = ClusteringConfig(num_clusters=5)
                clusterer = DataClusterer(cluster_config)

                clustered_df = clusterer.cluster_dataframe(df, text_column)
                clustered_df.write_parquet(output_path / "clustered.parquet")

                # Get summaries
                summaries = clusterer.get_cluster_summaries(clustered_df, text_column)
                console.print(f"\n[green]Created {len(summaries)} clusters[/green]")

        # Finish
        final_metrics = metrics.finish_processing()
        progress.finish()

        # Log completion
        logger.log_operation_complete(
            "data_processing",
            final_metrics.processing_time_seconds,
            records_processed=final_metrics.records_processed,
        )
        audit.log_data_processing(
            str(input_path),
            final_metrics.records_processed,
        )

        # Display results
        console.print("\n[bold green]✓ Processing Complete[/bold green]\n")
        console.print(metrics.get_summary())

    except Exception as e:
        logger.log_operation_failed("data_processing", e)
        audit.log_error(str(input_path), e)
        console.print(f"\n[bold red]✗ Error: {e}[/bold red]")
        raise


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
def quality_check(input_file: str):
    """Run data quality checks on a file."""
    input_path = Path(input_file)

    console.print(f"[bold cyan]Quality Check: {input_path.name}[/bold cyan]\n")

    # Load data
    if input_path.suffix == ".parquet":
        df = pl.read_parquet(input_path)
    elif input_path.suffix == ".csv":
        df = pl.read_csv(input_path)
    elif input_path.suffix == ".json":
        df = pl.read_json(input_path)
    else:
        console.print(f"[red]Unsupported file format: {input_path.suffix}[/red]")
        return

    # Run quality check
    checker = DataQualityChecker()
    report = checker.check(df)

    # Display results
    console.print(f"[bold]Records:[/bold] {report.total_records:,}")
    console.print(f"[bold]Columns:[/bold] {report.total_columns}")
    console.print(f"[bold]Quality Score:[/bold] {report.quality_score:.1f}/100\n")

    if report.quality_score >= 80:
        console.print("[green]✓ Good data quality[/green]")
    elif report.quality_score >= 60:
        console.print("[yellow]⚠ Moderate data quality[/yellow]")
    else:
        console.print("[red]✗ Poor data quality[/red]")

    if report.issues:
        console.print(f"\n[bold]Issues Found ({len(report.issues)}):[/bold]")
        for issue in report.issues[:10]:
            console.print(f"  • {issue}")
        if len(report.issues) > 10:
            console.print(f"  ... and {len(report.issues) - 10} more")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("text_column")
@click.option("--num-clusters", default=5, help="Number of clusters")
@click.option("--output", default="clusters.parquet", help="Output file")
def cluster(input_file: str, text_column: str, num_clusters: int, output: str):
    """Cluster data based on text embeddings."""
    input_path = Path(input_file)
    output_path = Path(output)

    console.print(f"[bold cyan]Clustering {input_path.name}[/bold cyan]")
    console.print(f"  Text column: {text_column}")
    console.print(f"  Clusters: {num_clusters}\n")

    # Load data
    df = pl.read_parquet(input_path)

    # Cluster
    config = ClusteringConfig(num_clusters=num_clusters)
    clusterer = DataClusterer(config)

    console.print("[yellow]Generating embeddings...[/yellow]")
    clustered_df = clusterer.cluster_dataframe(df, text_column)

    # Save
    clustered_df.write_parquet(output_path)
    console.print(f"\n[green]✓ Saved to {output_path}[/green]")

    # Show summaries
    summaries = clusterer.get_cluster_summaries(clustered_df, text_column)
    console.print(f"\n[bold]Cluster Summaries:[/bold]")
    for cluster_id, summary in summaries.items():
        console.print(f"\n  Cluster {cluster_id}: {summary['size']} records ({summary['percentage']:.1f}%)")
        console.print(f"  Samples:")
        for sample in summary['samples'][:3]:
            console.print(f"    - {sample[:100]}...")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--text-column", required=True, help="Text column to anonymize")
@click.option("--output", default="anonymized.parquet", help="Output file")
@click.option("--method", default="hash", help="Anonymization method (hash, mask, redact)")
def anonymize(input_file: str, text_column: str, output: str, method: str):
    """Anonymize PII in data."""
    input_path = Path(input_file)
    output_path = Path(output)

    console.print(f"[bold cyan]Anonymizing {input_path.name}[/bold cyan]")
    console.print(f"  Method: {method}\n")

    # Load data
    df = pl.read_parquet(input_path)

    # Anonymize
    config = AnonymizationConfig(anonymization_method=method)
    anonymizer = Anonymizer(config)

    console.print("[yellow]Detecting and anonymizing PII...[/yellow]")
    anon_df, stats = anonymizer.anonymize_dataframe(df, [text_column])

    # Save
    anon_df.write_parquet(output_path)

    # Display stats
    total_anonymized = sum(stats.values())
    console.print(f"\n[green]✓ Anonymized {total_anonymized:,} instances of PII[/green]")
    console.print(f"[green]✓ Saved to {output_path}[/green]")


@cli.command()
def info():
    """Display system information."""
    import platform
    import multiprocessing as mp
    import psutil

    console.print("[bold cyan]System Information[/bold cyan]\n")

    console.print(f"[bold]Platform:[/bold] {platform.system()} {platform.release()}")
    console.print(f"[bold]Architecture:[/bold] {platform.machine()}")
    console.print(f"[bold]CPU Cores:[/bold] {mp.cpu_count()}")

    vm = psutil.virtual_memory()
    console.print(f"[bold]Total Memory:[/bold] {vm.total / 1024 / 1024 / 1024:.1f} GB")
    console.print(f"[bold]Available Memory:[/bold] {vm.available / 1024 / 1024 / 1024:.1f} GB")

    # Check for Apple Silicon
    if platform.machine() == "arm64" and platform.system() == "Darwin":
        console.print("\n[green]✓ Running on Apple Silicon (optimizations enabled)[/green]")


if __name__ == "__main__":
    cli()
