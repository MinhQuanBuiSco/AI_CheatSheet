#!/usr/bin/env python3
"""
Production SFT Training Runner
Convenient entry point for running complete training pipeline with your processed data.
"""

import os
import sys
import argparse
import yaml
import logging
from pathlib import Path

# Add current directory to Python path
sys.path.append(str(Path(__file__).parent))

from sft_trainer import SFTConfig, ProductionSFTTrainer
from utils.evaluation import EvaluationConfig, ComprehensiveEvaluator


def setup_logging():
    """Setup basic logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
        
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def create_sft_config(config_dict: dict, args) -> SFTConfig:
    """Create SFT configuration from dict and command line args."""
    
    # Start with base config
    sft_config = {
        # Model settings
        "model_name": config_dict.get("model", {}).get("name", "microsoft/DialoGPT-small"),
        "model_revision": config_dict.get("model", {}).get("revision", "main"),
        
        # Dataset settings
        "dataset_path": config_dict.get("dataset", {}).get("path", args.dataset_path),
        "text_column": config_dict.get("dataset", {}).get("text_column", "text"),
        "max_seq_length": config_dict.get("dataset", {}).get("max_seq_length", 512),
        "train_test_split": config_dict.get("dataset", {}).get("train_test_split", 0.9),
        
        # Training settings
        "output_dir": args.output_dir,
        "num_train_epochs": config_dict.get("training", {}).get("num_train_epochs", 3),
        "per_device_train_batch_size": config_dict.get("training", {}).get("per_device_train_batch_size", 4),
        "per_device_eval_batch_size": config_dict.get("training", {}).get("per_device_eval_batch_size", 8),
        "gradient_accumulation_steps": config_dict.get("training", {}).get("gradient_accumulation_steps", 4),
        "learning_rate": float(config_dict.get("training", {}).get("learning_rate", 5e-5)),
        "weight_decay": float(config_dict.get("training", {}).get("weight_decay", 0.01)),
        "warmup_ratio": float(config_dict.get("training", {}).get("warmup_ratio", 0.03)),
        
        # Optimization
        "fp16": config_dict.get("training", {}).get("fp16", True),
        "gradient_checkpointing": config_dict.get("training", {}).get("gradient_checkpointing", True),
        
        # LoRA settings
        "use_lora": config_dict.get("lora", {}).get("enabled", True),
        "lora_r": config_dict.get("lora", {}).get("r", 16),
        "lora_alpha": config_dict.get("lora", {}).get("alpha", 32),
        "lora_dropout": float(config_dict.get("lora", {}).get("dropout", 0.1)),
        
        # Evaluation settings
        "evaluation_strategy": config_dict.get("evaluation", {}).get("strategy", "steps"),
        "eval_steps": config_dict.get("evaluation", {}).get("eval_steps", 100),
        "save_steps": config_dict.get("evaluation", {}).get("save_steps", 100),
        "logging_steps": config_dict.get("evaluation", {}).get("logging_steps", 10),
        
        # Monitoring
        "use_wandb": config_dict.get("monitoring", {}).get("use_wandb", True),
        "wandb_project": config_dict.get("monitoring", {}).get("wandb_project", "llm-sft-training"),
    }
    
    # Override with command line arguments
    if args.model_name:
        sft_config["model_name"] = args.model_name
    if args.epochs:
        sft_config["num_train_epochs"] = args.epochs
    if args.batch_size:
        sft_config["per_device_train_batch_size"] = args.batch_size
    if args.learning_rate:
        sft_config["learning_rate"] = args.learning_rate
    if args.no_wandb:
        sft_config["use_wandb"] = False
        
    return SFTConfig(**sft_config)


def run_training(config: SFTConfig, logger: logging.Logger):
    """Run the training process."""
    logger.info("=== Starting SFT Training ===")
    logger.info(f"Model: {config.model_name}")
    logger.info(f"Dataset: {config.dataset_path}")
    logger.info(f"Output: {config.output_dir}")
    logger.info(f"Epochs: {config.num_train_epochs}")
    logger.info(f"Batch size: {config.per_device_train_batch_size}")
    logger.info(f"Learning rate: {config.learning_rate}")
    logger.info(f"LoRA enabled: {config.use_lora}")
    
    # Create trainer and run
    trainer = ProductionSFTTrainer(config)
    trainer.train()
    
    logger.info("=== Training Completed ===")
    return config.output_dir


def run_evaluation(model_path: str, dataset_path: str, output_dir: str, logger: logging.Logger):
    """Run model evaluation."""
    logger.info("=== Starting Model Evaluation ===")
    
    eval_config = EvaluationConfig(
        model_path=model_path,
        test_data_path=dataset_path,
        output_dir=output_dir,
        max_samples=500,  # Limit for demo
        batch_size=4
    )
    
    evaluator = ComprehensiveEvaluator(eval_config)
    results = evaluator.run_comprehensive_evaluation()
    
    logger.info("=== Evaluation Completed ===")
    
    # Print key metrics
    for dataset_name, dataset_results in results.items():
        if dataset_name == "evaluation_summary":
            continue
        logger.info(f"\n{dataset_name} Results:")
        for metric in ["perplexity", "bleu_4", "rouge_l", "distinct_1"]:
            if metric in dataset_results:
                logger.info(f"  {metric}: {dataset_results[metric]:.4f}")
                
    return results


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Production SFT Training with Your Processed Data",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Configuration
    parser.add_argument(
        "--config", 
        type=str, 
        default="config/sft_config.yaml",
        help="Path to configuration file"
    )
    
    # Data and model
    parser.add_argument(
        "--dataset-path",
        type=str,
        default="../processed_data/processed_dataset.parquet",
        help="Path to your processed dataset"
    )
    parser.add_argument(
        "--model-name",
        type=str,
        help="Model to fine-tune (overrides config)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./outputs/sft-model",
        help="Output directory for trained model"
    )
    
    # Training parameters
    parser.add_argument("--epochs", type=int, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, help="Training batch size")
    parser.add_argument("--learning-rate", type=float, help="Learning rate")
    
    # Options
    parser.add_argument("--no-wandb", action="store_true", help="Disable W&B logging")
    parser.add_argument("--skip-training", action="store_true", help="Skip training, only evaluate")
    parser.add_argument("--skip-evaluation", action="store_true", help="Skip evaluation after training")
    parser.add_argument("--eval-only", action="store_true", help="Only run evaluation on existing model")
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging()
    
    try:
        # Check if dataset exists
        if not os.path.exists(args.dataset_path):
            logger.error(f"Dataset not found: {args.dataset_path}")
            logger.info("Make sure you've run the data pipeline first!")
            return 1
            
        # Load configuration
        config_dict = {}
        if os.path.exists(args.config):
            config_dict = load_config(args.config)
            logger.info(f"Loaded config from {args.config}")
        else:
            logger.warning(f"Config file not found: {args.config}, using defaults")
            
        model_path = args.output_dir
        
        # Run training
        if not args.skip_training and not args.eval_only:
            config = create_sft_config(config_dict, args)
            model_path = run_training(config, logger)
            
        # Run evaluation
        if not args.skip_evaluation:
            if args.eval_only or not args.skip_training:
                eval_output_dir = f"{model_path}/evaluation"
                run_evaluation(model_path, args.dataset_path, eval_output_dir, logger)
                
        logger.info("=== Pipeline Completed Successfully ===")
        logger.info(f"Model saved to: {model_path}")
        
        # Show next steps
        logger.info("\n=== Next Steps ===")
        logger.info("1. Review training logs and metrics")
        logger.info("2. Check evaluation results")
        logger.info("3. Deploy model for serving:")
        logger.info(f"   python utils/deployment.py --model-path {model_path}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())