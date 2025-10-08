"""Progress tracking for long-running operations."""

import time

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table


class ProgressTracker:
    """Tracks and displays progress for data processing operations."""

    def __init__(self, enable_rich: bool = True):
        self.enable_rich = enable_rich
        self.console = Console() if enable_rich else None
        self.progress: Progress | None = None
        self._tasks: dict[str, TaskID] = {}
        self._start_time: float | None = None

    def start(self) -> None:
        """Start progress tracking."""
        if not self.enable_rich:
            return

        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
            console=self.console,
        )
        self.progress.start()
        self._start_time = time.time()

    def add_task(
        self,
        name: str,
        description: str,
        total: int,
    ) -> TaskID | None:
        """Add a new task to track.

        Args:
            name: Task name (identifier)
            description: Task description
            total: Total units of work

        Returns:
            Task ID
        """
        if not self.enable_rich or not self.progress:
            print(f"Starting: {description}")
            return None

        task_id = self.progress.add_task(description, total=total)
        self._tasks[name] = task_id
        return task_id

    def update(
        self,
        name: str,
        advance: int = 1,
        description: str | None = None,
    ) -> None:
        """Update task progress.

        Args:
            name: Task name
            advance: Units to advance
            description: Optional new description
        """
        if not self.enable_rich or not self.progress:
            return

        task_id = self._tasks.get(name)
        if task_id is not None:
            if description:
                self.progress.update(task_id, advance=advance, description=description)
            else:
                self.progress.update(task_id, advance=advance)

    def finish(self) -> None:
        """Finish progress tracking and display summary."""
        if not self.enable_rich or not self.progress:
            return

        self.progress.stop()

        # Display summary
        if self._start_time and self.console:
            elapsed = time.time() - self._start_time
            self.console.print(f"\n[bold green]✓[/bold green] Completed in {elapsed:.2f}s")

    def display_summary(self, metrics: dict) -> None:
        """Display a summary table of metrics.

        Args:
            metrics: Dictionary of metrics to display
        """
        if not self.enable_rich:
            print("\nSummary:")
            for key, value in metrics.items():
                print(f"  {key}: {value}")
            return

        table = Table(title="Processing Summary", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        for key, value in metrics.items():
            if isinstance(value, float):
                value_str = f"{value:.2f}"
            elif isinstance(value, int):
                value_str = f"{value:,}"
            else:
                value_str = str(value)
            table.add_row(key, value_str)

        if self.console:
            self.console.print(table)

    def print_info(self, message: str) -> None:
        """Print an info message.

        Args:
            message: Message to print
        """
        if self.enable_rich and self.console:
            self.console.print(f"[blue]ℹ[/blue] {message}")
        else:
            print(f"INFO: {message}")

    def print_success(self, message: str) -> None:
        """Print a success message.

        Args:
            message: Message to print
        """
        if self.enable_rich and self.console:
            self.console.print(f"[bold green]✓[/bold green] {message}")
        else:
            print(f"SUCCESS: {message}")

    def print_error(self, message: str) -> None:
        """Print an error message.

        Args:
            message: Message to print
        """
        if self.enable_rich and self.console:
            self.console.print(f"[bold red]✗[/bold red] {message}")
        else:
            print(f"ERROR: {message}")

    def print_warning(self, message: str) -> None:
        """Print a warning message.

        Args:
            message: Message to print
        """
        if self.enable_rich and self.console:
            self.console.print(f"[bold yellow]⚠[/bold yellow] {message}")
        else:
            print(f"WARNING: {message}")
