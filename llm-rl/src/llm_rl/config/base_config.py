"""Base configuration classes for LLM-RL training."""

from enum import Enum
from pathlib import Path
from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, field_validator
import yaml


class ModelSize(str, Enum):
    """Supported model sizes."""
    SMALL = "small"  # GPT-2, TinyLlama
    MEDIUM = "medium"  # 7B-13B models


class RLMethod(str, Enum):
    """Supported RL training methods."""
    DPO = "dpo"
    PPO = "ppo"
    ONLINE_DPO = "online_dpo"
    GRPO = "grpo"


class ModelConfig(BaseModel):
    """Configuration for model loading and setup."""

    model_name_or_path: str = Field(
        description="HuggingFace model name or path to local model"
    )
    model_size: ModelSize = Field(
        default=ModelSize.SMALL,
        description="Model size category"
    )
    use_peft: bool = Field(
        default=True,
        description="Whether to use PEFT (LoRA/QLoRA)"
    )
    load_in_8bit: bool = Field(
        default=False,
        description="Load model in 8-bit precision"
    )
    load_in_4bit: bool = Field(
        default=False,
        description="Load model in 4-bit precision (QLoRA)"
    )
    torch_dtype: Optional[str] = Field(
        default="bfloat16",
        description="Torch dtype for model (float32, float16, bfloat16)"
    )
    trust_remote_code: bool = Field(
        default=False,
        description="Trust remote code when loading model"
    )

    @field_validator("load_in_4bit", "load_in_8bit")
    @classmethod
    def check_quantization(cls, v, info):
        """Ensure only one quantization method is used."""
        if v and info.data.get("load_in_8bit") and info.field_name == "load_in_4bit":
            raise ValueError("Cannot use both 8-bit and 4-bit quantization")
        return v


class PeftConfig(BaseModel):
    """Configuration for PEFT (LoRA) training."""

    r: int = Field(
        default=16,
        description="LoRA rank"
    )
    lora_alpha: int = Field(
        default=32,
        description="LoRA alpha parameter"
    )
    lora_dropout: float = Field(
        default=0.05,
        description="LoRA dropout rate",
        ge=0.0,
        le=1.0
    )
    target_modules: Optional[list[str]] = Field(
        default=None,
        description="Target modules for LoRA. If None, will auto-detect"
    )
    bias: str = Field(
        default="none",
        description="Bias training strategy (none, all, lora_only)"
    )
    task_type: str = Field(
        default="CAUSAL_LM",
        description="Task type for PEFT"
    )


class DatasetConfig(BaseModel):
    """Configuration for dataset loading."""

    dataset_name: Optional[str] = Field(
        default=None,
        description="HuggingFace dataset name or local path"
    )
    dataset_subset: Optional[str] = Field(
        default=None,
        description="Dataset subset/configuration"
    )
    train_split: str = Field(
        default="train",
        description="Training data split"
    )
    eval_split: str = Field(
        default="test",
        description="Evaluation data split"
    )
    max_train_samples: Optional[int] = Field(
        default=None,
        description="Maximum number of training samples"
    )
    max_eval_samples: Optional[int] = Field(
        default=None,
        description="Maximum number of evaluation samples"
    )
    max_length: int = Field(
        default=512,
        description="Maximum sequence length"
    )
    max_prompt_length: int = Field(
        default=256,
        description="Maximum prompt length"
    )
    preprocessing_num_workers: int = Field(
        default=4,
        description="Number of workers for data preprocessing"
    )


