"""PPO (Proximal Policy Optimization) Trainer."""

from typing import Dict, Any, Optional
import torch
from trl import PPOTrainer as TRLPPOTrainer, PPOConfig as TRLPPOConfig, AutoModelForCausalLMWithValueHead
from transformers import GenerationConfig
from rich.console import Console
from tqdm import tqdm

from .base_trainer import BaseRLTrainer
from ..config import PPOConfig
from ..data import get_preprocessor
from ..models import load_reward_model, compute_reward

console = Console()


class PPOTrainer(BaseRLTrainer):
    """Trainer for PPO (Proximal Policy Optimization)."""

    def __init__(self, config: PPOConfig):
        """
        Initialize PPO trainer.

        Args:
            config: PPO configuration
        """
        super().__init__(config)
        self.config: PPOConfig = config
        self.trainer: Optional[TRLPPOTrainer] = None
        self.reward_model = None
        self.reward_tokenizer = None

    def setup(self):
        """Setup model, tokenizer, reward model, and datasets."""
        # First run base setup
        super().setup()

        # Load reward model
        console.print("[cyan]Loading reward model...[/cyan]")
        self.reward_model, self.reward_tokenizer = load_reward_model(
            model_name_or_path=self.config.reward_model_name_or_path,
            device=self.config.reward_model_device,
        )
        console.print("[green]✓ Reward model loaded[/green]\n")

    def _preprocess_datasets(self):
        """Preprocess datasets for PPO training."""
        preprocessor = get_preprocessor(
            method="ppo",
            tokenizer=self.tokenizer,
            max_length=self.config.dataset.max_length,
        )

        self.train_dataset = preprocessor(self.train_dataset)
        if self.eval_dataset:
            self.eval_dataset = preprocessor(self.eval_dataset)

    def train(self) -> Dict[str, Any]:
        """
        Run PPO training.

        Returns:
            Training metrics
        """
        console.print("[bold green]Starting PPO Training[/bold green]\n")

        # Wrap model with value head
        if not isinstance(self.model, AutoModelForCausalLMWithValueHead):
            console.print("[cyan]Adding value head to model...[/cyan]")
            self.model = AutoModelForCausalLMWithValueHead.from_pretrained(
                self.model,
            )

        # Create PPO config
        ppo_config = TRLPPOConfig(
            model_name=self.config.model.model_name_or_path,
            learning_rate=self.config.training.learning_rate,
            batch_size=self.config.batch_size,
            mini_batch_size=self.config.per_device_train_batch_size,
            gradient_accumulation_steps=self.config.training.gradient_accumulation_steps,
            optimize_device_cache=self.config.optimize_device_cache,
            early_stopping=False,
            target_kl=self.config.target_kl,
            ppo_epochs=self.config.ppo_epochs,
            seed=self.config.training.seed,
            init_kl_coef=self.config.init_kl_coef,
            adap_kl_ctrl=self.config.adap_kl_ctrl,
            tracker_project_name=self.config.logging.wandb_project,
        )

        # Create PPO trainer
        self.trainer = TRLPPOTrainer(
            config=ppo_config,
            model=self.model,
            tokenizer=self.tokenizer,
            dataset=self.train_dataset,
        )

        # Generation config
        generation_config = GenerationConfig(
            max_new_tokens=self.config.max_new_tokens,
            temperature=self.config.temperature,
            top_k=self.config.top_k,
            top_p=self.config.top_p,
            do_sample=self.config.do_sample,
            pad_token_id=self.tokenizer.pad_token_id,
            eos_token_id=self.tokenizer.eos_token_id,
        )

        # Training loop
        console.print("[cyan]Starting PPO training loop...[/cyan]\n")

        all_stats = []
        for epoch in range(self.config.training.num_train_epochs):
            console.print(f"[bold]Epoch {epoch + 1}/{self.config.training.num_train_epochs}[/bold]")

            for batch in tqdm(self.trainer.dataloader, desc=f"Epoch {epoch + 1}"):
                # Get queries
                query_tensors = batch["input_ids"]

                # Generate responses
                with torch.no_grad():
                    response_tensors = self.trainer.generate(
                        query_tensors,
                        return_prompt=False,
                        generation_config=generation_config,
                    )

                # Compute rewards
                batch_rewards = []
                for query, response in zip(query_tensors, response_tensors):
                    # Decode query and response
                    query_text = self.tokenizer.decode(query, skip_special_tokens=True)
                    response_text = self.tokenizer.decode(response, skip_special_tokens=True)

                    # Compute reward
                    reward = compute_reward(
                        model=self.reward_model,
                        tokenizer=self.reward_tokenizer,
                        prompt=query_text,
                        response=response_text,
                    )
                    batch_rewards.append(torch.tensor(reward))

                # Run PPO step
                stats = self.trainer.step(query_tensors, response_tensors, batch_rewards)
                all_stats.append(stats)

                # Log stats
                self.trainer.log_stats(
                    stats=stats,
                    batch=batch,
                    rewards=batch_rewards,
                )

        # Save model
        self.save_model()

        # Compile metrics
        metrics = self._compile_metrics(all_stats)

        console.print("\n[bold green]✓ PPO Training Complete![/bold green]")
        return metrics

    def _compile_metrics(self, all_stats: list) -> Dict[str, Any]:
        """
        Compile training metrics from all steps.

        Args:
            all_stats: List of stats from each step

        Returns:
            Aggregated metrics
        """
        if not all_stats:
            return {}

        # Average metrics across all steps
        metrics = {}
        for key in all_stats[0].keys():
            values = [stats[key] for stats in all_stats if key in stats]
            if values:
                if isinstance(values[0], (int, float)):
                    metrics[f"train_{key}"] = sum(values) / len(values)

        return metrics

    def _run_evaluation(self) -> Dict[str, Any]:
        """
        Run PPO evaluation.

        Returns:
            Evaluation metrics
        """
        if self.eval_dataset is None:
            return {}

        console.print("[cyan]Running PPO evaluation...[/cyan]")

        generation_config = GenerationConfig(
            max_new_tokens=self.config.max_new_tokens,
            temperature=self.config.temperature,
            top_k=self.config.top_k,
            top_p=self.config.top_p,
            do_sample=self.config.do_sample,
            pad_token_id=self.tokenizer.pad_token_id,
            eos_token_id=self.tokenizer.eos_token_id,
        )

        total_reward = 0
        num_samples = 0

        for batch in tqdm(self.eval_dataset, desc="Evaluating"):
            query = batch["input_ids"]

            # Generate response
            with torch.no_grad():
                response = self.trainer.generate(
                    [query],
                    return_prompt=False,
                    generation_config=generation_config,
                )[0]

            # Compute reward
            query_text = self.tokenizer.decode(query, skip_special_tokens=True)
            response_text = self.tokenizer.decode(response, skip_special_tokens=True)

            reward = compute_reward(
                model=self.reward_model,
                tokenizer=self.reward_tokenizer,
                prompt=query_text,
                response=response_text,
            )

            total_reward += reward
            num_samples += 1

        avg_reward = total_reward / num_samples if num_samples > 0 else 0

        metrics = {
            "eval_avg_reward": avg_reward,
            "eval_num_samples": num_samples,
        }

        console.print(f"[green]Average Reward: {avg_reward:.4f}[/green]")

        return metrics
