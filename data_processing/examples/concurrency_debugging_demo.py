"""Concurrency debugging demonstration for CLIO.

This script demonstrates debugging complex concurrency issues in data processing pipelines:
- Race conditions in multiprocessing
- Shared state problems
- Inter-process communication errors
- Debugging techniques and solutions

This addresses the CLIO JD requirement: "Debug data processing pipelines that may
encounter difficult issues, such as concurrency inefficiencies or errors obscured by
inter-process communications."
"""
import time
import multiprocessing as mp
from pathlib import Path
from typing import List
import polars as pl
from rich.console import Console
from rich.panel import Panel
from rich import print as rprint

console = Console()


# ============================================================================
# BUGGY VERSION - Demonstrates Common Concurrency Issues
# ============================================================================

class BuggySharedCounter:
    """Demonstrates race condition bug."""

    def __init__(self):
        self.count = 0  # BUG: Not thread-safe!

    def increment(self):
        temp = self.count
        time.sleep(0.0001)  # Simulate processing time
        self.count = temp + 1


def buggy_worker(worker_id: int, shared_counter: BuggySharedCounter, items: List[int]):
    """Buggy worker that causes race conditions."""
    console.print(f"[yellow]Worker {worker_id} starting (BUGGY version)[/yellow]")

    for item in items:
        # BUG: Multiple workers increment shared counter without synchronization
        shared_counter.increment()

        # Simulate processing
        time.sleep(0.001)

    console.print(f"[yellow]Worker {worker_id} done[/yellow]")


def demonstrate_race_condition():
    """Demonstrate race condition bug."""
    console.print("\n[bold red]❌ BUGGY VERSION: Race Condition[/bold red]\n")

    console.print("[yellow]Issue: Multiple processes incrementing shared counter without locks[/yellow]")
    console.print("[yellow]Expected: Counter = 100[/yellow]")
    console.print("[yellow]Actual: Counter will be < 100 (race condition!)[/yellow]\n")

    # Create shared counter (buggy)
    counter = BuggySharedCounter()

    # Create workers
    num_workers = 10
    items_per_worker = 10

    # Simulate multiprocessing scenario (simplified with threads for demo)
    import threading

    threads = []
    for i in range(num_workers):
        items = list(range(items_per_worker))
        t = threading.Thread(target=buggy_worker, args=(i, counter, items))
        threads.append(t)
        t.start()

    # Wait for all workers
    for t in threads:
        t.join()

    expected = num_workers * items_per_worker
    actual = counter.count

    console.print(f"\n[bold]Results:[/bold]")
    console.print(f"  Expected count: {expected}")
    console.print(f"  Actual count: {actual}")

    if actual < expected:
        console.print(f"  [red]❌ Lost {expected - actual} increments due to race condition![/red]")
    else:
        console.print(f"  [green]✓ Counts match (got lucky this time!)[/green]")

    console.print("\n[red]🐛 Bug Explanation:[/red]")
    console.print("  Multiple threads read the same value, increment it, and write back.")
    console.print("  This causes lost updates when operations interleave:")
    console.print("    Thread 1: Read count=5")
    console.print("    Thread 2: Read count=5  (both see 5!)")
    console.print("    Thread 1: Write count=6")
    console.print("    Thread 2: Write count=6 (overwrites Thread 1's update!)")


# ============================================================================
# FIXED VERSION - Proper Synchronization
# ============================================================================

class FixedSharedCounter:
    """Fixed version with proper synchronization."""

    def __init__(self):
        self.count = mp.Value('i', 0)  # FIX: Shared memory with lock
        self.lock = mp.Lock()  # FIX: Explicit lock

    def increment(self):
        with self.lock:  # FIX: Atomic operation
            temp = self.count.value
            time.sleep(0.0001)
            self.count.value = temp + 1


def fixed_worker(worker_id: int, shared_counter: FixedSharedCounter, items: List[int]):
    """Fixed worker with proper synchronization."""
    console.print(f"[green]Worker {worker_id} starting (FIXED version)[/green]")

    for item in items:
        # FIX: Synchronized increment
        shared_counter.increment()

        # Simulate processing
        time.sleep(0.001)

    console.print(f"[green]Worker {worker_id} done[/green]")


