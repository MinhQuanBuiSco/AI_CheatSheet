"""Example: Train a model using DPO (Direct Preference Optimization)."""

from llm_rl.config import DPOConfig
from llm_rl.trainers import train_dpo


def main():
    """Train DPO model from config."""

    # Option 1: Load from YAML
    config = DPOConfig.from_yaml("configs/training/dpo/base.yaml")

    # Option 2: Create config programmatically
    # from llm_rl.config import ModelConfig, PeftConfig, DatasetConfig, TrainingConfig
    #
    # config = DPOConfig(
    #     method="dpo",
    #     model=ModelConfig(
    #         model_name_or_path="gpt2",
    #         use_peft=True,
    #     ),
    #     peft=PeftConfig(
    #         r=16,
    #         lora_alpha=32,
    #     ),
    #     dataset=DatasetConfig(
    #         dataset_name="ultrafeedback-binarized",
    #         max_train_samples=1000,
    #     ),
    #     training=TrainingConfig(
    #         output_dir="./outputs/dpo_example",
    #         num_train_epochs=1,
    #     ),
    #     beta=0.1,
    # )

    # Train using simplified API
    metrics = train_dpo(config)

    print("\nTraining complete!")
    print(f"Final metrics: {metrics}")


if __name__ == "__main__":
    main()
