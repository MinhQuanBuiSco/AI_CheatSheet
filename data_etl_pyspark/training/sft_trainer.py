"""
Production-level Supervised Fine-Tuning (SFT) Implementation
Optimized for big tech scale with comprehensive monitoring, error handling, and distributed training support.
"""

import os
import json
import time
import logging
import warnings
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Union, List
from pathlib import Path

import torch
import torch.distributed as dist
from torch.utils.data import DataLoader
import pandas as pd
from datasets import Dataset, load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
    EarlyStoppingCallback,
    Trainer
)
from transformers.integrations import WandbCallback
from peft import LoraConfig, get_peft_model, TaskType
# from trl import SFTTrainer  # Not needed, using standard Trainer
import wandb
import pyarrow.parquet as pq

# Suppress unnecessary warnings
warnings.filterwarnings("ignore", category=UserWarning)
os.environ["TOKENIZERS_PARALLELISM"] = "false"

@dataclass
class SFTConfig:
    """Comprehensive configuration for SFT training."""
    
    # Model Configuration
    model_name: str = "microsoft/DialoGPT-small"
    model_revision: str = "main"
    use_auth_token: bool = False
    trust_remote_code: bool = False
    
    # Dataset Configuration
    dataset_path: str = "../processed_data/processed_dataset.parquet"
    text_column: str = "text"
    max_seq_length: int = 512
    train_test_split: float = 0.9
    dataset_streaming: bool = False
    
    # Training Configuration
    output_dir: str = "./outputs/sft-model"
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 4
    per_device_eval_batch_size: int = 8
    gradient_accumulation_steps: int = 4
    learning_rate: float = 5e-5
    weight_decay: float = 0.01
    warmup_ratio: float = 0.03
    lr_scheduler_type: str = "cosine"
    max_grad_norm: float = 1.0
    
    # LoRA Configuration
    use_lora: bool = True
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.1
    lora_target_modules: List[str] = field(default_factory=lambda: ["q_proj", "v_proj", "k_proj", "o_proj"])
    
    # Optimization
    fp16: bool = True
    bf16: bool = False  # Set to True for A100/H100
    gradient_checkpointing: bool = True
    dataloader_num_workers: int = 4
    dataloader_pin_memory: bool = True
    optim: str = "adamw_torch"
    
    # Evaluation & Monitoring
    evaluation_strategy: str = "steps"
    eval_steps: int = 100
    save_strategy: str = "steps"
    save_steps: int = 100
    logging_steps: int = 10
    load_best_model_at_end: bool = True
    metric_for_best_model: str = "eval_loss"
    greater_is_better: bool = False
    save_total_limit: int = 3
    
    # Early Stopping
    early_stopping_patience: int = 5
    early_stopping_threshold: float = 0.001
    
    # Monitoring
    use_wandb: bool = True
    wandb_project: str = "llm-sft-training"
    wandb_run_name: Optional[str] = None
    report_to: List[str] = field(default_factory=lambda: ["wandb", "tensorboard"])
    
    # Hardware & Distributed
    local_rank: int = -1
    deepspeed_config: Optional[str] = None
    fsdp: bool = False
    
    # Reproducibility
    seed: int = 42
    data_seed: int = 42
    
    # Advanced Features
    resume_from_checkpoint: Optional[str] = None
    push_to_hub: bool = False
    hub_model_id: Optional[str] = None
    hub_strategy: str = "every_save"


