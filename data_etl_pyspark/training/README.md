# Production-Grade SFT Training System

Enterprise-level Supervised Fine-Tuning (SFT) implementation optimized for big tech scale deployment with comprehensive monitoring, distributed training, and advanced optimization techniques.

## 🚀 Quick Start

### 1. Installation

```bash
# Install dependencies
pip install -r requirements.txt

# For CUDA support (recommended for GPU training)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Optional: Install additional optimizations
pip install flash-attn triton  # For advanced attention optimizations
```

### 2. Basic Training

```bash
# Train with your processed dataset
python sft_trainer.py \
    --model-name "microsoft/DialoGPT-small" \
    --dataset-path "../processed_data/processed_dataset.parquet" \
    --output-dir "./outputs/my-model" \
    --epochs 3 \
    --batch-size 4 \
    --learning-rate 5e-5

# Train with configuration file
python sft_trainer.py --config config/sft_config.yaml
```

### 3. Hyperparameter Optimization

```bash
# Run automated hyperparameter search
python config/hyperparameter_optimization.py \
    --base-config config/sft_config.yaml \
    --n-trials 50 \
    --output-dir ./hpo_results

# With distributed optimization using Ray Tune
python config/hyperparameter_optimization.py \
    --base-config config/sft_config.yaml \
    --use-ray \
    --n-trials 100
```

### 4. Model Evaluation

```bash
# Comprehensive evaluation
python utils/evaluation.py \
    --model-path "./outputs/my-model" \
    --test-data "../processed_data/processed_dataset.parquet" \
    --output-dir "./evaluation_results"
```

### 5. Model Deployment

```bash
# Deploy for production serving
python utils/deployment.py \
    --model-path "./outputs/my-model" \
    --host 0.0.0.0 \
    --port 8000 \
    --optimize \
    --batch-size 8
```

## 📁 Directory Structure

```
training/
├── sft_trainer.py                 # Main training script
├── config/
│   ├── sft_config.yaml           # Training configuration
│   └── hyperparameter_optimization.py  # HPO system
├── utils/
│   ├── evaluation.py             # Comprehensive evaluation
│   └── deployment.py             # Production deployment
├── requirements.txt              # Dependencies
├── README.md                     # This file
└── outputs/                      # Training outputs (auto-created)
```

## ⚙️ Configuration

### Training Configuration (`config/sft_config.yaml`)

```yaml
# Model settings
model:
  name: "microsoft/DialoGPT-small"
  revision: "main"

# Training hyperparameters
training:
  num_train_epochs: 3
  per_device_train_batch_size: 4
  learning_rate: 5e-5
  weight_decay: 0.01
  warmup_ratio: 0.03

# LoRA (Parameter-Efficient Fine-tuning)
lora:
  enabled: true
  r: 16
  alpha: 32
  dropout: 0.1

# Monitoring
monitoring:
  use_wandb: true
  wandb_project: "llm-sft-training"
```

## 🔧 Advanced Features

### 1. Parameter-Efficient Fine-Tuning with LoRA

```python
# Automatic LoRA configuration for different model sizes
config = SFTConfig(
    model_name="microsoft/DialoGPT-medium",
    use_lora=True,
    lora_r=16,           # Rank (higher = more parameters)
    lora_alpha=32,       # Scaling (typically 2x rank)
    lora_dropout=0.1     # Dropout for regularization
)
```

### 2. Distributed Training

```bash
# Multi-GPU training with accelerate
accelerate config  # Run once to configure
accelerate launch sft_trainer.py --config config/sft_config.yaml

# Or with torchrun
torchrun --nproc_per_node=4 sft_trainer.py --config config/sft_config.yaml
```

### 3. Memory Optimization

```yaml
# In config/sft_config.yaml
training:
  fp16: true                    # Half precision
  gradient_checkpointing: true  # Trade compute for memory
  per_device_train_batch_size: 1  # Reduce batch size
  gradient_accumulation_steps: 16  # Maintain effective batch size
```

### 4. Advanced Monitoring

