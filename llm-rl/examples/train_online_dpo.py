"""Example: Train a model using Online DPO."""

from llm_rl.config import OnlineDPOConfig
from llm_rl.trainers import train_online_dpo


def main():
    """Train Online DPO model from config."""

    # Load config from YAML
    config = OnlineDPOConfig.from_yaml("configs/training/online_dpo/base.yaml")

    # Train with iterative improvement using simplified API
    # Online DPO will try to use native TRL implementation if available,
    # otherwise falls back to custom implementation
    results = train_online_dpo(config)

    print("\nOnline DPO training complete!")
    print(f"Trained for {config.num_iterations} iterations")
    print(f"Results: {results}")


if __name__ == "__main__":
    main()
