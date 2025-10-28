"""Utility functions for trainer setup and configuration."""

from typing import Optional, Tuple
from pathlib import Path
import logging
import torch
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..config import BaseRLConfig
from ..models import load_model_and_tokenizer
from ..data import DatasetLoader

console = Console()


def setup_logging(config: BaseRLConfig) -> logging.Logger:
    """
    Setup logging configuration.

    Args:
        config: Training configuration

    Returns:
        Logger instance
    """
    log_level = config.logging.log_level.upper()
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    return logging.getLogger("llm_rl")


def print_config(config: BaseRLConfig):
    """
    Print training configuration.

    Args:
        config: Training configuration
    """
    console.print("\n[bold cyan]Training Configuration[/bold cyan]")
    console.print(f"  Method: {config.method.value}")
    console.print(f"  Model: {config.model.model_name_or_path}")
    console.print(f"  Output: {config.training.output_dir}")
    console.print(f"  Epochs: {config.training.num_train_epochs}")
    console.print(f"  Batch size: {config.training.per_device_train_batch_size}")
    console.print(f"  Learning rate: {config.training.learning_rate}")
    console.print(f"  Use PEFT: {config.model.use_peft}\n")


def setup_model_and_data(config: BaseRLConfig):
    """
    Setup model, tokenizer, and datasets.

    Args:
        config: Training configuration

    Returns:
        Tuple of (model, tokenizer, train_dataset, eval_dataset)
    """
    console.print("[bold]Setting up training...[/bold]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Load model and tokenizer
        task = progress.add_task("Loading model and tokenizer...", total=None)
        model, tokenizer = load_model_and_tokenizer(
            model_config=config.model,
            peft_config=config.peft if config.model.use_peft else None,
        )
        progress.update(task, completed=True)

        # Load datasets
        task = progress.add_task("Loading datasets...", total=None)
        dataset_loader = DatasetLoader(config.dataset)
        dataset_loader.load()
        train_dataset, eval_dataset = dataset_loader.get_splits()
        progress.update(task, completed=True)

    console.print("[green]✓ Setup complete![/green]\n")

    # Print dataset info
    console.print("[bold]Dataset Information:[/bold]")
    console.print(f"  Train samples: {len(train_dataset)}")
    if eval_dataset:
        console.print(f"  Eval samples: {len(eval_dataset)}")
    console.print()

    return model, tokenizer, train_dataset, eval_dataset


def save_model_with_config(model, tokenizer, config: BaseRLConfig, output_dir: Optional[str] = None):
    """
    Save trained model with configuration.

    Args:
        model: Trained model
        tokenizer: Tokenizer
        config: Training configuration
        output_dir: Directory to save model (uses config if None)
    """
    save_dir = output_dir or config.training.output_dir
    Path(save_dir).mkdir(parents=True, exist_ok=True)

    console.print(f"[cyan]Saving model to:[/cyan] {save_dir}")

    model.save_pretrained(save_dir)
    tokenizer.save_pretrained(save_dir)

    # Save config
    config.to_yaml(Path(save_dir) / "training_config.yaml")

    console.print("[green]✓ Model saved successfully[/green]")


def cleanup_resources():
    """Cleanup GPU resources."""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