class TrainingConfig(BaseModel):
    """Base training configuration."""

    output_dir: str = Field(
        default="./outputs",
        description="Output directory for checkpoints and logs"
    )
    num_train_epochs: int = Field(
        default=1,
        description="Number of training epochs",
        gt=0
    )
    per_device_train_batch_size: int = Field(
        default=4,
        description="Training batch size per device",
        gt=0
    )
    per_device_eval_batch_size: int = Field(
        default=4,
        description="Evaluation batch size per device",
        gt=0
    )
    gradient_accumulation_steps: int = Field(
        default=1,
        description="Number of gradient accumulation steps",
        gt=0
    )
    learning_rate: float = Field(
        default=5e-5,
        description="Initial learning rate",
        gt=0.0
    )
    weight_decay: float = Field(
        default=0.01,
        description="Weight decay",
        ge=0.0
    )
    warmup_ratio: float = Field(
        default=0.1,
        description="Warmup ratio",
        ge=0.0,
        le=1.0
    )
    max_grad_norm: float = Field(
        default=1.0,
        description="Maximum gradient norm for clipping",
        gt=0.0
    )
    logging_steps: int = Field(
        default=10,
        description="Log every X steps",
        gt=0
    )
    eval_steps: Optional[int] = Field(
        default=None,
        description="Evaluate every X steps. If None, evaluates each epoch"
    )
    save_steps: int = Field(
        default=500,
        description="Save checkpoint every X steps",
        gt=0
    )
    save_total_limit: Optional[int] = Field(
        default=3,
        description="Maximum number of checkpoints to keep"
    )
    fp16: bool = Field(
        default=False,
        description="Use FP16 mixed precision"
    )
    bf16: bool = Field(
        default=True,
        description="Use BF16 mixed precision"
    )
    gradient_checkpointing: bool = Field(
        default=True,
        description="Use gradient checkpointing to save memory"
    )
    seed: int = Field(
        default=42,
        description="Random seed"
    )
    optim: str = Field(
        default="adamw_torch",
        description="Optimizer to use"
    )
    lr_scheduler_type: str = Field(
        default="cosine",
        description="Learning rate scheduler type"
    )
    report_to: list[str] = Field(
        default=["tensorboard"],
        description="Reporting tools (tensorboard, wandb, none)"
    )
    ddp_find_unused_parameters: Optional[bool] = Field(
        default=None,
        description="DDP find unused parameters"
    )
    deepspeed: Optional[str] = Field(
        default=None,
        description="Path to DeepSpeed config file"
    )

    @field_validator("fp16", "bf16")
    @classmethod
    def check_precision(cls, v, info):
        """Ensure only one precision mode is used."""
        if v and info.data.get("fp16") and info.field_name == "bf16":
            raise ValueError("Cannot use both FP16 and BF16")
        return v


class LoggingConfig(BaseModel):
    """Configuration for logging and tracking."""

    wandb_project: Optional[str] = Field(
        default=None,
        description="Weights & Biases project name"
    )
    wandb_entity: Optional[str] = Field(
        default=None,
        description="Weights & Biases entity (user/org)"
    )
    wandb_run_name: Optional[str] = Field(
        default=None,
        description="Weights & Biases run name"
    )
    tensorboard_dir: Optional[str] = Field(
        default=None,
        description="TensorBoard log directory"
    )
    log_level: str = Field(
        default="info",
        description="Logging level (debug, info, warning, error)"
    )


class BaseRLConfig(BaseModel):
    """Base configuration for all RL training methods."""

    method: RLMethod = Field(
        description="RL training method to use"
    )
    model: ModelConfig = Field(
        description="Model configuration"
    )
    peft: Optional[PeftConfig] = Field(
        default=None,
        description="PEFT configuration (if use_peft=True)"
    )
    dataset: DatasetConfig = Field(
        description="Dataset configuration"
    )
    training: TrainingConfig = Field(
        description="Training configuration"
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Logging configuration"
    )

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> "BaseRLConfig":
        """Load configuration from YAML file."""
        with open(yaml_path, 'r') as f:
            config_dict = yaml.safe_load(f)
        return cls(**config_dict)

    def to_yaml(self, yaml_path: str | Path) -> None:
        """Save configuration to YAML file."""
        with open(yaml_path, 'w') as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return self.model_dump()
