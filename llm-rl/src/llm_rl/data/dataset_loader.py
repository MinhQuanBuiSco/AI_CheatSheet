"""Dataset loading and management for RL training."""

from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from datasets import load_dataset, Dataset, DatasetDict
from rich.console import Console

from ..config import DatasetConfig

console = Console()


# Dataset catalog with metadata
DATASET_CATALOG = {
    "anthropic-hh-rlhf": {
        "hf_name": "Anthropic/hh-rlhf",
        "type": "preference",
        "description": "Anthropic's Helpful and Harmless RLHF dataset",
        "columns": ["chosen", "rejected"],
        "size": "~160k pairs",
    },
    "ultrafeedback": {
        "hf_name": "openbmb/UltraFeedback",
        "type": "preference",
        "description": "Large-scale, high-quality preference dataset",
        "columns": ["instruction", "completions", "score"],
        "size": "~64k samples",
    },
    "ultrafeedback-binarized": {
        "hf_name": "HuggingFaceH4/ultrafeedback_binarized",
        "type": "preference",
        "description": "Binarized version of UltraFeedback for DPO",
        "columns": ["prompt", "chosen", "rejected"],
        "size": "~64k pairs",
        "train_split": "train_prefs",
        "test_split": "test_prefs",
    },
    "stack-exchange-preferences": {
        "hf_name": "lvwerra/stack-exchange-paired",
        "type": "preference",
        "description": "Stack Exchange preference pairs",
        "columns": ["question", "response_j", "response_k"],
        "size": "~10M pairs",
    },
    "summarize-from-feedback": {
        "hf_name": "openai/summarize_from_feedback",
        "type": "preference",
        "description": "OpenAI summarization with human feedback",
        "columns": ["info", "summaries"],
        "size": "~90k samples",
    },
    "helpful-base": {
        "hf_name": "HuggingFaceH4/helpful-base",
        "type": "sft",
        "description": "Helpful conversations for SFT",
        "columns": ["prompt", "completion"],
        "size": "~43k samples",
    },
}


class DatasetLoader:
    """Loader for RL training datasets."""

    def __init__(self, config: DatasetConfig):
        """
        Initialize dataset loader.

        Args:
            config: Dataset configuration
        """
        self.config = config
        self.dataset: Optional[DatasetDict] = None

    def load(
        self,
        dataset_name: Optional[str] = None,
        cache_dir: Optional[str] = None,
    ) -> DatasetDict:
        """
        Load dataset from HuggingFace or local path.

        Args:
            dataset_name: Name of dataset (from catalog or HF hub)
            cache_dir: Cache directory for downloaded datasets

        Returns:
            Loaded dataset
        """
        dataset_name = dataset_name or self.config.dataset_name

        if dataset_name is None:
            raise ValueError("No dataset name provided")

        # Check if it's a known dataset from catalog
        dataset_info = None
        if dataset_name in DATASET_CATALOG:
            dataset_info = DATASET_CATALOG[dataset_name]
            hf_name = dataset_info["hf_name"]
            console.print(f"[green]Loading dataset:[/green] {dataset_name} ({hf_name})")

            # Override train/eval splits if specified in catalog
            if "train_split" in dataset_info:
                self.config.train_split = dataset_info["train_split"]
            if "test_split" in dataset_info:
                self.config.eval_split = dataset_info["test_split"]
        else:
            hf_name = dataset_name
            console.print(f"[green]Loading dataset:[/green] {hf_name}")

        # Load dataset
        try:
            dataset = load_dataset(
                hf_name,
                name=self.config.dataset_subset,
                cache_dir=cache_dir,
            )
        except Exception as e:
            console.print(f"[red]Error loading dataset:[/red] {e}")
            raise

        # Validate splits exist
        if self.config.train_split not in dataset:
            raise ValueError(
                f"Train split '{self.config.train_split}' not found in dataset. "
                f"Available splits: {list(dataset.keys())}"
            )

        self.dataset = dataset
        console.print(f"[green]✓ Dataset loaded successfully[/green]")
        self._print_dataset_info()

        return dataset

    def _print_dataset_info(self):
        """Print dataset information."""
        if self.dataset is None:
            return

        console.print("\n[bold]Dataset Information:[/bold]")
        for split_name, split_data in self.dataset.items():
            console.print(f"  - {split_name}: {len(split_data)} examples")

        # Print column names
        sample_split = list(self.dataset.values())[0]
        console.print(f"  - Columns: {sample_split.column_names}\n")

    def get_splits(
        self,
        apply_limit: bool = True,
    ) -> Tuple[Dataset, Optional[Dataset]]:
        """
        Get train and eval splits.

        Args:
            apply_limit: Whether to apply max_train/eval_samples limits

        Returns:
            Tuple of (train_dataset, eval_dataset)
        """
        if self.dataset is None:
            raise ValueError("Dataset not loaded. Call load() first.")

        # Get train split
        train_dataset = self.dataset[self.config.train_split]

        # Apply train sample limit
        if apply_limit and self.config.max_train_samples:
            train_dataset = train_dataset.select(range(min(self.config.max_train_samples, len(train_dataset))))

        # Get eval split if exists
        eval_dataset = None
        if self.config.eval_split in self.dataset:
            eval_dataset = self.dataset[self.config.eval_split]

            # Apply eval sample limit
            if apply_limit and self.config.max_eval_samples:
                eval_dataset = eval_dataset.select(range(min(self.config.max_eval_samples, len(eval_dataset))))

        return train_dataset, eval_dataset

    @staticmethod
    def list_available_datasets() -> Dict[str, Dict[str, Any]]:
        """
        List all available datasets in the catalog.

        Returns:
            Dictionary of dataset information
        """
        return DATASET_CATALOG

    @staticmethod
    def print_dataset_catalog():
        """Print formatted dataset catalog."""
        console.print("\n[bold cyan]Available Datasets:[/bold cyan]\n")

        for name, info in DATASET_CATALOG.items():
            console.print(f"[bold]{name}[/bold]")
            console.print(f"  Type: {info['type']}")
            console.print(f"  Description: {info['description']}")
            console.print(f"  Size: {info['size']}")
            console.print(f"  HF Hub: {info['hf_name']}")
            console.print()


