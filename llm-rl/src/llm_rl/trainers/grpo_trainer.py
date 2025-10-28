"""GRPO (Group Relative Policy Optimization) Trainer using native TRL."""

from typing import Dict, Any, Callable
from trl import GRPOTrainer as TRLGRPOTrainer, GRPOConfig as TRLGRPOConfig
from rich.console import Console

from ..config import GRPOConfig
from ..data import get_preprocessor
from ..models import load_reward_model, compute_reward
from .utils import setup_logging, print_config, setup_model_and_data, save_model_with_config, cleanup_resources

console = Console()


def create_grpo_trainer(config: GRPOConfig) -> TRLGRPOTrainer:
    """
    Create a GRPO trainer using native TRL.

    Args:
        config: GRPO configuration

    Returns:
        Configured TRL GRPOTrainer instance
    """
    # Setup logging
    logger = setup_logging(config)
    print_config(config)

    # Load model, tokenizer, and datasets
    model, tokenizer, train_dataset, eval_dataset = setup_model_and_data(config)

    # Preprocess datasets for GRPO
    train_dataset, eval_dataset = _preprocess_grpo_datasets(
        train_dataset, eval_dataset, tokenizer, config
    )

    # Load reward model and create reward function
    console.print("[cyan]Loading reward model...[/cyan]")
    reward_model, reward_tokenizer = load_reward_model(
        model_name_or_path=config.reward_model_name_or_path,
        device=config.reward_model_device,
    )
    console.print("[green]✓ Reward model loaded[/green]\n")

    # Create reward function for TRL
    def reward_function(completions, prompts=None, **kwargs):
        """
        Reward function compatible with TRL's GRPOTrainer.

        Args:
            completions: List of completion strings
            prompts: Optional list of prompt strings
            **kwargs: Additional keyword arguments

        Returns:
            List of reward scores
        """
        rewards = []
        for i, completion in enumerate(completions):
            # Extract completion content
            if isinstance(completion, list) and len(completion) > 0:
                # Handle conversational format
                completion_text = completion[0].get("content", "")
            else:
                completion_text = str(completion)

            # Get corresponding prompt
            if prompts and i < len(prompts):
                prompt = prompts[i]
            else:
                # Try to get from kwargs or dataset
                prompt = kwargs.get("prompt", [""])[i] if "prompt" in kwargs else ""

            # Compute reward
            reward = compute_reward(
                model=reward_model,
                tokenizer=reward_tokenizer,
                prompt=prompt,
                response=completion_text,
            )
            rewards.append(float(reward))

        return rewards

    # Create GRPO config
    grpo_config = TRLGRPOConfig(
        # Generation parameters
        num_generations=config.num_samples_per_prompt,
        max_completion_length=config.max_new_tokens,
        temperature=config.temperature,
        top_p=config.top_p,
        top_k=config.top_k,
        # Training dynamics
        beta=getattr(config, 'beta', 0.0),  # KL divergence weight
        epsilon=getattr(config, 'epsilon', 0.2),  # Trust region clipping
        loss_type=config.loss_type if hasattr(config, 'loss_type') else "dapo",
        num_iterations=getattr(config, 'num_iterations', 1),
        # Reward scaling
        scale_rewards=getattr(config, 'scale_rewards', "group"),
        # Advantage normalization
        use_advantage_normalization=config.use_advantage_normalization,
        # Logging
        log_completions=True,
        mask_truncated_completions=True,
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
        eval_steps=config.training.eval_steps if eval_dataset else None,
        fp16=config.training.fp16,
        bf16=config.training.bf16,
        gradient_checkpointing=config.training.gradient_checkpointing,
        seed=config.training.seed,
        optim=config.training.optim,
        lr_scheduler_type=config.training.lr_scheduler_type,
        report_to=config.training.report_to,
        remove_unused_columns=False,
    )

    # Create GRPO trainer with native TRL
    trainer = TRLGRPOTrainer(
        model=model,
        args=grpo_config,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,
        reward_funcs=reward_function,
    )

    # Store additional metadata
    trainer._llm_rl_config = config
    trainer._llm_rl_tokenizer = tokenizer

    return trainer


def _preprocess_grpo_datasets(train_dataset, eval_dataset, tokenizer, config: GRPOConfig):
    """
    Preprocess datasets for GRPO training.

    Args:
        train_dataset: Training dataset
        eval_dataset: Evaluation dataset
        tokenizer: Tokenizer
        config: GRPO configuration

    Returns:
        Tuple of (preprocessed_train_dataset, preprocessed_eval_dataset)
    """
    preprocessor = get_preprocessor(
        method="grpo",
        tokenizer=tokenizer,
        max_length=config.dataset.max_length,
    )

    train_dataset = preprocessor(train_dataset)
    if eval_dataset:
        eval_dataset = preprocessor(eval_dataset)

    return train_dataset, eval_dataset


def train_grpo(config: GRPOConfig) -> Dict[str, Any]:
    """
    Train a model using GRPO.

    Args:
        config: GRPO configuration

    Returns:
        Training metrics
    """
    console.print("[bold green]Starting GRPO Training[/bold green]\n")

    try:
        # Create trainer
        trainer = create_grpo_trainer(config)

        # Train
        train_result = trainer.train()

        # Save model
        save_model_with_config(
            trainer.model,
            trainer._llm_rl_tokenizer,
            config
        )

        # Get metrics
        metrics = train_result.metrics
        trainer.log_metrics("train", metrics)
        trainer.save_metrics("train", metrics)

        console.print("\n[bold green]✓ GRPO Training Complete![/bold green]")
        return metrics

    finally:
        cleanup_resources()
