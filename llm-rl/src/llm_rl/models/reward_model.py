"""Reward model training for PPO and GRPO."""

import torch
import torch.nn as nn
from typing import Optional, Dict, Any
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    PreTrainedModel,
    Trainer,
    TrainingArguments,
)
from datasets import Dataset
from peft import LoraConfig, get_peft_model, TaskType

from ..config import ModelConfig, PeftConfig, TrainingConfig


class RewardModelTrainer:
    """Trainer for reward models from preference data."""

    def __init__(
        self,
        model_config: ModelConfig,
        training_config: TrainingConfig,
        peft_config: Optional[PeftConfig] = None,
    ):
        """
        Initialize reward model trainer.

        Args:
            model_config: Model configuration
            training_config: Training configuration
            peft_config: Optional PEFT configuration
        """
        self.model_config = model_config
        self.training_config = training_config
        self.peft_config = peft_config

        # Load model and tokenizer
        self.model, self.tokenizer = self._load_model_and_tokenizer()

    def _load_model_and_tokenizer(self):
        """Load reward model and tokenizer."""
        tokenizer = AutoTokenizer.from_pretrained(
            self.model_config.model_name_or_path,
            trust_remote_code=self.model_config.trust_remote_code,
        )

        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        # Load model for sequence classification (binary: chosen vs rejected)
        model = AutoModelForSequenceClassification.from_pretrained(
            self.model_config.model_name_or_path,
            num_labels=1,  # Regression task for reward
            trust_remote_code=self.model_config.trust_remote_code,
        )

        # Configure pad token ID
        model.config.pad_token_id = tokenizer.pad_token_id

        # Apply PEFT if requested
        if self.model_config.use_peft and self.peft_config:
            lora_config = LoraConfig(
                r=self.peft_config.r,
                lora_alpha=self.peft_config.lora_alpha,
                lora_dropout=self.peft_config.lora_dropout,
                target_modules=self.peft_config.target_modules,
                bias=self.peft_config.bias,
                task_type=TaskType.SEQ_CLS,
            )
            model = get_peft_model(model, lora_config)
            model.print_trainable_parameters()

        return model, tokenizer

    def prepare_dataset(
        self,
        dataset: Dataset,
        max_length: int = 512,
    ) -> Dataset:
        """
        Prepare preference dataset for reward model training.

        Expected dataset format:
        {
            "prompt": "...",
            "chosen": "...",
            "rejected": "..."
        }

        Args:
            dataset: Input dataset with preference pairs
            max_length: Maximum sequence length

        Returns:
            Processed dataset
        """

        def preprocess_function(examples):
            # Tokenize chosen and rejected separately
            tokenized_chosen = self.tokenizer(
                [prompt + chosen for prompt, chosen in zip(examples["prompt"], examples["chosen"])],
                truncation=True,
                max_length=max_length,
                padding="max_length",
                return_tensors="pt",
            )

            tokenized_rejected = self.tokenizer(
                [prompt + rejected for prompt, rejected in zip(examples["prompt"], examples["rejected"])],
                truncation=True,
                max_length=max_length,
                padding="max_length",
                return_tensors="pt",
            )

            return {
                "input_ids_chosen": tokenized_chosen["input_ids"],
                "attention_mask_chosen": tokenized_chosen["attention_mask"],
                "input_ids_rejected": tokenized_rejected["input_ids"],
                "attention_mask_rejected": tokenized_rejected["attention_mask"],
            }

        return dataset.map(
            preprocess_function,
            batched=True,
            remove_columns=dataset.column_names,
        )

    def train(
        self,
        train_dataset: Dataset,
        eval_dataset: Optional[Dataset] = None,
    ) -> Dict[str, Any]:
        """
        Train the reward model.

        Args:
            train_dataset: Training dataset
            eval_dataset: Optional evaluation dataset

        Returns:
            Training metrics
        """
        # Prepare datasets
        train_dataset = self.prepare_dataset(train_dataset)
        if eval_dataset is not None:
            eval_dataset = self.prepare_dataset(eval_dataset)

        # Create training arguments
        training_args = TrainingArguments(
            output_dir=self.training_config.output_dir,
            num_train_epochs=self.training_config.num_train_epochs,
            per_device_train_batch_size=self.training_config.per_device_train_batch_size,
            per_device_eval_batch_size=self.training_config.per_device_eval_batch_size,
            gradient_accumulation_steps=self.training_config.gradient_accumulation_steps,
            learning_rate=self.training_config.learning_rate,
            weight_decay=self.training_config.weight_decay,
            warmup_ratio=self.training_config.warmup_ratio,
            max_grad_norm=self.training_config.max_grad_norm,
            logging_steps=self.training_config.logging_steps,
            save_steps=self.training_config.save_steps,
            save_total_limit=self.training_config.save_total_limit,
            fp16=self.training_config.fp16,
            bf16=self.training_config.bf16,
            gradient_checkpointing=self.training_config.gradient_checkpointing,
            seed=self.training_config.seed,
            optim=self.training_config.optim,
            lr_scheduler_type=self.training_config.lr_scheduler_type,
            report_to=self.training_config.report_to,
            evaluation_strategy="steps" if eval_dataset else "no",
            eval_steps=self.training_config.eval_steps,
            remove_unused_columns=False,
        )

        # Create custom trainer with preference loss
        trainer = RewardTrainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            tokenizer=self.tokenizer,
        )

        # Train
        train_result = trainer.train()

        # Save model
        trainer.save_model()
        self.tokenizer.save_pretrained(self.training_config.output_dir)

        return train_result.metrics


class RewardTrainer(Trainer):
    """Custom trainer for reward models with preference loss."""

    def compute_loss(self, model, inputs, return_outputs=False):
        """
        Compute Bradley-Terry preference loss.

        Loss = -log(sigmoid(r_chosen - r_rejected))
        """
        # Get rewards for chosen and rejected
        rewards_chosen = model(
            input_ids=inputs["input_ids_chosen"],
            attention_mask=inputs["attention_mask_chosen"],
        ).logits

        rewards_rejected = model(
            input_ids=inputs["input_ids_rejected"],
            attention_mask=inputs["attention_mask_rejected"],
        ).logits

        # Compute Bradley-Terry loss
        loss = -nn.functional.logsigmoid(rewards_chosen - rewards_rejected).mean()

        return (loss, {"rewards_chosen": rewards_chosen, "rewards_rejected": rewards_rejected}) if return_outputs else loss


def compute_reward(
    model: PreTrainedModel,
    tokenizer: AutoTokenizer,
    prompt: str,
    response: str,
    device: Optional[str] = None,
) -> float:
    """
    Compute reward for a prompt-response pair.

    Args:
        model: Reward model
        tokenizer: Tokenizer
        prompt: Input prompt
        response: Model response
        device: Device to run on

    Returns:
        Reward score
    """
    if device is None:
        device = next(model.parameters()).device

    # Tokenize
    inputs = tokenizer(
        prompt + response,
        return_tensors="pt",
        truncation=True,
        max_length=512,
    ).to(device)

    # Get reward
    with torch.no_grad():
        reward = model(**inputs).logits.squeeze().item()

    return reward
