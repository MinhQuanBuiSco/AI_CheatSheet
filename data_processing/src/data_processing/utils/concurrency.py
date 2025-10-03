"""Concurrency utilities optimized for Mac M4."""
import multiprocessing as mp
import os
import platform
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Optional


def get_optimal_workers(task_type: str = "cpu") -> int:
    """Get optimal number of workers for Mac M4.

    The M4 has 12 cores (4 performance + 8 efficiency cores).
    This function optimizes worker count based on task type.

    Args:
        task_type: Type of task ("cpu", "io", "mixed")

    Returns:
        Optimal number of workers
    """
    cpu_count = mp.cpu_count()

    # Detect if we're on Apple Silicon
    is_apple_silicon = platform.machine() == "arm64" and platform.system() == "Darwin"

    if task_type == "cpu":
        # For CPU-bound tasks on M4, use performance cores primarily
        # Leave 1-2 cores for system
        if is_apple_silicon and cpu_count >= 12:
            # M4: Use 10 workers (leave 2 for system)
            return min(10, cpu_count - 2)
        return max(1, cpu_count - 2)

    elif task_type == "io":
        # For I/O-bound tasks, can use more workers
        if is_apple_silicon and cpu_count >= 12:
            # Can use more for I/O
            return cpu_count * 2
        return cpu_count * 2

    elif task_type == "mixed":
        # Balanced approach
        if is_apple_silicon and cpu_count >= 12:
            return min(8, cpu_count - 2)
        return max(1, cpu_count // 2)

    return cpu_count


class OptimizedExecutor:
    """Process/Thread pool executor optimized for Mac M4."""

    def __init__(
        self,
        task_type: str = "cpu",
        max_workers: Optional[int] = None,
        use_threads: bool = False,
    ):
        """Initialize executor.

        Args:
            task_type: Type of task ("cpu", "io", "mixed")
            max_workers: Maximum number of workers (auto-detect if None)
            use_threads: Use threads instead of processes
        """
        self.task_type = task_type
        self.max_workers = max_workers or get_optimal_workers(task_type)
        self.use_threads = use_threads

        # Set optimal environment variables for Apple Silicon
        if platform.machine() == "arm64":
            # Use Accelerate framework for numpy/scipy
            os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
            os.environ.setdefault("OMP_NUM_THREADS", "1")

        if use_threads:
            self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        else:
            # Configure multiprocessing for M4
            ctx = mp.get_context("fork")  # fork is faster on macOS
            self.executor = ProcessPoolExecutor(
                max_workers=self.max_workers,
                mp_context=ctx,
            )

    def __enter__(self):
        return self.executor.__enter__()

    def __exit__(self, *args):
        return self.executor.__exit__(*args)

    def submit(self, fn, *args, **kwargs):
        """Submit a task."""
        return self.executor.submit(fn, *args, **kwargs)

    def map(self, fn, *iterables, **kwargs):
        """Map function over iterables."""
        return self.executor.map(fn, *iterables, **kwargs)

    def shutdown(self, wait=True):
        """Shutdown executor."""
        self.executor.shutdown(wait=wait)
