"""CLIO Research Infrastructure Demo

Demonstrates privacy-preserving research infrastructure for analyzing
Claude usage logs - exactly what Anthropic's CLIO team does.

This single script showcases all CLIO requirements:
- Privacy-preserving analytics on Claude conversations
- Large-scale clustering and topic discovery
- Monitoring and debugging capabilities
- High-performance processing
"""
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()


def main():
    """Run CLIO demo."""

    # Header
    console.print(Panel.fit(
        "[bold cyan]CLIO Research Infrastructure Demo[/bold cyan]\n\n"
        "[white]Privacy-Preserving Analysis of Claude Usage Logs[/white]\n\n"
        "Demonstrates:\n"
        "  ✓ Privacy-preserving analytics (PII detection & anonymization)\n"
        "  ✓ Large-scale clustering (semantic topic discovery)\n"
        "  ✓ Monitoring & observability (metrics, logging)\n"
        "  ✓ Concurrency debugging (multiprocessing issues)\n"
        "  ✓ Production-ready infrastructure (Docker, K8s, CI/CD)",
        border_style="cyan",
        padding=(1, 2)
    ))

    console.print("\n[bold yellow]Choose a demo:[/bold yellow]\n")
    console.print("[cyan]1.[/cyan] Generate Claude usage logs (simulates CLIO data)")
    console.print("[cyan]2.[/cyan] Privacy-preserving analytics (PII detection, aggregation)")
    console.print("[cyan]3.[/cyan] Concurrency debugging (race conditions, IPC)")
    console.print("[cyan]4.[/cyan] Run all demos")
    console.print("[cyan]5.[/cyan] Quick start guide")
    console.print()

    choice = input("Enter choice (1-5): ").strip()

    if choice == "1":
        console.print("\n[cyan]Running: Generate Claude Usage Logs[/cyan]\n")
        console.print("Command:")
        console.print("[green]python examples/generate_claude_usage_logs.py --conversations 10000[/green]\n")
        import subprocess
        subprocess.run([
            sys.executable,
            "examples/generate_claude_usage_logs.py",
            "--conversations", "10000"
        ])

    elif choice == "2":
        console.print("\n[cyan]Running: Privacy-Preserving Analytics[/cyan]\n")
        console.print("Command:")
        console.print("[green]python examples/privacy_preserving_analytics.py[/green]\n")
        import subprocess
        subprocess.run([sys.executable, "examples/privacy_preserving_analytics.py"])

    elif choice == "3":
        console.print("\n[cyan]Running: Concurrency Debugging Demo[/cyan]\n")
        console.print("Command:")
        console.print("[green]python examples/concurrency_debugging_demo.py[/green]\n")
        import subprocess
        subprocess.run([sys.executable, "examples/concurrency_debugging_demo.py"])

    elif choice == "4":
        console.print("\n[cyan]Running all demos...[/cyan]\n")
        import subprocess

        console.print("[bold]Step 1/3: Generating Claude usage logs...[/bold]")
        subprocess.run([
            sys.executable,
            "examples/generate_claude_usage_logs.py",
            "--conversations", "10000"
        ])

        console.print("\n[bold]Step 2/3: Privacy-preserving analytics...[/bold]")
        subprocess.run([sys.executable, "examples/privacy_preserving_analytics.py"])

        console.print("\n[bold]Step 3/3: Concurrency debugging...[/bold]")
        subprocess.run([sys.executable, "examples/concurrency_debugging_demo.py"])

    elif choice == "5":
        show_quick_start()

    else:
        console.print("[red]Invalid choice[/red]")


def show_quick_start():
    """Show quick start guide."""
    console.print("\n[bold cyan]Quick Start Guide[/bold cyan]\n")

    console.print("[bold]1. Generate Claude Usage Logs:[/bold]")
    console.print("   [green]python examples/generate_claude_usage_logs.py --conversations 10000[/green]")
    console.print("   Creates: demo_data/claude_usage_logs.parquet\n")

    console.print("[bold]2. Analyze with Privacy Preservation:[/bold]")
    console.print("   [green]python examples/privacy_preserving_analytics.py[/green]")
    console.print("   • Detects and anonymizes PII")
    console.print("   • Generates aggregated analytics")
    console.print("   • Clusters by topic\n")

    console.print("[bold]3. Use CLI for Processing:[/bold]")
    console.print("   [green]python -m data_processing process \\[/green]")
    console.print("   [green]    demo_data/claude_usage_logs.parquet \\[/green]")
    console.print("   [green]    output/ --enable-pii --workers 10[/green]\n")

    console.print("[bold]4. Cluster Conversations:[/bold]")
    console.print("   [green]python -m data_processing cluster \\[/green]")
    console.print("   [green]    demo_data/claude_usage_logs.parquet \\[/green]")
    console.print("   [green]    user_message --num-clusters 8[/green]\n")

    console.print("[bold]5. Start API Server:[/bold]")
    console.print("   [green]python -m uvicorn data_processing.api.main:app --reload[/green]")
    console.print("   Visit: http://localhost:8000/docs\n")

    console.print("[bold]6. Learn About Concurrency Debugging:[/bold]")
    console.print("   [green]python examples/concurrency_debugging_demo.py[/green]\n")

    console.print("[bold cyan]Files to Explore:[/bold cyan]")
    console.print("  • README.md - Overview")
    console.print("  • ARCHITECTURE.md - System design")
    console.print("  • CLIO_JD_ANALYSIS.md - How this maps to CLIO job requirements")
    console.print("  • src/data_processing/privacy/ - Privacy preservation code")
    console.print("  • src/data_processing/analytics/ - Clustering & quality checks")
    console.print("  • src/data_processing/monitoring/ - Metrics & logging\n")


if __name__ == "__main__":
    try:
        from rich.console import Console
        from rich.panel import Panel
    except ImportError:
        print("Installing rich...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "rich"], check=True)
        from rich.console import Console
        from rich.panel import Panel

    main()
