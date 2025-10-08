"""CLI commands for data processing."""

import time
from pathlib import Path

import click
import polars as pl
from rich.console import Console

from ..analytics import ClusteringConfig, DataClusterer, DataQualityChecker
from ..core import Pipeline, ProcessorConfig
from ..monitoring import MetricsCollector, ProgressTracker, StructuredLogger
from ..privacy import AnonymizationConfig, Anonymizer, AuditLogger

console = Console()


# Module-level processor functions (must be at module level for multiprocessing pickling)
class AnonymizeProcessor:
    """Anonymization processor that can be pickled for multiprocessing."""

    def __init__(
        self, anon_config: AnonymizationConfig, audit_logger: AuditLogger, input_path: str
    ):
        self.anon_config = anon_config
        self.audit_logger = audit_logger
        self.input_path = input_path
        self.anonymizer = Anonymizer(anon_config)

    def __call__(self, df: pl.DataFrame) -> pl.DataFrame:
        """Process a chunk with anonymization."""
        anon_df, stats = self.anonymizer.anonymize_dataframe(df)
        total_anon = sum(stats.values())
        if total_anon > 0:
            self.audit_logger.log_pii_anonymization(self.input_path, total_anon)
        return anon_df


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """Anthropic-level data processing infrastructure.

    High-performance, privacy-preserving data processing with monitoring,
    analytics, and Mac M4 optimizations.
    """
    pass


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("output_dir", type=click.Path())
@click.option(
    "--format", "file_format", default="parquet", help="Input file format (parquet, json, csv)"
)
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
    text_column: str | None,
) -> None:
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
            anonymize_processor = AnonymizeProcessor(anon_config, audit, str(input_path))
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
def quality_check(input_file: str) -> None:
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
def cluster(input_file: str, text_column: str, num_clusters: int, output: str) -> None:
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
    console.print("\n[bold]Cluster Summaries:[/bold]")
    for cluster_id, summary in summaries.items():
        console.print(
            f"\n  Cluster {cluster_id}: {summary['size']} records ({summary['percentage']:.1f}%)"
        )
        console.print("  Samples:")
        for sample in summary["samples"][:3]:
            console.print(f"    - {sample[:100]}...")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--text-column", required=True, help="Text column to anonymize")
@click.option("--output", default="anonymized.parquet", help="Output file")
@click.option("--method", default="hash", help="Anonymization method (hash, mask, redact)")
def anonymize(input_file: str, text_column: str, output: str, method: str) -> None:
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
def info() -> None:
    """Display system information."""
    import multiprocessing as mp
    import platform

    import psutil  # type: ignore[import-untyped]

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


# Minikube Demo Commands
@cli.group()
def demo() -> None:
    """Minikube demo management commands."""
    pass


@demo.command()
@click.option("--memory", default="8g", help="Memory allocation (default: 8g)")
@click.option("--cpus", default=4, help="CPU cores (default: 4)")
def start(memory: str, cpus: int) -> None:
    """Start Minikube cluster for demo."""
    import subprocess

    console.print("[bold cyan]Starting Minikube cluster...[/bold cyan]\n")

    try:
        # Start Minikube
        cmd = ["minikube", "start", f"--memory={memory}", f"--cpus={cpus}", "--driver=docker"]
        subprocess.run(cmd, check=True)

        console.print("\n[green]✓ Minikube started successfully![/green]")
        console.print("\nNext steps:")
        console.print("  1. data-processing demo deploy")
        console.print("  2. data-processing demo test")

    except subprocess.CalledProcessError as e:
        console.print(f"\n[red]✗ Failed to start Minikube: {e}[/red]")
        raise


@demo.command()
def stop() -> None:
    """Stop Minikube cluster."""
    import subprocess

    console.print("[bold cyan]Stopping Minikube...[/bold cyan]")

    try:
        subprocess.run(["minikube", "stop"], check=True)
        console.print("[green]✓ Minikube stopped[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗ Failed: {e}[/red]")


