"""Example: Download datasets for training."""

from llm_rl.data import DatasetLoader, download_dataset


def main():
    """Download and explore available datasets."""

    # List available datasets
    print("Available datasets in catalog:")
    DatasetLoader.print_dataset_catalog()

    # Download specific datasets
    print("\n" + "="*60)
    print("Downloading datasets...")
    print("="*60 + "\n")

    # Download UltraFeedback (binarized for DPO)
    download_dataset(
        dataset_name="ultrafeedback-binarized",
        output_dir="./data",
    )

    # Download Anthropic HH-RLHF
    download_dataset(
        dataset_name="anthropic-hh-rlhf",
        output_dir="./data",
    )

    print("\n✓ All datasets downloaded successfully!")


if __name__ == "__main__":
    main()
