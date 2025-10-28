"""Configuration for Online DPO training."""

from typing import Optional
from pydantic import Field
from .base_config import BaseRLConfig, RLMethod


class OnlineDPOConfig(BaseRLConfig):
    """Configuration for Online DPO training."""

    method: RLMethod = Field(
        default=RLMethod.ONLINE_DPO,
        description="RL method (must be online_dpo)"
    )

    # DPO parameters (inherited from DPO)
    beta: float = Field(
        default=0.1,
        description="Temperature parameter for DPO loss",
        gt=0.0
    )
    label_smoothing: float = Field(
        default=0.0,
        description="Label smoothing parameter",
        ge=0.0,
        le=1.0
    )
    loss_type: str = Field(
        default="sigmoid",
        description="Loss type for DPO"
    )

    # Online learning parameters
    num_iterations: int = Field(
        default=10,
        description="Number of online learning iterations",
        gt=0
    )
    samples_per_prompt: int = Field(
        default=4,
        description="Number of samples to generate per prompt",
        gt=1
    )
    reward_model_name_or_path: Optional[str] = Field(
        default=None,
        description="Reward model for ranking samples (optional)"
    )
    use_self_ranking: bool = Field(
        default=True,
        description="Use model's own preferences for ranking"
    )

    # Generation settings
    max_new_tokens: int = Field(
        default=128,
        description="Maximum new tokens to generate",
        gt=0
    )
    temperature: float = Field(
        default=0.9,
        description="Sampling temperature for diversity",
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
    num_beams: int = Field(
        default=1,
        description="Number of beams for beam search (1 = no beam search)",
        gt=0
    )

    # Iteration settings
    warmup_iterations: int = Field(
        default=2,
        description="Number of warmup iterations",
        ge=0
    )
    eval_interval: int = Field(
        default=1,
        description="Evaluate every N iterations",
        gt=0
    )
    save_iteration_checkpoints: bool = Field(
        default=True,
        description="Save checkpoints after each iteration"
    )

    # Data buffer
    buffer_size: Optional[int] = Field(
        default=None,
        description="Size of experience buffer (None = unlimited)"
    )
    replay_ratio: float = Field(
        default=0.5,
        description="Ratio of replayed samples vs new samples",
        ge=0.0,
        le=1.0
    )
