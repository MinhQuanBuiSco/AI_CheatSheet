"""Model utilities and reward model training."""

from .model_utils import (
    load_model_and_tokenizer,
    setup_peft_model,
    load_reward_model,
    get_quantization_config,
    get_default_lora_targets,
    count_parameters,
    get_model_memory_footprint,
)
from .reward_model import (
    RewardModelTrainer,
    RewardTrainer,
    compute_reward,
)

__all__ = [
    # Model loading and setup
    "load_model_and_tokenizer",
    "setup_peft_model",
    "load_reward_model",
    "get_quantization_config",
    "get_default_lora_targets",
    "count_parameters",
    "get_model_memory_footprint",
    # Reward model training
    "RewardModelTrainer",
    "RewardTrainer",
    "compute_reward",
]
