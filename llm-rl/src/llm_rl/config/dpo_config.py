"""Configuration for DPO (Direct Preference Optimization) training."""

from typing import Optional
from pydantic import Field
from .base_config import BaseRLConfig, RLMethod


class DPOConfig(BaseRLConfig):
    """Configuration for DPO training."""

    method: RLMethod = Field(
        default=RLMethod.DPO,
        description="RL method (must be DPO)"
    )

    # DPO-specific parameters
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
        description="Loss type for DPO (sigmoid, hinge, ipo, kto_pair)"
    )
    label_pad_token_id: int = Field(
        default=-100,
        description="Pad token ID for labels"
    )
    padding_value: int = Field(
        default=0,
        description="Padding value for input IDs"
    )
    truncation_mode: str = Field(
        default="keep_end",
        description="Truncation mode (keep_start, keep_end)"
    )
    max_prompt_length: int = Field(
        default=256,
        description="Maximum length for prompts"
    )
    max_length: int = Field(
        default=512,
        description="Maximum length for sequences"
    )
    generate_during_eval: bool = Field(
        default=True,
        description="Generate samples during evaluation"
    )
    precompute_ref_log_probs: bool = Field(
        default=False,
        description="Precompute reference model log probabilities"
    )
    reference_free: bool = Field(
        default=False,
        description="Use reference-free DPO variant"
    )
    force_use_ref_model: bool = Field(
        default=False,
        description="Force using a separate reference model"
    )
    ref_model_name_or_path: Optional[str] = Field(
        default=None,
        description="Reference model path (if force_use_ref_model=True)"
    )
