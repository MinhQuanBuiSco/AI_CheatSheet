"""Example: Train a model using PPO (Proximal Policy Optimization)."""

from llm_rl.config import PPOConfig
from llm_rl.trainers import PPOTrainer


def main():
    """Train PPO model from config."""

    # Load config from YAML
    config = PPOConfig.from_yaml("configs/training/ppo/base.yaml")

    # NOTE: PPO requires a trained reward model
    # Make sure to train a reward model first using train_reward_model.py
    # and update the reward_model_name_or_path in the config

    # Train
    with PPOTrainer(config) as trainer:
        trainer.setup()
        metrics = trainer.train()

    print("\nTraining complete!")
    print(f"Final metrics: {metrics}")


if __name__ == "__main__":
    main()
