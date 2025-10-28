"""Configuration for PPO (Proximal Policy Optimization) training."""

from typing import Optional
from pydantic import Field
from .base_config import BaseRLConfig, RLMethod


class PPOConfig(BaseRLConfig):
    """Configuration for PPO training."""

    method: RLMethod = Field(
        default=RLMethod.PPO,
        description="RL method (must be PPO)"
    )

    # Reward model
    reward_model_name_or_path: str = Field(
        description="Path to trained reward model"
    )
    reward_model_device: Optional[str] = Field(
        default=None,
        description="Device for reward model (cuda:0, cpu, etc.)"
    )

    # PPO-specific parameters
    init_kl_coef: float = Field(
        default=0.2,
        description="Initial KL penalty coefficient",
        ge=0.0
    )
    target_kl: float = Field(
        default=6.0,
        description="Target KL divergence",
        gt=0.0
    )
    adap_kl_ctrl: bool = Field(
        default=True,
        description="Use adaptive KL control"
    )
    gamma: float = Field(
        default=1.0,
        description="Discount factor for rewards",
        ge=0.0,
        le=1.0
    )
    lam: float = Field(
        default=0.95,
        description="Lambda for GAE (Generalized Advantage Estimation)",
        ge=0.0,
        le=1.0
    )
    cliprange: float = Field(
        default=0.2,
        description="Clipping parameter for PPO",
        gt=0.0
    )
    cliprange_value: float = Field(
        default=0.2,
        description="Clipping parameter for value function",
        gt=0.0
    )
    vf_coef: float = Field(
        default=0.1,
        description="Value function loss coefficient",
        ge=0.0
    )
    batch_size: int = Field(
        default=128,
        description="PPO mini-batch size",
        gt=0
    )
    forward_batch_size: Optional[int] = Field(
        default=None,
        description="Forward pass batch size (for generation)"
    )
    ppo_epochs: int = Field(
        default=4,
        description="Number of PPO optimization epochs per batch",
        gt=0
    )

    # Generation settings
    max_new_tokens: int = Field(
        default=128,
        description="Maximum new tokens to generate",
        gt=0
    )
    temperature: float = Field(
        default=1.0,
        description="Sampling temperature",
        gt=0.0
    )
    top_k: int = Field(
        default=0,
        description="Top-k sampling (0 = disabled)",
        ge=0
    )
    top_p: float = Field(
        default=1.0,
        description="Top-p (nucleus) sampling",
        gt=0.0,
        le=1.0
    )
    do_sample: bool = Field(
        default=True,
        description="Use sampling for generation"
    )

    # Optimization
    remove_unused_columns: bool = Field(
        default=False,
        description="Remove unused columns from dataset"
    )
    optimize_device_cache: bool = Field(
        default=False,
        description="Optimize CUDA cache for memory efficiency"
    )