- **Weights & Biases**: Automatic experiment tracking
- **TensorBoard**: Local monitoring dashboard
- **Prometheus**: Production metrics
- **Resource Monitoring**: GPU/CPU/Memory usage

### 5. Model Optimization for Production

```python
# Automatic inference optimizations
config = DeploymentConfig(
    model_path="./outputs/my-model",
    optimize_for_inference=True,
    use_better_transformer=True,
    enable_dynamic_batching=True,
    max_batch_size=32
)
```

## 📊 Evaluation Metrics

The evaluation system computes comprehensive metrics:

### Language Generation Quality
- **Perplexity**: Model uncertainty measure
- **BLEU Scores**: N-gram overlap with references
- **ROUGE Scores**: Recall-oriented overlap
- **BERTScore**: Semantic similarity

### Text Diversity
- **Distinct-1/2**: Unique unigram/bigram ratios
- **Self-BLEU**: Diversity within generated texts
- **Vocabulary Size**: Unique token count

### Production Metrics
- **Generation Speed**: Tokens per second
- **Memory Usage**: Peak memory consumption
- **Latency**: Response time distribution

## 🔄 Production Deployment

### API Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Single generation
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello, how are you?", "max_length": 100}'

# Batch generation
curl -X POST http://localhost:8000/batch_generate \
  -H "Content-Type: application/json" \
  -d '{"prompts": ["Hello!", "How are you?"], "temperature": 0.7}'

# Metrics
curl http://localhost:8000/metrics
```

### Monitoring Dashboard

- **Prometheus**: `http://localhost:8001` (metrics)
- **API Docs**: `http://localhost:8000/docs` (Swagger UI)
- **Health**: `http://localhost:8000/health`

## 🚀 Performance Optimizations

### Model-Specific Recommendations

| Model Size | Batch Size | LoRA Rank | Memory | Precision |
|------------|------------|-----------|---------|-----------|
| < 1B       | 8-16       | 8-16      | 8GB     | FP16      |
| 1B-7B      | 4-8        | 16-32     | 16GB    | FP16      |
| > 7B       | 1-4        | 32-64     | 32GB+   | BF16      |

### Hardware Optimization

```bash
# For V100/A100 GPUs
export CUDA_LAUNCH_BLOCKING=0
export TORCH_CUDA_ARCH_LIST="7.0;8.0"

# For CPU optimization
export OMP_NUM_THREADS=8
export MKL_NUM_THREADS=8
```

## 🐛 Troubleshooting

### Common Issues

1. **CUDA Out of Memory**
   ```yaml
   # Reduce batch size and enable gradient checkpointing
   training:
     per_device_train_batch_size: 1
     gradient_accumulation_steps: 16
     gradient_checkpointing: true
   ```

2. **Slow Training**
   ```yaml
   # Enable optimizations
   training:
     fp16: true
     dataloader_num_workers: 4
   lora:
     enabled: true  # Reduce trainable parameters
   ```

3. **Evaluation Issues**
   ```python
   # Reduce evaluation data size
   config = EvaluationConfig(
       max_samples=500,  # Limit samples
       batch_size=4      # Reduce batch size
   )
   ```

## 📈 Scaling Guidelines

### Development → Production

1. **Development Setup**
   - Small model (DialoGPT-small)
   - Limited data (1K samples)
   - Single GPU/CPU
   - Basic monitoring

2. **Staging Environment**
   - Medium model (DialoGPT-medium)
   - Representative data (10K samples)
   - Multi-GPU training
   - Full monitoring stack

3. **Production Deployment**
   - Large model (GPT-3.5 scale)
   - Full dataset (100K+ samples)
   - Distributed training
   - Enterprise monitoring

## 🤝 Contributing

1. Follow the existing code structure
2. Add comprehensive logging
3. Include error handling
4. Update configuration documentation
5. Add tests for new features

## 📄 License

Enterprise deployment ready - adapt for your organization's needs.

---

**Built for Big Tech Scale** 🏗️ | **Production Ready** ⚡ | **Fully Monitored** 📊