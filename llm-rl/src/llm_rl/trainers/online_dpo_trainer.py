"""Online DPO Trainer - DPO with online preference generation using native TRL."""

from typing import Dict, Any, List
import torch
from transformers import GenerationConfig
from datasets import Dataset
from rich.console import Console
from tqdm import tqdm

try:
    from trl import OnlineDPOTrainer as TRLOnlineDPOTrainer, OnlineDPOConfig as TRLOnlineDPOConfig
    HAS_ONLINE_DPO = True
except ImportError:
    HAS_ONLINE_DPO = False

from ..config import OnlineDPOConfig
from ..models import load_reward_model, compute_reward
from .dpo_trainer import create_dpo_trainer, _preprocess_dpo_datasets
from .utils import setup_logging, print_config, setup_model_and_data, save_model_with_config, cleanup_resources

console = Console()


def create_online_dpo_trainer(config: OnlineDPOConfig):
    """
    Create an Online DPO trainer.

    If TRL has native OnlineDPOTrainer, use it. Otherwise, use custom implementation.

    Args:
        config: Online DPO configuration

    Returns:
        Configured OnlineDPO trainer instance
    """
    if HAS_ONLINE_DPO:
        console.print("[cyan]Using native TRL OnlineDPOTrainer[/cyan]")
        return _create_trl_online_dpo_trainer(config)
    else:
        console.print("[yellow]TRL OnlineDPOTrainer not available, using custom implementation[/yellow]")
        return _CustomOnlineDPOTrainer(config)


def _create_trl_online_dpo_trainer(config: OnlineDPOConfig):
    """Create trainer using native TRL OnlineDPOTrainer."""
    # Setup logging
    logger = setup_logging(config)
    print_config(config)

    # Load model, tokenizer, and datasets
    model, tokenizer, train_dataset, eval_dataset = setup_model_and_data(config)

    # Preprocess datasets
    train_dataset, eval_dataset = _preprocess_dpo_datasets(
        train_dataset, eval_dataset, tokenizer, config
    )

    # Load reward model if specified
    reward_model = None
    reward_tokenizer = None
    if config.reward_model_name_or_path:
        console.print("[cyan]Loading reward model for ranking...[/cyan]")
        reward_model, reward_tokenizer = load_reward_model(
            model_name_or_path=config.reward_model_name_or_path,
        )
        console.print("[green]✓ Reward model loaded[/green]\n")

    # Create OnlineDPO config
    online_dpo_config = TRLOnlineDPOConfig(
        # Online DPO specific
        num_iterations=config.num_iterations,
        samples_per_prompt=config.samples_per_prompt,
        buffer_size=config.buffer_size,
        replay_ratio=config.replay_ratio,
        # DPO parameters
        beta=config.beta,
        label_smoothing=config.label_smoothing,
        loss_type=config.loss_type,
        max_prompt_length=config.max_prompt_length,
        max_length=config.max_length,
        # Training arguments
        output_dir=config.training.output_dir,
        num_train_epochs=config.training.num_train_epochs,
        per_device_train_batch_size=config.training.per_device_train_batch_size,
        per_device_eval_batch_size=config.training.per_device_eval_batch_size,
        gradient_accumulation_steps=config.training.gradient_accumulation_steps,
        learning_rate=config.training.learning_rate,
        weight_decay=config.training.weight_decay,
        warmup_ratio=config.training.warmup_ratio,
        max_grad_norm=config.training.max_grad_norm,
        logging_steps=config.training.logging_steps,
        save_steps=config.training.save_steps,
        save_total_limit=config.training.save_total_limit,
        eval_strategy="steps" if eval_dataset else "no",
        eval_steps=config.training.eval_steps,
        fp16=config.training.fp16,
        bf16=config.training.bf16,
        gradient_checkpointing=config.training.gradient_checkpointing,
        seed=config.training.seed,
        optim=config.training.optim,
        lr_scheduler_type=config.training.lr_scheduler_type,
        report_to=config.training.report_to,
        remove_unused_columns=False,
    )

    # Create trainer
    trainer = TRLOnlineDPOTrainer(
        model=model,
        reward_model=reward_model,
        args=online_dpo_config,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,
    )

    # Store metadata
    trainer._llm_rl_config = config
    trainer._llm_rl_tokenizer = tokenizer

    return trainer


