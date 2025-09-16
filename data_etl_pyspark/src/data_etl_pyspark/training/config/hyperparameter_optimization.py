"""
Advanced Hyperparameter Optimization for SFT Training
Production-ready HPO with Ray Tune, Optuna, and distributed search
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
import yaml

import optuna
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler
import ray
from ray import tune
from ray.tune.schedulers import ASHAScheduler
from ray.tune.search.optuna import OptunaSearch

from sft_trainer import SFTConfig, ProductionSFTTrainer


@dataclass
class HPOConfig:
    """Configuration for Hyperparameter Optimization."""
    
    # Search space configuration
    search_space: Dict[str, Any]
    
    # Optimization settings
    n_trials: int = 50
    study_name: str = "sft_optimization"
    direction: str = "minimize"  # "minimize" for loss, "maximize" for accuracy
    metric_name: str = "eval_loss"
    
    # Pruning and early stopping
    enable_pruning: bool = True
    patience: int = 3
    min_resource: int = 1  # Minimum epochs before pruning
    max_resource: int = 10  # Maximum epochs
    
    # Resource allocation
    max_concurrent_trials: int = 4
    cpu_per_trial: int = 2
    gpu_per_trial: float = 0.25
    
    # Storage and logging
    storage_url: Optional[str] = None  # Database URL for Optuna study
    output_dir: str = "./hpo_results"
    log_level: str = "INFO"
    
    # Advanced features
    use_ray_tune: bool = True
    enable_multi_objective: bool = False
    objectives: List[str] = None  # For multi-objective optimization


class HyperparameterOptimizer:
    """Production-grade hyperparameter optimization system."""
    
    def __init__(self, base_config: SFTConfig, hpo_config: HPOConfig):
        self.base_config = base_config
        self.hpo_config = hpo_config
        self.setup_logging()
        self.best_trial = None
        self.study = None
        
        # Create output directory
        Path(hpo_config.output_dir).mkdir(parents=True, exist_ok=True)
        
    def setup_logging(self):
        """Setup logging for HPO."""
        logging.basicConfig(
            level=getattr(logging, self.hpo_config.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def create_search_space(self) -> Dict[str, Any]:
        """Create comprehensive search space for SFT training."""
        
        # Default search space optimized for production
        default_search_space = {
            # Learning rate (log scale)
            "learning_rate": {
                "type": "loguniform",
                "low": 1e-6,
                "high": 1e-3
            },
            
            # Batch size (discrete values)
            "per_device_train_batch_size": {
                "type": "choice",
                "choices": [2, 4, 8, 16]
            },
            
            # Gradient accumulation
            "gradient_accumulation_steps": {
                "type": "choice", 
                "choices": [1, 2, 4, 8, 16]
            },
            
            # Weight decay
            "weight_decay": {
                "type": "uniform",
                "low": 0.0,
                "high": 0.1
            },
            
            # Warmup ratio
            "warmup_ratio": {
                "type": "uniform",
                "low": 0.0,
                "high": 0.2
            },
            
            # LoRA parameters
            "lora_r": {
                "type": "choice",
                "choices": [4, 8, 16, 32, 64]
            },
            
            "lora_alpha": {
                "type": "choice", 
                "choices": [8, 16, 32, 64, 128]
            },
            
            "lora_dropout": {
                "type": "uniform",
                "low": 0.0,
                "high": 0.3
            },
            
            # Optimization method
            "optim": {
                "type": "choice",
                "choices": ["adamw_torch", "adamw_hf", "adafactor"]
            },
            
            # Learning rate scheduler
            "lr_scheduler_type": {
                "type": "choice",
                "choices": ["linear", "cosine", "cosine_with_restarts", "polynomial"]
            },
            
            # Max sequence length
            "max_seq_length": {
                "type": "choice",
                "choices": [256, 512, 1024]
            }
        }
        
        # Use custom search space if provided, otherwise default
        return self.hpo_config.search_space or default_search_space
        
    def sample_hyperparameters(self, trial) -> SFTConfig:
        """Sample hyperparameters for a trial."""
        search_space = self.create_search_space()
        sampled_params = {}
        
        for param_name, config in search_space.items():
            if config["type"] == "uniform":
                value = trial.suggest_uniform(param_name, config["low"], config["high"])
            elif config["type"] == "loguniform":
                value = trial.suggest_loguniform(param_name, config["low"], config["high"])
            elif config["type"] == "choice":
                value = trial.suggest_categorical(param_name, config["choices"])
            elif config["type"] == "int":
                value = trial.suggest_int(param_name, config["low"], config["high"])
            else:
                self.logger.warning(f"Unknown parameter type: {config['type']}")
                continue
                
            sampled_params[param_name] = value
            
        # Create new config with sampled parameters
        config_dict = asdict(self.base_config)
        config_dict.update(sampled_params)
        
        # Adjust related parameters
        if "lora_r" in sampled_params:
            # Alpha typically 2x rank
            config_dict["lora_alpha"] = sampled_params.get("lora_alpha", sampled_params["lora_r"] * 2)
            
        # Create unique output directory for this trial
        trial_dir = Path(self.hpo_config.output_dir) / f"trial_{trial.number}"
        config_dict["output_dir"] = str(trial_dir)
        
        return SFTConfig(**config_dict)
        
    def objective_function(self, trial) -> float:
        """Objective function for optimization."""
        try:
            # Sample hyperparameters
            config = self.sample_hyperparameters(trial)
            
            # Log trial parameters
            self.logger.info(f"Trial {trial.number}: Testing parameters:")
            for key, value in trial.params.items():
                self.logger.info(f"  {key}: {value}")
                
            # Create and run trainer
            trainer = ProductionSFTTrainer(config)
            
            # Add pruning callback for early stopping
            def report_callback(logs):
                if self.hpo_config.enable_pruning:
                    step = logs.get("step", 0)
                    eval_loss = logs.get("eval_loss")
                    if eval_loss is not None:
                        trial.report(eval_loss, step)
                        if trial.should_prune():
                            raise optuna.TrialPruned()
                            
            # Train model (you might want to add the callback to the trainer)
            trainer.train()
            
            # Load results
            results_file = Path(config.output_dir) / "training_results.json"
            if results_file.exists():
                with open(results_file, 'r') as f:
                    results = json.load(f)
                    
                # Return the metric we're optimizing
                metric_value = results.get(self.hpo_config.metric_name, float('inf'))
                
                self.logger.info(f"Trial {trial.number} completed with {self.hpo_config.metric_name}: {metric_value}")
                return metric_value
            else:
                self.logger.error(f"Results file not found for trial {trial.number}")
                return float('inf')
                
        except optuna.TrialPruned:
            self.logger.info(f"Trial {trial.number} pruned")
            raise
        except Exception as e:
            self.logger.error(f"Trial {trial.number} failed: {e}")
            return float('inf')
            
    def optimize_with_optuna(self) -> optuna.Study:
        """Run optimization using Optuna."""
        self.logger.info("Starting hyperparameter optimization with Optuna...")
        
        # Create study
        study = optuna.create_study(
            study_name=self.hpo_config.study_name,
            direction=self.hpo_config.direction,
            storage=self.hpo_config.storage_url,
            load_if_exists=True,
            sampler=TPESampler(seed=42),
            pruner=MedianPruner(
                n_startup_trials=5,
                n_warmup_steps=10
            ) if self.hpo_config.enable_pruning else None
        )
        
        # Run optimization
        study.optimize(
            self.objective_function,
            n_trials=self.hpo_config.n_trials,
            n_jobs=1  # Single process for now
        )
        
        self.study = study
        self.best_trial = study.best_trial
        
        return study
        
    def optimize_with_ray_tune(self) -> ray.tune.ExperimentAnalysis:
        """Run optimization using Ray Tune for distributed HPO."""
        self.logger.info("Starting hyperparameter optimization with Ray Tune...")
        
        # Initialize Ray
        if not ray.is_initialized():
            ray.init(ignore_reinit_error=True)
            
        # Convert search space to Ray Tune format
        search_space = self.create_search_space()
        tune_search_space = {}
        
        for param_name, config in search_space.items():
            if config["type"] == "uniform":
                tune_search_space[param_name] = tune.uniform(config["low"], config["high"])
            elif config["type"] == "loguniform":
                tune_search_space[param_name] = tune.loguniform(config["low"], config["high"])
            elif config["type"] == "choice":
                tune_search_space[param_name] = tune.choice(config["choices"])
            elif config["type"] == "int":
                tune_search_space[param_name] = tune.randint(config["low"], config["high"])
                
        # Create trainable function
        def trainable(config_dict):
            # Merge with base config
            merged_config = asdict(self.base_config)
            merged_config.update(config_dict)
            merged_config["output_dir"] = tune.get_trial_dir()
            
            config = SFTConfig(**merged_config)
            trainer = ProductionSFTTrainer(config)
            trainer.train()
            
            # Load results and report
            results_file = Path(config.output_dir) / "training_results.json"
            if results_file.exists():
                with open(results_file, 'r') as f:
                    results = json.load(f)
                tune.report(eval_loss=results.get("eval_loss", float('inf')))
                
        # Setup search algorithm and scheduler
        search_alg = OptunaSearch(
            metric=self.hpo_config.metric_name,
            mode="min" if self.hpo_config.direction == "minimize" else "max"
        )
        
        scheduler = ASHAScheduler(
            time_attr="training_iteration",
            metric=self.hpo_config.metric_name,
            mode="min" if self.hpo_config.direction == "minimize" else "max",
            max_t=self.hpo_config.max_resource,
            grace_period=self.hpo_config.min_resource,
            reduction_factor=2
        )
        
        # Run tuning
        analysis = tune.run(
            trainable,
            config=tune_search_space,
            num_samples=self.hpo_config.n_trials,
            search_alg=search_alg,
            scheduler=scheduler,
            resources_per_trial={
                "cpu": self.hpo_config.cpu_per_trial,
                "gpu": self.hpo_config.gpu_per_trial
            },
            max_concurrent_trials=self.hpo_config.max_concurrent_trials,
            local_dir=self.hpo_config.output_dir,
            name="sft_hpo",
            verbose=1
        )
        
        return analysis
        
    def run_optimization(self) -> Dict[str, Any]:
        """Run the complete hyperparameter optimization."""
        self.logger.info("=== Starting Hyperparameter Optimization ===")
        
        if self.hpo_config.use_ray_tune:
            analysis = self.optimize_with_ray_tune()
            best_config = analysis.best_config
            best_result = analysis.best_result
        else:
            study = self.optimize_with_optuna()
            best_config = study.best_params
            best_result = {"best_value": study.best_value}
            
        # Save best configuration
        self.save_best_config(best_config, best_result)
        
        return {
            "best_config": best_config,
            "best_result": best_result,
            "optimization_summary": self.get_optimization_summary()
        }
        
    def save_best_config(self, best_config: Dict[str, Any], best_result: Dict[str, Any]):
        """Save the best configuration and results."""
        results = {
            "best_hyperparameters": best_config,
            "best_metrics": best_result,
            "optimization_config": asdict(self.hpo_config),
            "base_config": asdict(self.base_config),
            "timestamp": str(datetime.now())
        }
        
        results_file = Path(self.hpo_config.output_dir) / "best_hyperparameters.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
            
        # Save as YAML for easy reading
        yaml_file = Path(self.hpo_config.output_dir) / "best_config.yaml"
        with open(yaml_file, 'w') as f:
            yaml.dump(best_config, f, default_flow_style=False)
            
        self.logger.info(f"Best configuration saved to {results_file}")
        self.logger.info(f"Best hyperparameters: {best_config}")
        
    def get_optimization_summary(self) -> Dict[str, Any]:
        """Get summary of optimization results."""
        summary = {
            "total_trials": self.hpo_config.n_trials,
            "search_space_size": len(self.create_search_space()),
            "optimization_metric": self.hpo_config.metric_name,
            "optimization_direction": self.hpo_config.direction,
        }
        
        if self.study:
            summary.update({
                "completed_trials": len(self.study.trials),
                "pruned_trials": len([t for t in self.study.trials if t.state == optuna.trial.TrialState.PRUNED]),
                "failed_trials": len([t for t in self.study.trials if t.state == optuna.trial.TrialState.FAIL]),
                "best_value": self.study.best_value,
            })
            
        return summary


def create_hpo_config_from_yaml(config_path: str) -> HPOConfig:
    """Load HPO configuration from YAML file."""
    with open(config_path, 'r') as f:
        config_dict = yaml.safe_load(f)
        
    return HPOConfig(**config_dict.get('hyperparameter_optimization', {}))


def main():
    """Main function for running hyperparameter optimization."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Hyperparameter Optimization for SFT")
    parser.add_argument("--base-config", type=str, required=True, help="Base training configuration")
    parser.add_argument("--hpo-config", type=str, help="HPO configuration file")
    parser.add_argument("--n-trials", type=int, default=50, help="Number of optimization trials")
    parser.add_argument("--output-dir", type=str, default="./hpo_results", help="Output directory")
    parser.add_argument("--use-ray", action="store_true", help="Use Ray Tune for distributed optimization")
    
    args = parser.parse_args()
    
    # Load base configuration
    with open(args.base_config, 'r') as f:
        base_config_dict = yaml.safe_load(f)
    base_config = SFTConfig(**base_config_dict)
    
    # Create HPO configuration
    if args.hpo_config and os.path.exists(args.hpo_config):
        hpo_config = create_hpo_config_from_yaml(args.hpo_config)
    else:
        hpo_config = HPOConfig(
            search_space={},  # Use default
            n_trials=args.n_trials,
            output_dir=args.output_dir,
            use_ray_tune=args.use_ray
        )
        
    # Run optimization
    optimizer = HyperparameterOptimizer(base_config, hpo_config)
    results = optimizer.run_optimization()
    
    print("=== Optimization Complete ===")
    print(f"Best configuration: {results['best_config']}")
    print(f"Best result: {results['best_result']}")


if __name__ == "__main__":
    main()