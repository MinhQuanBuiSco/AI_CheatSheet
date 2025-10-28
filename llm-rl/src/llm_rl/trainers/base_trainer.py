"""Base trainer class for all RL methods."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pathlib import Path
import torch
from transformers import PreTrainedModel, PreTrainedTokenizer
from datasets import Dataset
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..config import BaseRLConfig
from ..models import load_model_and_tokenizer
from ..data import DatasetLoader

console = Console()


class BaseRLTrainer(ABC):
    """
    Abstract base class for all RL trainers.

    All specific RL methods (DPO, PPO, etc.) should inherit from this class.
    """

    def __init__(self, config: BaseRLConfig):
        """
        Initialize base trainer.

        Args:
            config: Configuration for training
        """
        self.config = config
        self.model: Optional[PreTrainedModel] = None
        self.tokenizer: Optional[PreTrainedTokenizer] = None
        self.ref_model: Optional[PreTrainedModel] = None
        self.train_dataset: Optional[Dataset] = None
        self.eval_dataset: Optional[Dataset] = None

        # Setup
        self._setup_logging()
        self._print_config()

    def _setup_logging(self):
        """Setup logging configuration."""
        import logging

        log_level = self.config.logging.log_level.upper()
        logging.basicConfig(
            level=getattr(logging, log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(self.__class__.__name__)

    def _print_config(self):
        """Print training configuration."""
        console.print("\n[bold cyan]Training Configuration[/bold cyan]")
        console.print(f"  Method: {self.config.method.value}")
        console.print(f"  Model: {self.config.model.model_name_or_path}")
        console.print(f"  Output: {self.config.training.output_dir}")
        console.print(f"  Epochs: {self.config.training.num_train_epochs}")
        console.print(f"  Batch size: {self.config.training.per_device_train_batch_size}")
        console.print(f"  Learning rate: {self.config.training.learning_rate}")
        console.print(f"  Use PEFT: {self.config.model.use_peft}\n")

    def setup(self):
        """Setup model, tokenizer, and datasets."""
        console.print("[bold]Setting up training...[/bold]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Load model and tokenizer
            task = progress.add_task("Loading model and tokenizer...", total=None)
            self.model, self.tokenizer = load_model_and_tokenizer(
                model_config=self.config.model,
                peft_config=self.config.peft if self.config.model.use_peft else None,
            )
            progress.update(task, completed=True)

            # Load datasets
            task = progress.add_task("Loading datasets...", total=None)
            dataset_loader = DatasetLoader(self.config.dataset)
            dataset_loader.load()
            self.train_dataset, self.eval_dataset = dataset_loader.get_splits()
            progress.update(task, completed=True)

            # Preprocess datasets
            task = progress.add_task("Preprocessing datasets...", total=None)
            self._preprocess_datasets()
            progress.update(task, completed=True)

        console.print("[green]✓ Setup complete![/green]\n")

        # Print dataset info
        self._print_dataset_info()

    def _print_dataset_info(self):
        """Print dataset information."""
        console.print("[bold]Dataset Information:[/bold]")
        console.print(f"  Train samples: {len(self.train_dataset)}")
        if self.eval_dataset:
            console.print(f"  Eval samples: {len(self.eval_dataset)}")
        console.print()

    @abstractmethod
    def _preprocess_datasets(self):
        """
        Preprocess datasets for specific RL method.

        Must be implemented by subclasses.
        """
        pass

    @abstractmethod
    def train(self) -> Dict[str, Any]:
        """
        Run training loop.

        Must be implemented by subclasses.

        Returns:
            Training metrics and results
        """
        pass

    def save_model(self, output_dir: Optional[str] = None):
        """
        Save trained model.

        Args:
            output_dir: Directory to save model (uses config if None)
        """
        save_dir = output_dir or self.config.training.output_dir
        Path(save_dir).mkdir(parents=True, exist_ok=True)

        console.print(f"[cyan]Saving model to:[/cyan] {save_dir}")

        self.model.save_pretrained(save_dir)
        self.tokenizer.save_pretrained(save_dir)

        # Save config
        self.config.to_yaml(Path(save_dir) / "training_config.yaml")

        console.print("[green]✓ Model saved successfully[/green]")

    def evaluate(self) -> Dict[str, Any]:
        """
        Evaluate model.

        Returns:
            Evaluation metrics
        """
        if self.eval_dataset is None:
            console.print("[yellow]No evaluation dataset available[/yellow]")
            return {}

        console.print("[cyan]Running evaluation...[/cyan]")
        metrics = self._run_evaluation()
        console.print("[green]✓ Evaluation complete[/green]")

        return metrics

    @abstractmethod
    def _run_evaluation(self) -> Dict[str, Any]:
        """
        Run evaluation logic.

        Must be implemented by subclasses.

        Returns:
            Evaluation metrics
        """
        pass

    def cleanup(self):
        """Cleanup resources."""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