def demonstrate_fixed_version():
    """Demonstrate fixed version with proper synchronization."""
    console.print("\n[bold green]✓ FIXED VERSION: Proper Synchronization[/bold green]\n")

    console.print("[green]Solution: Use multiprocessing.Lock() for synchronization[/green]")
    console.print("[green]Expected: Counter = 100[/green]")
    console.print("[green]Actual: Counter will be exactly 100[/green]\n")

    # Create shared counter (fixed)
    counter = FixedSharedCounter()

    # Create workers
    num_workers = 10
    items_per_worker = 10

    # Simulate with threads (in real code, use multiprocessing.Process)
    import threading

    threads = []
    for i in range(num_workers):
        items = list(range(items_per_worker))
        t = threading.Thread(target=fixed_worker, args=(i, counter, items))
        threads.append(t)
        t.start()

    # Wait for all workers
    for t in threads:
        t.join()

    expected = num_workers * items_per_worker
    actual = counter.count.value

    console.print(f"\n[bold]Results:[/bold]")
    console.print(f"  Expected count: {expected}")
    console.print(f"  Actual count: {actual}")

    if actual == expected:
        console.print(f"  [green]✓ Perfect! No lost updates[/green]")
    else:
        console.print(f"  [red]❌ Still lost {expected - actual} increments[/red]")

    console.print("\n[green]✓ Fix Explanation:[/green]")
    console.print("  Using multiprocessing.Lock() ensures atomic operations:")
    console.print("    1. Worker acquires lock")
    console.print("    2. Reads current value")
    console.print("    3. Increments")
    console.print("    4. Writes back")
    console.print("    5. Releases lock")
    console.print("  Other workers must wait their turn → No race condition!")


# ============================================================================
# Inter-Process Communication Debugging
# ============================================================================

def buggy_ipc_worker(queue: mp.Queue, data: List[int]):
    """Demonstrates IPC error - forgetting to put results in queue."""
    # BUG: Process data but forget to send results back!
    result = sum(data)
    # BUG: Missing queue.put(result)
    console.print(f"[yellow]Worker processed {len(data)} items, sum={result}[/yellow]")
    # Parent will hang waiting for result that never comes!


def fixed_ipc_worker(queue: mp.Queue, data: List[int]):
    """Fixed version - properly sends results back."""
    result = sum(data)
    queue.put(result)  # FIX: Always send result back
    console.print(f"[green]Worker processed {len(data)} items, sum={result}, sent to queue[/green]")


def demonstrate_ipc_debugging():
    """Demonstrate inter-process communication debugging."""
    console.print("\n[bold cyan]Debugging Inter-Process Communication[/bold cyan]\n")

    # Buggy version
    console.print("[bold red]❌ BUGGY: Forgetting to send results[/bold red]")
    console.print("[yellow]This will hang waiting for results...[/yellow]\n")

    queue = mp.Queue()
    data = list(range(100))

    # Show what would happen (with timeout to avoid actual hang)
    console.print("[yellow]Simulating buggy worker (would hang without timeout)...[/yellow]")
    console.print("[yellow]Worker calculates result but doesn't send it back![/yellow]")
    console.print("[yellow]Parent waits forever with queue.get()...[/yellow]\n")

    # Fixed version
    console.print("[bold green]✓ FIXED: Proper result communication[/bold green]\n")

    queue = mp.Queue()
    p = mp.Process(target=fixed_ipc_worker, args=(queue, data))
    p.start()
    p.join()

    # Get result with timeout
    try:
        result = queue.get(timeout=2.0)
        console.print(f"[green]✓ Received result from worker: {result}[/green]")
    except:
        console.print(f"[red]❌ Timeout! Worker didn't send result[/red]")

    console.print("\n[green]✓ Debugging Tips for IPC:[/green]")
    console.print("  1. Always use queue.put() to send results")
    console.print("  2. Use queue.get(timeout=X) to avoid hanging")
    console.print("  3. Check queue.empty() before get()")
    console.print("  4. Log when data is sent/received")
    console.print("  5. Use queue.qsize() to monitor queue depth")


# ============================================================================
# Performance Debugging - Identifying Bottlenecks
# ============================================================================