@demo.command()
def deploy() -> None:
    """Deploy all services to Minikube."""
    import subprocess

    console.print("[bold cyan]Deploying to Minikube...[/bold cyan]\n")

    try:
        # Run deploy script
        result = subprocess.run(
            ["bash", "scripts/deploy.sh"], cwd=Path.cwd(), capture_output=True, text=True
        )

        if result.returncode == 0:
            console.print("\n[green]✓ Deployment complete![/green]")
            console.print("\nAccess points:")
            console.print("  • API:        http://localhost:8000")
            console.print("  • Grafana:    http://localhost:3000 (admin/admin)")
            console.print("  • Prometheus: http://localhost:9090")
            console.print("  • Spark UI:   http://localhost:8080")
            console.print("  • MinIO:      http://localhost:9001 (minioadmin/minioadmin)")
        else:
            console.print("[red]✗ Deployment failed[/red]")
            console.print(result.stderr)

    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")


@demo.command()
def test() -> None:
    """Run end-to-end test on the demo."""
    import subprocess

    console.print("[bold cyan]Running end-to-end test...[/bold cyan]\n")

    try:
        result = subprocess.run(
            ["bash", "scripts/test.sh"], cwd=Path.cwd(), capture_output=False, text=True
        )

        if result.returncode == 0:
            console.print("\n[green]✓ Test passed![/green]")
        else:
            console.print("\n[red]✗ Test failed[/red]")

    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")


@demo.command()
def status() -> None:
    """Show status of all services."""
    import subprocess

    console.print("[bold cyan]Service Status[/bold cyan]\n")

    try:
        # Minikube status
        result = subprocess.run(["minikube", "status"], capture_output=True, text=True)
        console.print("[bold]Minikube:[/bold]")
        console.print(result.stdout)

        # Kubernetes pods
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", "data-processing"], capture_output=True, text=True
        )
        console.print("\n[bold]Pods:[/bold]")
        console.print(result.stdout)

        # Port forwards
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        port_forwards = [line for line in result.stdout.split("\n") if "port-forward" in line]
        if port_forwards:
            console.print("\n[bold]Port Forwards:[/bold]")
            for pf in port_forwards:
                console.print(f"  {pf.split()[-1]}")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗ Error: {e}[/red]")


@demo.command()
@click.option(
    "--service", default="api", help="Service to view logs (api, spark, minio, prometheus, grafana)"
)
@click.option("--follow", "-f", is_flag=True, help="Follow logs")
@click.option("--tail", default=100, help="Number of lines to show")
def logs(service: str, follow: bool, tail: int) -> None:
    """View logs from demo services."""
    import subprocess

    service_map = {
        "api": "component=api",
        "spark": "component=spark",
        "minio": "app=minio",
        "prometheus": "app=prometheus",
        "grafana": "app=grafana",
    }

    label = service_map.get(service)
    if not label:
        console.print(f"[red]Unknown service: {service}[/red]")
        console.print(f"Available services: {', '.join(service_map.keys())}")
        return

    cmd = ["kubectl", "logs", "-n", "data-processing", "-l", label, f"--tail={tail}"]
    if follow:
        cmd.append("-f")

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        pass


@demo.command()
def clean() -> None:
    """Clean up demo resources."""
    import subprocess

    console.print("[bold cyan]Cleaning up demo resources...[/bold cyan]\n")

    try:
        # Delete namespace
        subprocess.run(["kubectl", "delete", "namespace", "data-processing"], check=True)
        console.print("[green]✓ Namespace deleted[/green]")

        # Kill port forwards
        subprocess.run(["pkill", "-f", "kubectl port-forward"])
        console.print("[green]✓ Port forwards stopped[/green]")

        console.print("\n[green]✓ Cleanup complete![/green]")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗ Error: {e}[/red]")


@demo.command()
def dashboard() -> None:
    """Open Grafana dashboard in browser."""
    import subprocess
    import webbrowser

    console.print("[bold cyan]Opening Grafana dashboard...[/bold cyan]")

    # Check if port forward is running
    result = subprocess.run(["ps", "aux"], capture_output=True, text=True)

    if "grafana" not in result.stdout or "port-forward" not in result.stdout:
        console.print("[yellow]Port forward not found, starting...[/yellow]")
        subprocess.Popen(
            ["kubectl", "port-forward", "-n", "data-processing", "svc/grafana", "3000:3000"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)

    webbrowser.open("http://localhost:3000")
    console.print("[green]✓ Dashboard opened in browser[/green]")
    console.print("Default credentials: admin / admin")


if __name__ == "__main__":
    cli()
