"""Data preprocessors for different RL methods."""

from typing import Dict, Any, Callable
from datasets import Dataset
from transformers import PreTrainedTokenizer


class DPOPreprocessor:
    """Preprocessor for DPO datasets."""

    def __init__(
        self,
        tokenizer: PreTrainedTokenizer,
        max_length: int = 512,
        max_prompt_length: int = 256,
    ):
        """
        Initialize DPO preprocessor.

        Args:
            tokenizer: Tokenizer for encoding
            max_length: Maximum total sequence length
            max_prompt_length: Maximum prompt length
        """
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.max_prompt_length = max_prompt_length

    def __call__(self, dataset: Dataset) -> Dataset:
        """
        Preprocess dataset for DPO training.

        DPO expects: prompt, chosen, rejected fields

        Args:
            dataset: Input dataset

        Returns:
            Preprocessed dataset
        """
        # The TRL DPOTrainer handles tokenization internally
        # We just need to ensure the format is correct
        required_columns = ["prompt", "chosen", "rejected"]

        for col in required_columns:
            if col not in dataset.column_names:
                raise ValueError(f"Dataset missing required column: {col}")

        # Keep only the required columns - DPOTrainer is strict about this
        columns_to_remove = [col for col in dataset.column_names if col not in required_columns]
        if columns_to_remove:
            dataset = dataset.remove_columns(columns_to_remove)

        return dataset


class PPOPreprocessor:
    """Preprocessor for PPO datasets."""

    def __init__(
        self,
        tokenizer: PreTrainedTokenizer,
        max_length: int = 512,
    ):
        """
        Initialize PPO preprocessor.

        Args:
            tokenizer: Tokenizer for encoding
            max_length: Maximum sequence length
        """
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __call__(self, dataset: Dataset) -> Dataset:
        """
        Preprocess dataset for PPO training.

        PPO needs prompts that the model will complete.

        Args:
            dataset: Input dataset

        Returns:
            Preprocessed dataset with tokenized prompts
        """

        def tokenize_prompts(examples):
            # Tokenize prompts
            tokenized = self.tokenizer(
                examples["prompt"],
                truncation=True,
                max_length=self.max_length,
                padding=False,  # PPO handles padding
                return_tensors=None,
            )
            return {
                "input_ids": tokenized["input_ids"],
                "attention_mask": tokenized["attention_mask"],
                "query": examples["prompt"],  # Keep original text
            }

        # Ensure prompt field exists
        if "prompt" not in dataset.column_names:
            raise ValueError("Dataset missing 'prompt' column for PPO")

        processed = dataset.map(
            tokenize_prompts,
            batched=True,
            remove_columns=[col for col in dataset.column_names if col != "prompt"],
        )

        return processed


class OnlineDPOPreprocessor:
    """Preprocessor for Online DPO datasets."""

    def __init__(
        self,
        tokenizer: PreTrainedTokenizer,
        max_length: int = 512,
    ):
        """
        Initialize Online DPO preprocessor.

        Args:
            tokenizer: Tokenizer for encoding
            max_length: Maximum sequence length
        """
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __call__(self, dataset: Dataset) -> Dataset:
        """
        Preprocess dataset for Online DPO.

        Online DPO starts with prompts and generates completions online.

        Args:
            dataset: Input dataset with prompts

        Returns:
            Preprocessed dataset
        """
        # For online DPO, we just need prompts
        if "prompt" not in dataset.column_names:
            raise ValueError("Dataset missing 'prompt' column")

        return dataset


class GRPOPreprocessor:
    """Preprocessor for GRPO datasets."""

    def __init__(
        self,
        tokenizer: PreTrainedTokenizer,
        max_length: int = 512,
    ):
        """
        Initialize GRPO preprocessor.

        Args:
            tokenizer: Tokenizer for encoding
            max_length: Maximum sequence length
        """
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __call__(self, dataset: Dataset) -> Dataset:
        """
        Preprocess dataset for GRPO.

        GRPO needs prompts for generating multiple completions.

        Args:
            dataset: Input dataset

        Returns:
            Preprocessed dataset
        """

        def tokenize_prompts(examples):
            tokenized = self.tokenizer(
                examples["prompt"],
                truncation=True,
                max_length=self.max_length,
                padding=False,
                return_tensors=None,
            )
            return {
                "input_ids": tokenized["input_ids"],
                "attention_mask": tokenized["attention_mask"],
                "query": examples["prompt"],
            }

        if "prompt" not in dataset.column_names:
            raise ValueError("Dataset missing 'prompt' column")

        return dataset.map(
            tokenize_prompts,
            batched=True,
            remove_columns=[col for col in dataset.column_names if col != "prompt"],
        )


def get_preprocessor(
    method: str,
    tokenizer: PreTrainedTokenizer,
    max_length: int = 512,
    max_prompt_length: int = 256,
) -> Callable:
    """
    Get preprocessor for a specific RL method.

    Args:
        method: RL method name (dpo, ppo, online_dpo, grpo)
        tokenizer: Tokenizer
        max_length: Maximum sequence length
        max_prompt_length: Maximum prompt length

    Returns:
        Preprocessor function
    """
    preprocessors = {
        "dpo": DPOPreprocessor(tokenizer, max_length, max_prompt_length),
        "ppo": PPOPreprocessor(tokenizer, max_length),
        "online_dpo": OnlineDPOPreprocessor(tokenizer, max_length),
        "grpo": GRPOPreprocessor(tokenizer, max_length),
    }

    if method not in preprocessors:
        raise ValueError(
            f"Unknown method: {method}. "
            f"Available: {list(preprocessors.keys())}"
        )

    return preprocessors[method]
