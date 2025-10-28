"""Configuration for GRPO (Group Relative Policy Optimization) training."""

from typing import Optional
from pydantic import Field
from .base_config import BaseRLConfig, RLMethod


class GRPOConfig(BaseRLConfig):
    """Configuration for GRPO training."""

    method: RLMethod = Field(
        default=RLMethod.GRPO,
        description="RL method (must be GRPO)"
    )

    # GRPO-specific parameters
    num_samples_per_prompt: int = Field(
        default=4,
        description="Number of completions to generate per prompt",
        gt=1
    )
    beta: float = Field(
        default=0.1,
        description="Temperature parameter for GRPO loss",
        gt=0.0
    )
    group_size: Optional[int] = Field(
        default=None,
        description="Group size for relative ranking (None = use all samples)"
    )

    # Reward model
    reward_model_name_or_path: str = Field(
        description="Path to trained reward model"
    )
    reward_model_device: Optional[str] = Field(
        default=None,
        description="Device for reward model"
    )

    # Generation settings
    max_new_tokens: int = Field(
        default=128,
        description="Maximum new tokens to generate",
        gt=0
    )
    temperature: float = Field(
        default=0.9,
        description="Sampling temperature",
        gt=0.0
    )
    top_k: int = Field(
        default=50,
        description="Top-k sampling",
        ge=0
    )
    top_p: float = Field(
        default=0.95,
        description="Top-p (nucleus) sampling",
        gt=0.0,
        le=1.0
    )
    do_sample: bool = Field(
        default=True,
        description="Use sampling for generation"
    )
    num_beams: int = Field(
        default=1,
        description="Number of beams (1 = no beam search)",
        gt=0
    )

    # Optimization parameters
    max_grad_norm: float = Field(
        default=1.0,
        description="Maximum gradient norm for clipping",
        gt=0.0
    )
    label_smoothing: float = Field(
        default=0.0,
        description="Label smoothing parameter",
        ge=0.0,
        le=1.0
    )

    # Relative preference settings
    use_advantage_normalization: bool = Field(
        default=True,
        description="Normalize advantages within groups"
    )
    advantage_clipping: Optional[float] = Field(
        default=10.0,
        description="Clip advantage values (None = no clipping)"
    )

    # Memory optimization
    gradient_checkpointing: bool = Field(
        default=True,
        description="Use gradient checkpointing"
    )
    optimize_device_cache: bool = Field(
        default=False,
        description="Optimize CUDA cache"
    )
