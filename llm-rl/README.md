# LLM-RL: Production-Ready LLM Fine-Tuning with Reinforcement Learning

A comprehensive, production-ready platform for fine-tuning Large Language Models using various Reinforcement Learning approaches including **DPO**, **PPO**, **Online DPO**, and **GRPO**.

## Features

- **Multiple RL Methods**: DPO, PPO, Online DPO, GRPO
- **Production-Ready**: Built with best practices, error handling, and scalability
- **Distributed Training**: DeepSpeed and FSDP support for multi-GPU training
- **Memory Efficient**: Support for LoRA, QLoRA (4-bit/8-bit quantization)
- **Auto-Download Datasets**: Pre-configured popular datasets with automatic downloading
- **Experiment Tracking**: Weights & Biases and TensorBoard integration
- **CLI and Python API**: Use via command-line or as a library
- **Flexible Configuration**: YAML-based configs with Pydantic validation

## Supported RL Methods

### 1. DPO (Direct Preference Optimization)
- Most stable and easiest to implement
- No reward model required
- Directly optimizes from preference data
- Best for: Getting started, stable training

### 2. PPO (Proximal Policy Optimization)
- Classic RL approach with actor-critic
- Requires a trained reward model
- Online learning with rollouts
- Best for: Maximum control, research

### 3. Online DPO
- DPO with iterative online data generation
- Self-improving through active learning
- Optional reward model for ranking
- Best for: Iterative improvement, data efficiency

### 4. GRPO (Group Relative Policy Optimization)
- Multiple completions per prompt
- Group-wise preference optimization
- More sample-efficient than pairwise
- Best for: Efficiency, batch preference learning

## Installation

### Using UV (Recommended)

```bash
# Clone the repository
git clone <your-repo-url>
cd llm-rl

# Install with UV
uv sync

# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows
```

### Using pip

```bash
pip install -e .
```

## Quick Start

### 1. Download Datasets

```bash
# List available datasets
llm-rl list-datasets

# Download a dataset
llm-rl download-dataset ultrafeedback-binarized --output ./data
```

### 2. Train with DPO (Easiest Start)

```bash
# Using CLI
llm-rl train --config configs/training/dpo/base.yaml

# Or using Python
python examples/train_dpo.py
```

### 3. Train a Reward Model (for PPO/GRPO)

```bash
# Train reward model first
python examples/train_reward_model.py

# Then train with PPO
python examples/train_ppo.py
```

## Usage

### Command-Line Interface

```bash
# Train with specific method
llm-rl train --config configs/training/dpo/base.yaml

# Train reward model
llm-rl train-reward --config configs/reward_model.yaml

# Download dataset
llm-rl download-dataset anthropic-hh-rlhf --output ./data

# List available datasets
llm-rl list-datasets

# Evaluate model (coming soon)
llm-rl evaluate --checkpoint ./outputs/model --config configs/eval.yaml

# Compare models (coming soon)
llm-rl compare --checkpoints model1,model2,model3
```

### Python API

```python
from llm_rl.config import DPOConfig
from llm_rl.trainers import DPOTrainer

# Load config from YAML
config = DPOConfig.from_yaml("configs/training/dpo/base.yaml")

# Or create programmatically
from llm_rl.config import ModelConfig, PeftConfig, DatasetConfig, TrainingConfig

config = DPOConfig(
    method="dpo",
    model=ModelConfig(
        model_name_or_path="gpt2",
        use_peft=True,
    ),
    peft=PeftConfig(r=16, lora_alpha=32),
    dataset=DatasetConfig(
        dataset_name="ultrafeedback-binarized",
        max_train_samples=1000,
    ),
    training=TrainingConfig(
        output_dir="./outputs/dpo_gpt2",
        num_train_epochs=1,
    ),
    beta=0.1,
)

# Train
with DPOTrainer(config) as trainer:
    trainer.setup()
    metrics = trainer.train()
```

## Configuration

All methods use YAML configuration files. Example structure:

