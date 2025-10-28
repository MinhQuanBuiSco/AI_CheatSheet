"""DPO (Direct Preference Optimization) Trainer using native TRL."""

from typing import Dict, Any, Optional
from trl import DPOTrainer as TRLDPOTrainer, DPOConfig as TRLDPOConfig
from rich.console import Console

from ..config import DPOConfig
from ..data import get_preprocessor, format_anthropic_hh
from .utils import setup_logging, print_config, setup_model_and_data, save_model_with_config, cleanup_resources

console = Console()


def create_dpo_trainer(config: DPOConfig) -> TRLDPOTrainer:
    """
    Create a DPO trainer using native TRL.

    Args:
        config: DPO configuration

    Returns:
        Configured TRL DPOTrainer instance
    """
    # Setup logging
    logger = setup_logging(config)
    print_config(config)

    # Load model, tokenizer, and datasets
    model, tokenizer, train_dataset, eval_dataset = setup_model_and_data(config)

    # Preprocess datasets for DPO
    train_dataset, eval_dataset = _preprocess_dpo_datasets(
        train_dataset, eval_dataset, tokenizer, config
    )

    # Load reference model if needed
    ref_model = None
    if config.force_use_ref_model:
        console.print("[cyan]Loading reference model...[/cyan]")
        from ..models import load_model_and_tokenizer
        ref_model, _ = load_model_and_tokenizer(
            model_config=config.model,
            peft_config=None,  # Reference model is not PEFT
        )
        console.print("[green]✓ Reference model loaded[/green]")

    # Create DPO config (inherits from TrainingArguments)
    dpo_config = TRLDPOConfig(
        # DPO-specific parameters
        beta=config.beta,
        label_smoothing=config.label_smoothing,
        loss_type=config.loss_type,
        label_pad_token_id=config.label_pad_token_id,
        padding_value=config.padding_value,
        truncation_mode=config.truncation_mode,
        max_prompt_length=config.max_prompt_length,
        max_length=config.max_length,
        generate_during_eval=config.generate_during_eval,
        precompute_ref_log_probs=config.precompute_ref_log_probs,
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

    # Create DPO trainer
    trainer = TRLDPOTrainer(
        model=model,
        ref_model=ref_model,
        args=dpo_config,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,
    )

    # Store additional metadata for later use
    trainer._llm_rl_config = config
    trainer._llm_rl_tokenizer = tokenizer

    return trainer


def _preprocess_dpo_datasets(train_dataset, eval_dataset, tokenizer, config: DPOConfig):
    """
    Preprocess datasets for DPO training.

    Args:
        train_dataset: Training dataset
        eval_dataset: Evaluation dataset
        tokenizer: Tokenizer
        config: DPO configuration

    Returns:
        Tuple of (preprocessed_train_dataset, preprocessed_eval_dataset)
    """
    # Get preprocessor
    preprocessor = get_preprocessor(
        method="dpo",
        tokenizer=tokenizer,
        max_length=config.max_length,
        max_prompt_length=config.max_prompt_length,
    )

    # Format datasets if needed (e.g., Anthropic HH)
    if "chosen" in train_dataset.column_names and "rejected" in train_dataset.column_names:
        if "prompt" not in train_dataset.column_names:
            console.print("[yellow]Formatting Anthropic HH dataset...[/yellow]")
            train_dataset = format_anthropic_hh(train_dataset)
            if eval_dataset:
                eval_dataset = format_anthropic_hh(eval_dataset)

    # Apply preprocessing
    train_dataset = preprocessor(train_dataset)
    if eval_dataset:
        eval_dataset = preprocessor(eval_dataset)

    return train_dataset, eval_dataset


def train_dpo(config: DPOConfig) -> Dict[str, Any]:
    """
    Train a model using DPO.

    Args:
        config: DPO configuration

    Returns:
        Training metrics
    """
    console.print("[bold green]Starting DPO Training[/bold green]\n")

    try:
        # Create trainer
        trainer = create_dpo_trainer(config)

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

        console.print("\n[bold green]✓ DPO Training Complete![/bold green]")
        return metrics

    finally:
        cleanup_resources()
