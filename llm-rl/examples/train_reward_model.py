"""Example: Train a reward model from preference data."""

from llm_rl.config import ModelConfig, TrainingConfig, PeftConfig, DatasetConfig
from llm_rl.models import RewardModelTrainer
from llm_rl.data import DatasetLoader


def main():
    """Train a reward model."""

    # Configure model
    model_config = ModelConfig(
        model_name_or_path="gpt2",
        use_peft=True,
        torch_dtype="bfloat16",
    )

    # Configure PEFT
    peft_config = PeftConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
    )

    # Configure training
    training_config = TrainingConfig(
        output_dir="./outputs/reward_model",
        num_train_epochs=1,
        per_device_train_batch_size=4,
        learning_rate=5e-5,
        save_steps=500,
    )

    # Configure dataset
    dataset_config = DatasetConfig(
        dataset_name="ultrafeedback-binarized",
        max_train_samples=5000,
        max_eval_samples=500,
    )

    # Load dataset
    print("Loading dataset...")
    dataset_loader = DatasetLoader(dataset_config)
    dataset_loader.load()
    train_dataset, eval_dataset = dataset_loader.get_splits()

    # Train reward model
    print("\nTraining reward model...")
    trainer = RewardModelTrainer(
        model_config=model_config,
        training_config=training_config,
        peft_config=peft_config,
    )

    metrics = trainer.train(train_dataset, eval_dataset)

    print("\nReward model training complete!")
    print(f"Model saved to: {training_config.output_dir}")
    print(f"Metrics: {metrics}")


if __name__ == "__main__":
    main()