```yaml
method: "dpo"

model:
  model_name_or_path: "gpt2"
  use_peft: true
  load_in_4bit: false

peft:
  r: 16
  lora_alpha: 32
  lora_dropout: 0.05

dataset:
  dataset_name: "ultrafeedback-binarized"
  max_train_samples: 10000

training:
  output_dir: "./outputs/dpo_gpt2"
  num_train_epochs: 1
  per_device_train_batch_size: 4
  learning_rate: 5.0e-5

# Method-specific parameters
beta: 0.1
```

See `configs/` directory for complete examples.

## Supported Models

### Small Models (Single GPU)
- GPT-2 (124M - 1.5B parameters)
- TinyLlama (1.1B)
- DistilGPT-2

### Medium Models (With LoRA/QLoRA)
- LLaMA-2 (7B, 13B)
- Mistral (7B)
- Vicuna (7B, 13B)

## Available Datasets

| Dataset | Type | Size | Description |
|---------|------|------|-------------|
| ultrafeedback-binarized | Preference | ~64k | Binarized UltraFeedback for DPO |
| anthropic-hh-rlhf | Preference | ~160k | Anthropic's Helpful & Harmless |
| stack-exchange-preferences | Preference | ~10M | Stack Exchange Q&A pairs |
| summarize-from-feedback | Preference | ~90k | OpenAI summarization feedback |

## Project Structure

```
llm-rl/
├── src/llm_rl/
│   ├── config/          # Configuration classes
│   ├── trainers/        # RL trainers (DPO, PPO, etc.)
│   ├── models/          # Model utilities, reward models
│   ├── data/            # Dataset loaders, preprocessors
│   ├── utils/           # Utilities
│   └── cli.py           # Command-line interface
├── configs/
│   ├── models/          # Model configurations
│   └── training/        # Training configurations
│       ├── dpo/
│       ├── ppo/
│       ├── online_dpo/
│       └── grpo/
├── examples/            # Example scripts
├── tests/              # Unit tests
└── README.md
```

## Advanced Features

### Distributed Training

```yaml
# DeepSpeed ZeRO-3
training:
  deepspeed: "configs/deepspeed/zero3.json"
```

### Experiment Tracking

```yaml
logging:
  wandb_project: "my-llm-project"
  wandb_entity: "my-team"
  report_to: ["wandb", "tensorboard"]
```

### Memory Optimization

```yaml
model:
  load_in_4bit: true  # QLoRA

training:
  gradient_checkpointing: true
  gradient_accumulation_steps: 8
```

## Examples

See the `examples/` directory for complete examples:

- `train_dpo.py` - Direct Preference Optimization
- `train_ppo.py` - Proximal Policy Optimization
- `train_online_dpo.py` - Online DPO with iterative learning
- `train_grpo.py` - Group Relative Policy Optimization
- `train_reward_model.py` - Train reward model for PPO/GRPO
- `download_datasets.py` - Download and explore datasets

## Development

### Running Tests

```bash
pytest tests/
```

### Code Quality

```bash
# Format code
black src/

# Type checking
mypy src/

# Linting
ruff check src/
```

## Troubleshooting

### Out of Memory

1. Enable gradient checkpointing: `gradient_checkpointing: true`
2. Use 4-bit quantization: `load_in_4bit: true`
3. Reduce batch size: `per_device_train_batch_size: 2`
4. Increase gradient accumulation: `gradient_accumulation_steps: 8`

### Slow Training

1. Enable bf16: `bf16: true`
2. Use DeepSpeed for multi-GPU
3. Adjust `max_train_samples` for faster iteration

### Dataset Issues

1. Check dataset format matches expected structure
2. Use `llm-rl list-datasets` to see available datasets
3. Manually inspect dataset with HuggingFace datasets library

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Citation

If you use this framework in your research, please cite:

```bibtex
@software{llm_rl,
  title = {LLM-RL: Production-Ready LLM Fine-Tuning with Reinforcement Learning},
  author = {Quan Bui},
  year = {2025},
  url = {https://github.com/yourusername/llm-rl}
}
```

## Acknowledgments

- Built on top of [HuggingFace Transformers](https://github.com/huggingface/transformers)
- Uses [TRL](https://github.com/huggingface/trl) for RL implementations
- Inspired by research from Anthropic, OpenAI, and DeepMind

## Support

- GitHub Issues: Report bugs or request features
- Documentation: Coming soon

---

**Happy Training!**
