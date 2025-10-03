# Quick Start Guide

Get up and running with the Anthropic-level data processing infrastructure in 5 minutes.

## Prerequisites

- Mac Mini M4 (or any Mac with Apple Silicon)
- Python 3.12+
- 24GB RAM (recommended)

## Installation

```bash
# 1. Navigate to project directory
cd data_processing

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -e .
```

## Run the Demo (Fastest Way to See Everything)

```bash
# 1. Generate synthetic data
python examples/generate_synthetic_data.py

# 2. Run complete demonstration
python examples/demo_pipeline.py
```

This will:
- ✅ Generate 1M synthetic customer records with PII
- ✅ Run data quality checks
- ✅ Detect and anonymize PII (emails, phones, etc.)
- ✅ Process data using multiprocessing (optimized for M4)
- ✅ Cluster data using embeddings
- ✅ Display comprehensive metrics and stats

**Expected output:**
```
====================================================================================
ANTHROPIC-LEVEL DATA PROCESSING DEMONSTRATION
====================================================================================

📊 Loading data...
  Records: 1,000,000
  Columns: 10
  Size: 95.2 MB

1️⃣  DATA QUALITY CHECK
--------------------------------------------------------------------------------
Quality Score: 87.5/100
...

2️⃣  PRIVACY & ANONYMIZATION
--------------------------------------------------------------------------------
Detecting PII in text columns...
  PII Instances Found: 3,521,442
  Anonymization Time: 12.34s
  Throughput: 81,031 records/sec
...

✅ DEMONSTRATION COMPLETE
```

## CLI Usage

### System Information

```bash
python -m data_processing info
```

### Process Data

```bash
# Basic processing
python -m data_processing process demo_data/customers_large.parquet output/

# With PII detection
python -m data_processing process demo_data/customers_large.parquet output/ --enable-pii

# With clustering
python -m data_processing process demo_data/customers_large.parquet output/ \
    --enable-clustering --text-column message
```

### Quality Check

```bash
python -m data_processing quality-check demo_data/customers_large.parquet
```

### Cluster Data

```bash
python -m data_processing cluster \
    demo_data/customers_large.parquet \
    message \
    --num-clusters 5 \
    --output clustered.parquet
```

### Anonymize PII

```bash
python -m data_processing anonymize \
    demo_data/customers_large.parquet \
    --text-column message \
    --method hash \
    --output anonymized.parquet
```

## Python API

### Basic Example

```python
from data_processing.core import Pipeline, ProcessorConfig
from data_processing.privacy import Anonymizer, AnonymizationConfig
from data_processing.analytics import DataQualityChecker
import polars as pl

# 1. Check data quality
checker = DataQualityChecker()
df = pl.read_parquet("data.parquet")
report = checker.check(df)
print(f"Quality: {report.quality_score}/100")

# 2. Anonymize PII
config = AnonymizationConfig()
anonymizer = Anonymizer(config)
anon_df, stats = anonymizer.anonymize_dataframe(df)
print(f"Anonymized {sum(stats.values())} PII instances")

# 3. Process through pipeline
pipeline_config = ProcessorConfig(num_workers=10)
pipeline = Pipeline(pipeline_config)
stats = pipeline.process_file("input.parquet", "output/")
print(f"Processed {stats.processed_records:,} records")
```

## Processing Your Own Data

### Parquet Files

```bash
python -m data_processing process your_data.parquet output/ --enable-pii
```

### CSV Files

```bash
python -m data_processing process your_data.csv output/ --format csv --enable-pii
```

### JSON Files

```bash
python -m data_processing process your_data.json output/ --format json --enable-pii
```

## Performance Tips

### For 20GB+ Datasets

```bash
# Use larger chunk sizes and all available workers
python -m data_processing process large_data.parquet output/ \
    --workers 10 \
    --chunk-size 50000 \
    --enable-pii
```

### For Memory-Constrained Systems

```bash
# Use smaller chunks
python -m data_processing process data.parquet output/ \
    --workers 4 \
    --chunk-size 5000
```

### For Maximum Speed

```bash
# Disable PII detection and use all cores
python -m data_processing process data.parquet output/ \
    --workers 12 \
    --chunk-size 100000
```

## Troubleshooting

### Out of Memory

- Reduce `--chunk-size`
- Reduce `--workers`
- Close other applications

### Slow Processing

- Increase `--workers` (up to 10 on M4)
- Increase `--chunk-size`
- Disable clustering if not needed

### Import Errors

```bash
# Reinstall dependencies
pip install -e . --force-reinstall
```

### Sentence Transformers Download

The first run will download embedding models (~90MB). This is normal and only happens once.

## Next Steps

1. Read the [full documentation](README.md)
2. Explore the [example scripts](examples/)
3. Customize the pipeline for your use case
4. Check out the [API reference](src/data_processing/)

## Support

For issues or questions:
1. Check the main [README.md](README.md)
2. Review example code in [examples/](examples/)
3. Inspect module docstrings in the source code

---

**Ready to process at scale! 🚀**
