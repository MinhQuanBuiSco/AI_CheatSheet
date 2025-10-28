"""Command-line interface for LLM-RL."""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table

from .config import (
    RLMethod,
    DPOConfig,
    PPOConfig,
    OnlineDPOConfig,
    GRPOConfig,
)
from .trainers import (
    train_dpo,
    train_grpo,
    train_online_dpo,
)
from .models import RewardModelTrainer
from .data import DatasetLoader, DATASET_CATALOG

app = typer.Typer(
    name="llm-rl",
    help="Production-ready LLM fine-tuning with RL methods (DPO, PPO, Online DPO, GRPO)",
    add_completion=False,
)

console = Console()


@app.command()
def train(
    config_path: str = typer.Option(
        ...,
        "--config",
        "-c",
        help="Path to training configuration YAML file",
    ),
    method: Optional[str] = typer.Option(
        None,
        "--method",
        "-m",
        help="RL method (dpo, ppo, online_dpo, grpo). Overrides config.",
    ),
    output_dir: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory. Overrides config.",
    ),
):
    """
    Train a model using specified RL method.

    Example:
        llm-rl train --config configs/training/dpo/base.yaml
    """
    console.print("[bold cyan]LLM-RL Training[/bold cyan]\n")

    # Load config
    config_path = Path(config_path)
    if not config_path.exists():
        console.print(f"[red]Error: Config file not found:[/red] {config_path}")
        raise typer.Exit(1)

    # Determine method from config or argument
    import yaml
    with open(config_path) as f:
        config_dict = yaml.safe_load(f)

    method_str = method or config_dict.get("method")
    if not method_str:
        console.print("[red]Error: No method specified in config or arguments[/red]")
        raise typer.Exit(1)

    # Override output dir if specified
    if output_dir:
        config_dict["training"]["output_dir"] = output_dir

    # Load appropriate config and train
    try:
        if method_str == "dpo":
            config = DPOConfig(**config_dict)
            metrics = train_dpo(config)
        elif method_str == "ppo":
            console.print("[yellow]PPO support coming soon - use native TRL PPOTrainer directly[/yellow]")
            raise typer.Exit(1)
        elif method_str == "online_dpo":
            config = OnlineDPOConfig(**config_dict)
            metrics = train_online_dpo(config)
        elif method_str == "grpo":
            config = GRPOConfig(**config_dict)
            metrics = train_grpo(config)
        else:
            console.print(f"[red]Error: Unknown method:[/red] {method_str}")
            console.print("Available methods: dpo, grpo, online_dpo")
            raise typer.Exit(1)

        # Print final metrics
        console.print("\n[bold green]Training Complete![/bold green]")
        console.print("\n[bold]Final Metrics:[/bold]")
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                console.print(f"  {key}: {value:.4f}")

    except Exception as e:
        console.print(f"[red]Error during training:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def train_reward(
    config_path: str = typer.Option(
        ...,
        "--config",
        "-c",
        help="Path to reward model training configuration",
    ),
):
    """
    Train a reward model from preference data.

    Example:
        llm-rl train-reward --config configs/reward_model.yaml
    """
    console.print("[bold cyan]Reward Model Training[/bold cyan]\n")

    # Load config
    config_path = Path(config_path)
    if not config_path.exists():
        console.print(f"[red]Error: Config file not found:[/red] {config_path}")
        raise typer.Exit(1)

    # Load config as DPOConfig (reward model uses similar structure)
    import yaml
    with open(config_path) as f:
        config_dict = yaml.safe_load(f)

    try:
        # Create base config
        from .config import ModelConfig, TrainingConfig, PeftConfig, DatasetConfig

        model_config = ModelConfig(**config_dict["model"])
        training_config = TrainingConfig(**config_dict["training"])
        peft_config = PeftConfig(**config_dict["peft"]) if "peft" in config_dict else None
        dataset_config = DatasetConfig(**config_dict["dataset"])

        # Train reward model
        reward_trainer = RewardModelTrainer(
            model_config=model_config,
            training_config=training_config,
            peft_config=peft_config,
        )

        # Load dataset
        dataset_loader = DatasetLoader(dataset_config)
        dataset_loader.load()
        train_dataset, eval_dataset = dataset_loader.get_splits()

        # Train
        metrics = reward_trainer.train(train_dataset, eval_dataset)

        console.print("\n[bold green]✓ Reward Model Training Complete![/bold green]")
        console.print(f"Model saved to: {training_config.output_dir}")

    except Exception as e:
        console.print(f"[red]Error during reward model training:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def download_dataset(
    name: str = typer.Argument(
        ...,
        help="Dataset name from catalog or HuggingFace Hub",
    ),
    output_dir: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory to save dataset",
    ),
):
    """
    Download a dataset from HuggingFace Hub.

    Example:
        llm-rl download-dataset ultrafeedback-binarized --output ./data
    """
    console.print(f"[cyan]Downloading dataset:[/cyan] {name}\n")

    try:
        from .data import download_dataset as dl_dataset
        path = dl_dataset(name, output_dir=output_dir)
        console.print(f"\n[green]✓ Dataset downloaded successfully[/green]")
        console.print(f"Location: {path}")

    except Exception as e:
        console.print(f"[red]Error downloading dataset:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def list_datasets():
    """
    List available datasets in the catalog.

    Example:
        llm-rl list-datasets
    """
    table = Table(title="Available Datasets", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="green")
    table.add_column("Type", style="yellow")
    table.add_column("Size", style="magenta")
    table.add_column("Description")

    for name, info in DATASET_CATALOG.items():
        table.add_row(
            name,
            info["type"],
            info["size"],
            info["description"],
        )

    console.print(table)


@app.command()
def evaluate(
    checkpoint: str = typer.Option(
        ...,
        "--checkpoint",
        "-c",
        help="Path to model checkpoint",
    ),
    config_path: str = typer.Option(
        ...,
        "--config",
        help="Path to evaluation configuration",
    ),
    dataset: Optional[str] = typer.Option(
        None,
        "--dataset",
        "-d",
        help="Dataset name or path for evaluation",
    ),
):
    """
    Evaluate a trained model.

    Example:
        llm-rl evaluate --checkpoint ./outputs/final --config configs/eval.yaml
    """
    console.print("[bold cyan]Model Evaluation[/bold cyan]\n")
    console.print(f"Checkpoint: {checkpoint}")
    console.print(f"Config: {config_path}")

    # TODO: Implement evaluation logic
    console.print("\n[yellow]Evaluation feature coming soon![/yellow]")


@app.command()
def compare(
    checkpoints: str = typer.Option(
        ...,
        "--checkpoints",
        help="Comma-separated list of checkpoint paths",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file for comparison results",
    ),
):
    """
    Compare multiple trained models.

    Example:
        llm-rl compare --checkpoints model1,model2,model3 --output comparison.csv
    """
    console.print("[bold cyan]Model Comparison[/bold cyan]\n")

    checkpoint_list = [c.strip() for c in checkpoints.split(",")]
    console.print(f"Comparing {len(checkpoint_list)} models:")
    for cp in checkpoint_list:
        console.print(f"  - {cp}")

    # TODO: Implement comparison logic
    console.print("\n[yellow]Comparison feature coming soon![/yellow]")


@app.command()
def version():
    """Show version information."""
    from importlib.metadata import version as get_version

    try:
        ver = get_version("llm-rl")
    except Exception:
        ver = "unknown"

    console.print(f"[bold]llm-rl[/bold] version [cyan]{ver}[/cyan]")
    console.print("\nA production-ready platform for LLM fine-tuning with RL methods")
    console.print("Methods: DPO, PPO, Online DPO, GRPO")


if __name__ == "__main__":
    app()
