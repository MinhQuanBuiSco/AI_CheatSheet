"""Example: Train a model using GRPO (Group Relative Policy Optimization)."""

from llm_rl.config import GRPOConfig
from llm_rl.trainers import train_grpo


def main():
    """Train GRPO model from config."""

    # Load configuration from YAML
    config = GRPOConfig.from_yaml("configs/training/grpo/base.yaml")

    # NOTE: GRPO requires a trained reward model
    # Make sure to train a reward model first using train_reward_model.py
    # and update the reward_model_name_or_path in the config

    # Train using simplified API
    # Note: GRPO now uses native TRL implementation with advanced features:
    # - vLLM acceleration support
    # - Multiple loss types (DAPO, GRPO, Dr. GRPO, BNPO)
    # - Flexible reward scaling strategies
    # - VLM (Vision-Language Model) support
    metrics = train_grpo(config)

    print("\nGRPO training complete!")
    print(f"Final metrics: {metrics}")


if __name__ == "__main__":
    main()