def demonstrate_performance_debugging():
    """Demonstrate debugging performance issues in concurrent processing."""
    console.print("\n[bold cyan]Performance Debugging: Finding Bottlenecks[/bold cyan]\n")

    console.print("[yellow]Scenario: Processing slows down with more workers[/yellow]")
    console.print("[yellow]Expected: Linear speedup with more workers[/yellow]")
    console.print("[yellow]Actual: Performance degrades[/yellow]\n")

    # Simulate data
    num_items = 1000

    console.print("[bold]Testing with different worker counts:[/bold]\n")

    for num_workers in [1, 2, 4, 8]:
        start = time.time()

        # Simulate work split across workers
        items_per_worker = num_items // num_workers
        simulated_time = items_per_worker * 0.001  # Simulate processing

        # Add overhead for lock contention (gets worse with more workers)
        lock_overhead = num_workers * 0.1  # Simulated lock contention

        total_time = simulated_time + lock_overhead

        throughput = num_items / total_time

        console.print(f"  Workers: {num_workers:2d} | Time: {total_time:.3f}s | Throughput: {throughput:.0f} items/s")

        if num_workers > 1 and throughput < 1000:
            console.print(f"    [red]⚠ Lock contention detected![/red]")

    console.print("\n[yellow]🐛 Problem Identified: Lock Contention[/yellow]")
    console.print("  Too many workers fighting for the same lock")
    console.print("  Solution: Reduce shared state, use lock-free data structures\n")

    console.print("[green]✓ Solutions:[/green]")
    console.print("  1. Use lock-free data structures (queue.Queue)")
    console.print("  2. Minimize shared state")
    console.print("  3. Use worker-local accumulators, merge at end")
    console.print("  4. Profile with cProfile to find hotspots")
    console.print("  5. Monitor with multiprocessing.Manager metrics")


# ============================================================================
# Real-World Example: Pipeline Debugging
# ============================================================================

def demonstrate_pipeline_debugging():
    """Demonstrate debugging a real data processing pipeline."""
    console.print("\n[bold cyan]Real-World: Debugging Data Pipeline[/bold cyan]\n")

    console.print("[bold]Common Issues in Production:[/bold]\n")

    issues = [
        ("[red]1. Silent failures[/red]", "Workers crash without error messages", "Use try/except with logging"),
        ("[yellow]2. Memory leaks[/yellow]", "Workers consume increasing memory", "Monitor with psutil, cleanup resources"),
        ("[red]3. Deadlocks[/red]", "Workers hang waiting for each other", "Use timeouts, avoid circular dependencies"),
        ("[yellow]4. Load imbalance[/yellow]", "Some workers idle while others overloaded", "Use dynamic work queues"),
        ("[red]5. Resource exhaustion[/red]", "Too many open files/connections", "Limit workers, use connection pools"),
    ]

    for issue, desc, solution in issues:
        console.print(f"{issue}")
        console.print(f"  Problem: {desc}")
        console.print(f"  [green]Solution: {solution}[/green]\n")

    console.print("[bold green]✓ Debugging Toolkit:[/bold green]")
    console.print("  • Structured logging (JSON) for parsing")
    console.print("  • Prometheus metrics for monitoring")
    console.print("  • Distributed tracing (trace IDs)")
    console.print("  • Health checks per worker")
    console.print("  • Graceful shutdown handlers")


# ============================================================================
# Main Demo
# ============================================================================

def main():
    """Run complete concurrency debugging demo."""
    console.print(Panel.fit(
        "[bold cyan]Concurrency Debugging for CLIO[/bold cyan]\n\n"
        "Demonstrating debugging of:\n"
        "• Race conditions\n"
        "• Inter-process communication errors\n"
        "• Performance bottlenecks\n"
        "• Production pipeline issues\n\n"
        "[yellow]This addresses CLIO JD requirement:\n"
        "\"Debug pipelines with concurrency inefficiencies or\n"
        "errors obscured by inter-process communications\"[/yellow]",
        border_style="cyan"
    ))

    # Demo 1: Race condition
    demonstrate_race_condition()

    # Demo 2: Fixed version
    demonstrate_fixed_version()

    # Demo 3: IPC debugging
    demonstrate_ipc_debugging()

    # Demo 4: Performance debugging
    demonstrate_performance_debugging()

    # Demo 5: Pipeline debugging
    demonstrate_pipeline_debugging()

    # Summary
    console.print("\n" + "="*70)
    console.print(Panel.fit(
        "[bold green]Key Takeaways: Concurrency Debugging[/bold green]\n\n"
        "1. [green]Race Conditions:[/green] Use locks/semaphores for shared state\n"
        "2. [green]IPC Errors:[/green] Always send results, use timeouts\n"
        "3. [green]Performance:[/green] Profile, minimize contention\n"
        "4. [green]Production:[/green] Log everything, monitor metrics\n"
        "5. [green]Debugging:[/green] Reproduce, isolate, fix, verify\n\n"
        "[cyan]These skills are essential for maintaining CLIO's\n"
        "large-scale, concurrent data processing infrastructure![/cyan]",
        border_style="green"
    ))
    console.print("="*70 + "\n")


if __name__ == "__main__":
    # Avoid issues with multiprocessing on macOS
    mp.set_start_method('fork', force=True)

    main()
