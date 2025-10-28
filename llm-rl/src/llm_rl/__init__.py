"""LLM-RL: Production-ready LLM fine-tuning with RL methods."""

__version__ = "0.1.0"

from . import config, models, data, trainers

__all__ = ["config", "models", "data", "trainers"]


def main() -> None:
    """Main entry point for CLI."""
    from .cli import app
    app()
