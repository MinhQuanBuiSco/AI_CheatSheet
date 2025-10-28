"""Utilities for loading and configuring models."""

import torch
from typing import Optional, Tuple
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    PreTrainedModel,
    PreTrainedTokenizer,
)
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    PeftModel,
)

from ..config import ModelConfig, PeftConfig


def get_quantization_config(
    load_in_4bit: bool = False,
    load_in_8bit: bool = False,
    bnb_4bit_compute_dtype: str = "bfloat16",
) -> Optional[BitsAndBytesConfig]:
    """
    Create BitsAndBytes quantization configuration.

    Args:
        load_in_4bit: Whether to load in 4-bit precision
        load_in_8bit: Whether to load in 8-bit precision
        bnb_4bit_compute_dtype: Compute dtype for 4-bit quantization

    Returns:
        BitsAndBytesConfig or None
    """
    if not (load_in_4bit or load_in_8bit):
        return None

    if load_in_4bit:
        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=getattr(torch, bnb_4bit_compute_dtype),
            bnb_4bit_use_double_quant=True,
        )
    else:
        return BitsAndBytesConfig(
            load_in_8bit=True,
        )


def load_model_and_tokenizer(
    model_config: ModelConfig,
    peft_config: Optional[PeftConfig] = None,
    device_map: str = "auto",
    add_pad_token: bool = True,
) -> Tuple[PreTrainedModel, PreTrainedTokenizer]:
    """
    Load model and tokenizer with optional PEFT configuration.

    Args:
        model_config: Model configuration
        peft_config: PEFT configuration (optional)
        device_map: Device mapping strategy
        add_pad_token: Whether to add pad token if missing

    Returns:
        Tuple of (model, tokenizer)
    """
    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        model_config.model_name_or_path,
        trust_remote_code=model_config.trust_remote_code,
        padding_side="left",  # Important for causal LM
    )

    # Add pad token if needed
    if add_pad_token and tokenizer.pad_token is None:
        if tokenizer.eos_token is not None:
            tokenizer.pad_token = tokenizer.eos_token
        else:
            tokenizer.add_special_tokens({"pad_token": "[PAD]"})

    # Add a simple chat template if the tokenizer doesn't have one
    # This is needed for TRL's DPOTrainer
    if tokenizer.chat_template is None:
        tokenizer.chat_template = "{% for message in messages %}{{ message['content'] }}{% endfor %}"

    # Get quantization config
    quantization_config = get_quantization_config(
        load_in_4bit=model_config.load_in_4bit,
        load_in_8bit=model_config.load_in_8bit,
        bnb_4bit_compute_dtype=model_config.torch_dtype or "bfloat16",
    )

    # Determine torch dtype
    if model_config.torch_dtype:
        torch_dtype = getattr(torch, model_config.torch_dtype)
    else:
        torch_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16

    # Load model
    model = AutoModelForCausalLM.from_pretrained(
        model_config.model_name_or_path,
        quantization_config=quantization_config,
        device_map=device_map,
        torch_dtype=torch_dtype if quantization_config is None else None,
        trust_remote_code=model_config.trust_remote_code,
        use_cache=False,  # Disable cache for training
    )

    # Resize token embeddings if we added tokens
    if len(tokenizer) > model.config.vocab_size:
        model.resize_token_embeddings(len(tokenizer))

    # Apply PEFT if requested
    if model_config.use_peft and peft_config:
        model = setup_peft_model(model, peft_config, model_config)

    return model, tokenizer


def setup_peft_model(
    model: PreTrainedModel,
    peft_config: PeftConfig,
    model_config: ModelConfig,
) -> PeftModel:
    """
    Setup PEFT (LoRA) on a model.

    Args:
        model: Base model
        peft_config: PEFT configuration
        model_config: Model configuration

    Returns:
        PEFT-enabled model
    """
    # Prepare model for k-bit training if using quantization
    if model_config.load_in_4bit or model_config.load_in_8bit:
        model = prepare_model_for_kbit_training(
            model,
            use_gradient_checkpointing=True,
        )

    # Auto-detect target modules if not specified
    target_modules = peft_config.target_modules
    if target_modules is None:
        target_modules = get_default_lora_targets(model)

    # Create LoRA config
    lora_config = LoraConfig(
        r=peft_config.r,
        lora_alpha=peft_config.lora_alpha,
        lora_dropout=peft_config.lora_dropout,
        target_modules=target_modules,
        bias=peft_config.bias,
        task_type=peft_config.task_type,
    )

    # Apply PEFT
    model = get_peft_model(model, lora_config)

    # Print trainable parameters
    model.print_trainable_parameters()

    return model


def get_default_lora_targets(model: PreTrainedModel) -> list[str]:
    """
    Get default LoRA target modules based on model architecture.

    Args:
        model: The model to inspect

    Returns:
        List of target module names
    """
    model_type = model.config.model_type.lower()

    # Common patterns for different model architectures
    target_map = {
        "llama": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        "mistral": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        "gpt2": ["c_attn", "c_proj", "c_fc"],
        "gpt_neox": ["query_key_value", "dense", "dense_h_to_4h", "dense_4h_to_h"],
        "opt": ["q_proj", "k_proj", "v_proj", "out_proj", "fc1", "fc2"],
        "bloom": ["query_key_value", "dense", "dense_h_to_4h", "dense_4h_to_h"],
    }

    # Try to find matching architecture
    for key, targets in target_map.items():
        if key in model_type:
            return targets

    # Default fallback: target all linear layers with 'proj' or 'fc' in name
    print(f"Warning: Unknown model type '{model_type}', using default LoRA targets")
    return ["q_proj", "v_proj"]


def load_reward_model(
    model_name_or_path: str,
    device: Optional[str] = None,
    torch_dtype: str = "bfloat16",
) -> Tuple[PreTrainedModel, PreTrainedTokenizer]:
    """
    Load a reward model for PPO/GRPO training.

    Args:
        model_name_or_path: Path to reward model
        device: Device to load model on
        torch_dtype: Torch dtype for model

    Returns:
        Tuple of (reward_model, tokenizer)
    """
    tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    dtype = getattr(torch, torch_dtype)

    model = AutoModelForCausalLM.from_pretrained(
        model_name_or_path,
        torch_dtype=dtype,
        device_map=device or "auto",
    )

    model.eval()  # Reward model is always in eval mode

    return model, tokenizer


def count_parameters(model: PreTrainedModel) -> dict:
    """
    Count total and trainable parameters in model.

    Args:
        model: Model to count parameters for

    Returns:
        Dictionary with parameter counts
    """
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

    return {
        "total": total_params,
        "trainable": trainable_params,
        "percentage": 100 * trainable_params / total_params if total_params > 0 else 0,
    }


def get_model_memory_footprint(model: PreTrainedModel) -> dict:
    """
    Get model memory footprint information.

    Args:
        model: Model to analyze

    Returns:
        Dictionary with memory information
    """
    param_count = count_parameters(model)

    # Estimate memory in bytes (rough approximation)
    # Each parameter is typically 4 bytes (fp32) or 2 bytes (fp16/bf16)
    bytes_per_param = 2  # Assuming mixed precision

    total_memory_mb = (param_count["total"] * bytes_per_param) / (1024 ** 2)
    trainable_memory_mb = (param_count["trainable"] * bytes_per_param) / (1024 ** 2)

    return {
        "total_params": param_count["total"],
        "trainable_params": param_count["trainable"],
        "trainable_percentage": param_count["percentage"],
        "estimated_total_memory_mb": total_memory_mb,
        "estimated_trainable_memory_mb": trainable_memory_mb,
    }