def format_preference_dataset(
    dataset: Dataset,
    prompt_key: str = "prompt",
    chosen_key: str = "chosen",
    rejected_key: str = "rejected",
) -> Dataset:
    """
    Format dataset to standard preference format.

    Standard format:
    {
        "prompt": str,
        "chosen": str,
        "rejected": str,
    }

    Args:
        dataset: Input dataset
        prompt_key: Key for prompt field
        chosen_key: Key for chosen response
        rejected_key: Key for rejected response

    Returns:
        Formatted dataset
    """

    def format_example(example):
        return {
            "prompt": example[prompt_key],
            "chosen": example[chosen_key],
            "rejected": example[rejected_key],
        }

    return dataset.map(format_example, remove_columns=dataset.column_names)


def format_anthropic_hh(dataset: Dataset) -> Dataset:
    """
    Format Anthropic HH-RLHF dataset to standard format.

    The Anthropic HH dataset has chosen/rejected fields directly.

    Args:
        dataset: Anthropic HH dataset

    Returns:
        Formatted dataset
    """
    def extract_prompt_and_responses(example):
        # The dataset has full conversations in chosen/rejected
        # We need to extract prompt and response
        chosen = example["chosen"]
        rejected = example["rejected"]

        # Split by Human/Assistant markers
        # Format: "\n\nHuman: ... \n\nAssistant: ..."
        parts = chosen.split("\n\nAssistant:")

        if len(parts) >= 2:
            prompt = parts[0] + "\n\nAssistant:"
            chosen_response = parts[-1].strip()
        else:
            prompt = ""
            chosen_response = chosen

        # Extract rejected response
        rejected_parts = rejected.split("\n\nAssistant:")
        rejected_response = rejected_parts[-1].strip() if len(rejected_parts) >= 2 else rejected

        return {
            "prompt": prompt,
            "chosen": chosen_response,
            "rejected": rejected_response,
        }

    return dataset.map(extract_prompt_and_responses, remove_columns=dataset.column_names)


def download_dataset(
    dataset_name: str,
    output_dir: Optional[str] = None,
    cache_dir: Optional[str] = None,
) -> Path:
    """
    Download dataset and save to local directory.

    Args:
        dataset_name: Name of dataset to download
        output_dir: Directory to save dataset
        cache_dir: Cache directory

    Returns:
        Path to saved dataset
    """
    console.print(f"[cyan]Downloading dataset:[/cyan] {dataset_name}")

    # Load dataset
    config = DatasetConfig(dataset_name=dataset_name)
    loader = DatasetLoader(config)
    dataset = loader.load(cache_dir=cache_dir)

    # Save to disk if output_dir specified
    if output_dir:
        output_path = Path(output_dir) / dataset_name.replace("/", "_")
        output_path.mkdir(parents=True, exist_ok=True)

        console.print(f"[cyan]Saving to:[/cyan] {output_path}")
        dataset.save_to_disk(str(output_path))

        console.print(f"[green]✓ Dataset saved successfully[/green]")
        return output_path

    console.print(f"[green]✓ Dataset downloaded to cache[/green]")
    return Path(cache_dir) if cache_dir else Path.home() / ".cache" / "huggingface" / "datasets"