class _CustomOnlineDPOTrainer:
    """Custom Online DPO trainer implementation (fallback when TRL doesn't have it)."""

    def __init__(self, config: OnlineDPOConfig):
        self.config = config
        self.experience_buffer: List[Dict] = []

        # Setup logging
        setup_logging(config)
        print_config(config)

        # Load components
        self.model, self.tokenizer, self.train_dataset, self.eval_dataset = setup_model_and_data(config)

        # Load reward model if specified
        self.reward_model = None
        self.reward_tokenizer = None
        if config.reward_model_name_or_path:
            console.print("[cyan]Loading reward model for ranking...[/cyan]")
            self.reward_model, self.reward_tokenizer = load_reward_model(
                model_name_or_path=config.reward_model_name_or_path,
            )
            console.print("[green]✓ Reward model loaded[/green]\n")

    def train(self) -> Dict[str, Any]:
        """Run Online DPO training with iterative improvement."""
        all_metrics = []

        for iteration in range(self.config.num_iterations):
            console.print(f"\n[bold cyan]Iteration {iteration + 1}/{self.config.num_iterations}[/bold cyan]")

            # Generate preference data online
            console.print("[cyan]Generating preference pairs online...[/cyan]")
            new_preferences = self._generate_preferences()

            # Update experience buffer
            self._update_buffer(new_preferences)

            # Create training dataset from buffer
            iteration_dataset = self._create_dataset_from_buffer()

            # Create DPO config for this iteration
            from ..config import DPOConfig
            dpo_config = DPOConfig(
                **self.config.model_dump(exclude={"method", "num_iterations", "samples_per_prompt"})
            )
            dpo_config.method = "dpo"

            # Train DPO on current dataset
            console.print(f"[cyan]Training DPO (iteration {iteration + 1})...[/cyan]")

            # Update train dataset
            from .dpo_trainer import _preprocess_dpo_datasets
            processed_dataset, _ = _preprocess_dpo_datasets(
                iteration_dataset, None, self.tokenizer, dpo_config
            )

            # Create a temporary DPO trainer for this iteration
            trainer = create_dpo_trainer(dpo_config)
            trainer.train_dataset = processed_dataset

            # Train one epoch
            train_result = trainer.train()

            metrics = train_result.metrics
            metrics["iteration"] = iteration + 1
            all_metrics.append(metrics)

            # Save iteration checkpoint if requested
            if self.config.save_iteration_checkpoints:
                checkpoint_dir = f"{self.config.training.output_dir}/iteration_{iteration + 1}"
                save_model_with_config(self.model, self.tokenizer, self.config, checkpoint_dir)

        # Save final model
        save_model_with_config(self.model, self.tokenizer, self.config)

        console.print("\n[bold green]✓ Online DPO Training Complete![/bold green]")
        return {"all_iterations": all_metrics}

    def _generate_preferences(self) -> List[Dict[str, str]]:
        """Generate preference pairs by sampling multiple completions."""
        preferences = []

        generation_config = GenerationConfig(
            max_new_tokens=self.config.max_new_tokens,
            temperature=self.config.temperature,
            top_k=self.config.top_k,
            top_p=self.config.top_p,
            do_sample=True,
            pad_token_id=self.tokenizer.pad_token_id,
            eos_token_id=self.tokenizer.eos_token_id,
        )

        num_prompts = min(len(self.train_dataset), self.config.dataset.max_train_samples or 1000)
        sampled_dataset = self.train_dataset.select(range(num_prompts))

        for example in tqdm(sampled_dataset, desc="Generating preferences"):
            prompt = example.get("prompt", "")

            # Generate multiple completions
            completions = self._generate_multiple_completions(
                prompt, self.config.samples_per_prompt, generation_config
            )

            # Rank completions
            ranked_completions = self._rank_completions(prompt, completions)

            # Create preference pair
            preference = {
                "prompt": prompt,
                "chosen": ranked_completions[0],
                "rejected": ranked_completions[-1],
            }
            preferences.append(preference)

        return preferences

    def _generate_multiple_completions(self, prompt: str, num_samples: int, generation_config) -> List[str]:
        """Generate multiple completions for a prompt."""
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                generation_config=generation_config,
                num_return_sequences=num_samples,
            )

        completions = []
        for output in outputs:
            completion = self.tokenizer.decode(
                output[inputs.input_ids.shape[1]:],
                skip_special_tokens=True,
            )
            completions.append(completion)

        return completions

    def _rank_completions(self, prompt: str, completions: List[str]) -> List[str]:
        """Rank completions by quality using reward model."""
        if self.reward_model:
            scores = []
            for completion in completions:
                score = compute_reward(
                    model=self.reward_model,
                    tokenizer=self.reward_tokenizer,
                    prompt=prompt,
                    response=completion,
                )
                scores.append(score)

            ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
            return [completions[i] for i in ranked_indices]
        else:
            return completions

    def _update_buffer(self, new_preferences: List[Dict[str, str]]):
        """Update experience buffer with new preferences."""
        self.experience_buffer.extend(new_preferences)

        if self.config.buffer_size and len(self.experience_buffer) > self.config.buffer_size:
            self.experience_buffer = self.experience_buffer[-self.config.buffer_size:]

    def _create_dataset_from_buffer(self) -> Dataset:
        """Create dataset from experience buffer."""
        return Dataset.from_list(self.experience_buffer)


def train_online_dpo(config: OnlineDPOConfig) -> Dict[str, Any]:
    """
    Train a model using Online DPO.

    Args:
        config: Online DPO configuration

    Returns:
        Training metrics
    """
    console.print("[bold green]Starting Online DPO Training[/bold green]\n")

    try:
        trainer = create_online_dpo_trainer(config)
        metrics = trainer.train()

        console.print("\n[bold green]✓ Online DPO Training Complete![/bold green]")
        return metrics

    finally:
        cleanup_resources()