class ProductionSFTTrainer:
    """Production-grade SFT trainer with comprehensive monitoring and error handling."""
    
    def __init__(self, config: SFTConfig):
        self.config = config
        self.start_time = time.time()
        
        # Setup logging
        self.setup_logging()
        
        # Setup distributed training
        self.setup_distributed()
        
        # Initialize monitoring
        self.setup_monitoring()
        
        self.logger.info("=== Production SFT Training Initialized ===")
        self.logger.info(f"Model: {config.model_name}")
        self.logger.info(f"Dataset: {config.dataset_path}")
        self.logger.info(f"Output: {config.output_dir}")
        
    def setup_logging(self):
        """Setup comprehensive logging."""
        log_dir = Path(self.config.output_dir) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"sft_training_{timestamp}.log"
        
        # Configure logger
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Logging initialized. Log file: {log_file}")
        
    def setup_distributed(self):
        """Setup distributed training environment."""
        self.is_distributed = False
        
        if "RANK" in os.environ and "WORLD_SIZE" in os.environ:
            self.is_distributed = True
            rank = int(os.environ["RANK"])
            world_size = int(os.environ["WORLD_SIZE"])
            
            # Initialize distributed training
            if not dist.is_initialized():
                dist.init_process_group(backend="nccl")
                
            self.logger.info(f"Distributed training initialized: rank {rank}/{world_size}")
            
            # Set device
            torch.cuda.set_device(rank % torch.cuda.device_count())
            
    def setup_monitoring(self):
        """Initialize monitoring tools."""
        self.metrics = {
            "training_time": 0,
            "data_loading_time": 0,
            "model_loading_time": 0,
            "total_samples": 0,
            "best_eval_loss": float('inf'),
            "training_losses": [],
            "eval_losses": []
        }
        
        # Initialize W&B if enabled
        if self.config.use_wandb and (not self.is_distributed or dist.get_rank() == 0):
            try:
                wandb.init(
                    project=self.config.wandb_project,
                    name=self.config.wandb_run_name or f"sft-{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    config=self.config.__dict__,
                    tags=["sft", "production", self.config.model_name.split('/')[-1]]
                )
                self.logger.info("W&B monitoring initialized")
            except Exception as e:
                self.logger.warning(f"W&B initialization failed: {e}")
                self.config.use_wandb = False
                
    def load_dataset(self) -> Dataset:
        """Load and preprocess dataset with comprehensive error handling."""
        self.logger.info("Loading dataset...")
        load_start = time.time()
        
        try:
            # Load processed parquet data
            if self.config.dataset_path.endswith('.parquet'):
                # Handle parquet directory or file
                if os.path.isdir(self.config.dataset_path):
                    table = pq.read_table(self.config.dataset_path)
                    df = table.to_pandas()
                else:
                    df = pd.read_parquet(self.config.dataset_path)
                    
                # Convert to HuggingFace dataset
                dataset = Dataset.from_pandas(df)
                
            else:
                # Load from HuggingFace Hub
                dataset = load_dataset(
                    self.config.dataset_path,
                    streaming=self.config.dataset_streaming
                )["train"]
                
            # Validate required columns
            if self.config.text_column not in dataset.column_names:
                raise ValueError(f"Text column '{self.config.text_column}' not found in dataset. "
                               f"Available columns: {dataset.column_names}")
                
            # Dataset statistics
            total_samples = len(dataset) if hasattr(dataset, '__len__') else "unknown (streaming)"
            self.metrics["total_samples"] = total_samples if isinstance(total_samples, int) else 0
            
            self.logger.info(f"Dataset loaded: {total_samples} samples")
            self.logger.info(f"Columns: {dataset.column_names}")
            
            # Train/eval split
            if self.config.train_test_split < 1.0:
                dataset = dataset.train_test_split(
                    train_size=self.config.train_test_split,
                    seed=self.config.data_seed
                )
                train_dataset = dataset["train"]
                eval_dataset = dataset["test"]
                
                self.logger.info(f"Train samples: {len(train_dataset)}")
                self.logger.info(f"Eval samples: {len(eval_dataset)}")
            else:
                train_dataset = dataset
                eval_dataset = None
                
            self.metrics["data_loading_time"] = time.time() - load_start
            self.logger.info(f"Dataset loading completed in {self.metrics['data_loading_time']:.2f}s")
            
            return train_dataset, eval_dataset
            
        except Exception as e:
            self.logger.error(f"Failed to load dataset: {e}")
            raise
            
    def load_model_and_tokenizer(self):
        """Load model and tokenizer with optimization configurations."""
        self.logger.info("Loading model and tokenizer...")
        load_start = time.time()
        
        try:
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_name,
                revision=self.config.model_revision,
                use_auth_token=self.config.use_auth_token,
                trust_remote_code=self.config.trust_remote_code
            )
            
            # Add pad token if missing
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
                self.logger.info("Added pad token (using eos_token)")
                
            # Load model with optimization
            device_map = "auto" if torch.cuda.device_count() > 1 and not self.is_distributed else None
            
            model_kwargs = {
                "revision": self.config.model_revision,
                "use_auth_token": self.config.use_auth_token,
                "trust_remote_code": self.config.trust_remote_code,
                "torch_dtype": torch.float16 if self.config.fp16 else torch.float32,
                "device_map": device_map,
            }
            
            # Add quantization if needed (for memory efficiency)
            if torch.cuda.is_available():
                model_kwargs["low_cpu_mem_usage"] = True
                
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config.model_name,
                **model_kwargs
            )
            
            self.logger.info(f"Model loaded: {self.model.config.name_or_path}")
            self.logger.info(f"Model parameters: {self.model.num_parameters():,}")
            
            # Enable gradient checkpointing before LoRA
            if self.config.gradient_checkpointing:
                self.model.gradient_checkpointing_enable()
                self.logger.info("Gradient checkpointing enabled")
                
            # Apply LoRA if configured
            if self.config.use_lora:
                self.apply_lora()
                
            # Ensure model is in training mode
            self.model.train()
            
            # Check that some parameters require gradients
            trainable_params = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
            if trainable_params == 0:
                self.logger.error("No trainable parameters found! This will cause training to fail.")
                # If no LoRA, enable training for all parameters
                if not self.config.use_lora:
                    for param in self.model.parameters():
                        param.requires_grad = True
                    trainable_params = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
                    
            self.logger.info(f"Trainable parameters: {trainable_params:,}")
                
            self.metrics["model_loading_time"] = time.time() - load_start
            self.logger.info(f"Model loading completed in {self.metrics['model_loading_time']:.2f}s")
            
        except Exception as e:
            self.logger.error(f"Failed to load model: {e}")
            raise
            
    def apply_lora(self):
        """Apply LoRA (Low-Rank Adaptation) for parameter-efficient fine-tuning."""
        self.logger.info("Applying LoRA configuration...")
        
        try:
            # Auto-detect target modules if not specified or if they don't exist
            target_modules = self.config.lora_target_modules
            
            # Check if target modules exist in the model
            existing_modules = []
            for name, module in self.model.named_modules():
                if any(target in name for target in target_modules):
                    existing_modules.append(name.split('.')[-1])
                    
            if not existing_modules:
                # Fall back to common attention modules
                self.logger.warning("Specified target modules not found, trying common alternatives...")
                # Common alternatives for different architectures
                common_targets = ["q_proj", "v_proj", "k_proj", "o_proj", "query", "value", "key", "dense"]
                for name, module in self.model.named_modules():
                    module_name = name.split('.')[-1]
                    if module_name in common_targets and hasattr(module, 'weight'):
                        if module_name not in existing_modules:
                            existing_modules.append(module_name)
                            
                if existing_modules:
                    target_modules = list(set(existing_modules))
                    self.logger.info(f"Using auto-detected target modules: {target_modules}")
                else:
                    # Last resort - target all linear layers
                    target_modules = "all-linear"
                    self.logger.info("Using all linear layers as target modules")
            
            lora_config = LoraConfig(
                task_type=TaskType.CAUSAL_LM,
                r=self.config.lora_r,
                lora_alpha=self.config.lora_alpha,
                lora_dropout=self.config.lora_dropout,
                target_modules=target_modules,
                bias="none"
            )
            
            self.model = get_peft_model(self.model, lora_config)
            
            # Log trainable parameters
            trainable_params = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
            total_params = sum(p.numel() for p in self.model.parameters())
            
            self.logger.info(f"LoRA applied successfully")
            self.logger.info(f"Trainable parameters: {trainable_params:,} ({100 * trainable_params / total_params:.2f}%)")
            
            if trainable_params == 0:
                raise ValueError("LoRA resulted in 0 trainable parameters!")
            
        except Exception as e:
            self.logger.error(f"Failed to apply LoRA: {e}")
            self.logger.info("Falling back to full fine-tuning...")
            self.config.use_lora = False
            # Enable all parameters for training
            for param in self.model.parameters():
                param.requires_grad = True
            
    def create_training_arguments(self) -> TrainingArguments:
        """Create optimized training arguments."""
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        return TrainingArguments(
            # Basic training config
            output_dir=str(output_dir),
            num_train_epochs=self.config.num_train_epochs,
            per_device_train_batch_size=self.config.per_device_train_batch_size,
            per_device_eval_batch_size=self.config.per_device_eval_batch_size,
            gradient_accumulation_steps=self.config.gradient_accumulation_steps,
            
            # Optimization
            learning_rate=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
            warmup_ratio=self.config.warmup_ratio,
            lr_scheduler_type=self.config.lr_scheduler_type,
            max_grad_norm=self.config.max_grad_norm,
            optim=self.config.optim,
            
            # Precision and memory
            fp16=self.config.fp16,
            bf16=self.config.bf16,
            gradient_checkpointing=self.config.gradient_checkpointing,
            dataloader_num_workers=self.config.dataloader_num_workers,
            dataloader_pin_memory=self.config.dataloader_pin_memory,
            
            # Evaluation and saving
            eval_strategy=self.config.evaluation_strategy,
            eval_steps=self.config.eval_steps,
            save_strategy=self.config.save_strategy,
            save_steps=self.config.save_steps,
            logging_steps=self.config.logging_steps,
            load_best_model_at_end=self.config.load_best_model_at_end,
            metric_for_best_model=self.config.metric_for_best_model,
            greater_is_better=self.config.greater_is_better,
            save_total_limit=self.config.save_total_limit,
            
            # Monitoring
            report_to=self.config.report_to if self.config.use_wandb else [],
            
            # Reproducibility
            seed=self.config.seed,
            data_seed=self.config.data_seed,
            
            # Distributed training
            local_rank=self.config.local_rank,
            deepspeed=self.config.deepspeed_config,
            fsdp=["full_shard", "auto_wrap"] if self.config.fsdp else [],
            
            # Hub integration
            push_to_hub=self.config.push_to_hub,
            hub_model_id=self.config.hub_model_id,
            hub_strategy=self.config.hub_strategy,
            
            # Performance optimizations
            remove_unused_columns=False,
            include_inputs_for_metrics=True,
        )
        
    def preprocess_function(self, examples):
        """Preprocess examples for training."""
        # Tokenize with proper truncation and padding
        return self.tokenizer(
            examples[self.config.text_column],
            truncation=True,
            padding=False,  # Dynamic padding in data collator
            max_length=self.config.max_seq_length,
            return_overflowing_tokens=False,
        )
        
    def train(self):
        """Execute the complete training pipeline."""
        try:
            training_start = time.time()
            
            # 1. Load dataset
            train_dataset, eval_dataset = self.load_dataset()
            
            # 2. Load model and tokenizer
            self.load_model_and_tokenizer()
            
            # 3. Preprocess dataset
            self.logger.info("Preprocessing dataset...")
            preprocess_start = time.time()
            
            train_dataset = train_dataset.map(
                self.preprocess_function,
                batched=True,
                remove_columns=train_dataset.column_names,
                desc="Tokenizing train dataset",
            )
            
            if eval_dataset is not None:
                eval_dataset = eval_dataset.map(
                    self.preprocess_function,
                    batched=True,
                    remove_columns=eval_dataset.column_names,
                    desc="Tokenizing eval dataset",
                )
                
            self.logger.info(f"Preprocessing completed in {time.time() - preprocess_start:.2f}s")
            
            # 4. Create data collator
            data_collator = DataCollatorForLanguageModeling(
                tokenizer=self.tokenizer,
                mlm=False,  # Causal LM
                pad_to_multiple_of=8 if self.config.fp16 else None,
            )
            
            # 5. Setup training arguments
            training_args = self.create_training_arguments()
            
            # 6. Create trainer
            self.logger.info("Initializing trainer...")
            
            callbacks = []
            if eval_dataset is not None:
                callbacks.append(
                    EarlyStoppingCallback(
                        early_stopping_patience=self.config.early_stopping_patience,
                        early_stopping_threshold=self.config.early_stopping_threshold,
                    )
                )
                
            trainer = Trainer(
                model=self.model,
                args=training_args,
                train_dataset=train_dataset,
                eval_dataset=eval_dataset,
                tokenizer=self.tokenizer,
                data_collator=data_collator,
                callbacks=callbacks,
            )
            
            # 7. Resume from checkpoint if specified
            checkpoint_path = None
            if self.config.resume_from_checkpoint:
                if os.path.isdir(self.config.resume_from_checkpoint):
                    checkpoint_path = self.config.resume_from_checkpoint
                    self.logger.info(f"Resuming from checkpoint: {checkpoint_path}")
                    
            # 8. Start training
            self.logger.info("=== Starting Training ===")
            self.metrics["training_time"] = time.time()
            
            train_result = trainer.train(resume_from_checkpoint=checkpoint_path)
            
            self.metrics["training_time"] = time.time() - self.metrics["training_time"]
            
            # 9. Save final model
            self.logger.info("Saving final model...")
            trainer.save_model()
            self.tokenizer.save_pretrained(self.config.output_dir)
            
            # 10. Log final metrics
            self.log_final_results(train_result)
            
            # 11. Push to hub if configured
            if self.config.push_to_hub:
                self.logger.info("Pushing model to Hub...")
                trainer.push_to_hub()
                
            self.logger.info("=== Training Completed Successfully ===")
            
        except Exception as e:
            self.logger.error(f"Training failed: {e}")
            raise
        finally:
            # Cleanup
            if self.config.use_wandb:
                wandb.finish()
                
    def log_final_results(self, train_result):
        """Log comprehensive training results."""
        total_time = time.time() - self.start_time
        
        results = {
            "training_loss": train_result.training_loss,
            "train_runtime": train_result.metrics.get("train_runtime", 0),
            "train_samples_per_second": train_result.metrics.get("train_samples_per_second", 0),
            "total_training_time": self.metrics["training_time"],
            "data_loading_time": self.metrics["data_loading_time"],
            "model_loading_time": self.metrics["model_loading_time"],
            "total_pipeline_time": total_time,
            "total_samples": self.metrics["total_samples"],
        }
        
        # Save results
        results_file = Path(self.config.output_dir) / "training_results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
            
        # Log summary
        self.logger.info("=== Training Summary ===")
        self.logger.info(f"Final training loss: {train_result.training_loss:.4f}")
        self.logger.info(f"Training runtime: {train_result.metrics.get('train_runtime', 0):.2f}s")
        self.logger.info(f"Samples per second: {train_result.metrics.get('train_samples_per_second', 0):.2f}")
        self.logger.info(f"Total pipeline time: {total_time:.2f}s ({total_time/60:.1f} minutes)")
        self.logger.info(f"Results saved to: {results_file}")


def main():
    """Main training function with comprehensive error handling."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Production SFT Training")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument("--model-name", type=str, default="microsoft/DialoGPT-small")
    parser.add_argument("--dataset-path", type=str, default="./processed_data/processed_dataset.parquet")
    parser.add_argument("--output-dir", type=str, default="./outputs/sft-model")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--use-lora", action="store_true", default=True)
    parser.add_argument("--no-wandb", action="store_true", help="Disable W&B logging")
    
    args = parser.parse_args()
    
    # Create configuration
    config = SFTConfig(
        model_name=args.model_name,
        dataset_path=args.dataset_path,
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        use_lora=args.use_lora,
        use_wandb=not args.no_wandb,
    )
    
    # Load config file if provided
    if args.config and os.path.exists(args.config):
        import yaml
        with open(args.config, 'r') as f:
            config_dict = yaml.safe_load(f)
        
        # Update config with file values
        for key, value in config_dict.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    # Initialize and run trainer
    trainer = ProductionSFTTrainer(config)
    trainer.train()


if __name__ == "__main__":
    main()