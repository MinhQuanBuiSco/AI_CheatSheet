"""RL Trainers for different methods - using native TRL trainers."""

# Import training functions (new simplified API)
from .dpo_trainer import train_dpo, create_dpo_trainer
from .grpo_trainer import train_grpo, create_grpo_trainer
from .online_dpo_trainer import train_online_dpo, create_online_dpo_trainer
from .utils import (
    setup_logging,
    print_config,
    setup_model_and_data,
    save_model_with_config,
    cleanup_resources,
)

# Keep base trainer for backward compatibility (if needed)
try:
    from .base_trainer import BaseRLTrainer
except ImportError:
    BaseRLTrainer = None

__all__ = [
    # New simplified API
    "train_dpo",
    "train_grpo",
    "train_online_dpo",
    "create_dpo_trainer",
    "create_grpo_trainer",
    "create_online_dpo_trainer",
    # Utility functions
    "setup_logging",
    "print_config",
    "setup_model_and_data",
    "save_model_with_config",
    "cleanup_resources",
    # Backward compatibility
    "BaseRLTrainer",
]
