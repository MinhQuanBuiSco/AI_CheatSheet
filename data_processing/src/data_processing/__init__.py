"""Anthropic-level data processing infrastructure.

High-performance, privacy-preserving data processing with monitoring,
analytics, and Mac M4 optimizations.
"""
from .cli.commands import cli


def main():
    """Main entry point."""
    cli()


__version__ = "0.1.0"
__all__ = ["main", "cli"]
