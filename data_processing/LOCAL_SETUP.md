# Local Setup & Usage Guide

Quick start guide for running the data processing infrastructure on your Mac M4 locally.

## Step 1: Install Dependencies

```bash
# Make sure you have uv installed
# If not: curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies (this takes 2-3 minutes)
make install-all
```

This installs:
- Core dependencies (polars, pyarrow, click, etc.)
- Optional: PySpark, FastAPI, Great Expectations, Kafka
- Dev tools: pytest, ruff, black, mypy

## Step 2: Generate Demo Data

```bash
# Generate synthetic data (10K, 100K, 1M records)
make generate-data
```

This creates:
```
demo_data/
├── customers_small.parquet   (~1 MB, 10K records)
├── customers_medium.parquet  (~10 MB, 100K records)
├── customers_large.parquet   (~100 MB, 1M records)
├── usage_logs_small.parquet
├── usage_logs_medium.parquet
└── usage_logs_large.parquet
```

## Step 3: Run Complete Demo

```bash
# Run the full demonstration
make demo
```

**What this does:**
1. ✅ Data quality check (scoring, null detection, duplicates)
2. ✅ PII detection and anonymization (emails, phones, SSN, etc.)
3. ✅ High-performance multiprocessing (10 workers on M4)
4. ✅ Data clustering using embeddings
5. ✅ Monitoring and metrics
6. ✅ Audit logging

**Expected output:**
```
================================================================================
ANTHROPIC-LEVEL DATA PROCESSING DEMONSTRATION
================================================================================

📊 Loading data...
  Records: 1,000,000
  Columns: 10
  Size: 95.2 MB

1️⃣  DATA QUALITY CHECK
--------------------------------------------------------------------------------
Quality Score: 87.5/100
Null Values: 50,000
Duplicate Rows: 20,000
Issues Found: 5

2️⃣  PRIVACY & ANONYMIZATION
--------------------------------------------------------------------------------
Detecting PII in text columns...
  PII Instances Found: 3,521,442
  Anonymization Time: 12.34s
  Throughput: 81,031 records/sec
    - email: 1,000,000
    - phone: 950,000
    - message: 1,571,442

3️⃣  HIGH-PERFORMANCE PROCESSING
--------------------------------------------------------------------------------
Optimal Workers (Mac M4): 10
Processing data...
  Records Processed: 1,000,000
  Processing Time: 28.50s
  Throughput: 35,088 records/sec
  Peak Memory: 2,100.5 MB
  CPU Usage: 85.3%

4️⃣  DATA CLUSTERING & ANALYTICS
--------------------------------------------------------------------------------
Generating embeddings and clustering messages...
  Clustering Time: 8.45s

Clusters Created: 5
  Cluster 0: 250 (25.0%)
  Cluster 1: 210 (21.0%)
  ...

✅ DEMONSTRATION COMPLETE
```

## Step 4: Try CLI Commands

### 4.1 System Info

```bash
python -m data_processing info
```

Output:
```
System Information

Platform: Darwin 24.6.0
Architecture: arm64
CPU Cores: 12
Total Memory: 24.0 GB
Available Memory: 16.5 GB

✓ Running on Apple Silicon (optimizations enabled)
```

### 4.2 Quality Check

```bash
python -m data_processing quality-check demo_data/customers_large.parquet
```

Output:
```
Quality Check: customers_large.parquet

Records: 1,000,000
Columns: 10
Quality Score: 87.5/100

✓ Good data quality

Issues Found (5):
  • Column 'phone' has 5.0% null values (threshold: 50%)
  • Column 'message' has 150 outliers (0.0%)
  ...
```

### 4.3 Process Data with PII Anonymization

```bash
python -m data_processing process \
    demo_data/customers_large.parquet \
    output/ \
    --format parquet \
    --workers 10 \
    --chunk-size 10000 \
    --enable-pii
```

Output:
```
Processing customers_large.parquet
  Format: parquet
  Workers: 10
  Chunk size: 10,000

Enabling PII detection and anonymization
[====================] 100% Complete

✓ Processing Complete

Processing Summary:
  Records Processed: 1,000,000
  Records Failed: 0
  Bytes Processed: 95,234,567 (90.82 MB)
  Processing Time: 28.50s
  Throughput: 35,088.00 records/sec
  Peak Memory: 2,100.50 MB
  CPU Usage: 85.3%
  Errors: 0
```

### 4.4 Cluster Data

```bash
python -m data_processing cluster \
    demo_data/customers_small.parquet \
    message \
    --num-clusters 5 \
    --output clustered.parquet
```

Output:
```
Clustering customers_small.parquet
  Text column: message
  Clusters: 5

Generating embeddings...
[====================] 100% 10000/10000

✓ Saved to clustered.parquet

Cluster Summaries:
  Cluster 0: 2,500 records (25.0%)
    Samples:
      - I'm having trouble with login. My account number is 1234567890...
      - Can you help me with payment processing? I've been trying...
      - I'm very satisfied with the new dashboard! Great job!...
```

### 4.5 Anonymize PII

```bash
python -m data_processing anonymize \
    demo_data/customers_small.parquet \
    --text-column message \
    --method hash \
    --output anonymized.parquet
```

Output:
```
Anonymizing customers_small.parquet
  Method: hash

Detecting and anonymizing PII...

✓ Anonymized 35,214 instances of PII
✓ Saved to anonymized.parquet
```

## Step 5: Python API Usage

Create a script `my_pipeline.py`:

```python
from data_processing.core import Pipeline, ProcessorConfig
from data_processing.privacy import Anonymizer, AnonymizationConfig
from data_processing.analytics import DataQualityChecker
import polars as pl

# 1. Load data
df = pl.read_parquet("demo_data/customers_small.parquet")
print(f"Loaded {len(df):,} records")

# 2. Quality check
checker = DataQualityChecker()
report = checker.check(df)
print(f"Quality Score: {report.quality_score}/100")

# 3. Anonymize PII
config = AnonymizationConfig(anonymization_method="hash")
anonymizer = Anonymizer(config)
anon_df, stats = anonymizer.anonymize_dataframe(df, ["email", "phone", "message"])
print(f"Anonymized {sum(stats.values()):,} PII instances")

# 4. Process through pipeline
pipeline_config = ProcessorConfig(
    chunk_size=1000,
    num_workers=10,
)
pipeline = Pipeline(pipeline_config)

# Add custom processor
def clean_text(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        pl.col("message").str.strip_chars().alias("message")
    )

pipeline.add_processor(clean_text)

# Save anonymized data for processing
anon_df.write_parquet("temp_input.parquet")

# Process
stats = pipeline.process_file(
    "temp_input.parquet",
    "processed_output/",
    file_type="parquet",
    enable_multiprocessing=True,
)

print(f"\nProcessed {stats.processed_records:,} records in {stats.processing_time:.2f}s")
print(f"Throughput: {stats.throughput:,.0f} records/sec")
```

Run it:
```bash
python my_pipeline.py
```

## Step 6: Test the Code

```bash
# Run all tests
make test

# Run tests without coverage (faster)
make test-fast

# Run specific test file
pytest tests/test_pipeline.py -v
```

## Step 7: Format and Lint

```bash
# Format code
make format

# Run linters
make lint

# Run both + tests
make pre-commit
```

## Common Use Cases

### Process Your Own Data

**CSV File:**
```bash
python -m data_processing process \
    /path/to/your/data.csv \
    output/ \
    --format csv \
    --enable-pii
```

**JSON File:**
```bash
python -m data_processing process \
    /path/to/your/data.json \
    output/ \
    --format json \
    --enable-pii
```

### Custom Processing Script

```python
import polars as pl
from data_processing.core import Pipeline, ProcessorConfig

# Your custom data processing
config = ProcessorConfig(
    chunk_size=10_000,
    num_workers=10,
    max_memory_mb=16_000,
)

pipeline = Pipeline(config)

# Add your custom transformations
def remove_duplicates(df: pl.DataFrame) -> pl.DataFrame:
    return df.unique()

def filter_recent(df: pl.DataFrame) -> pl.DataFrame:
    return df.filter(pl.col("timestamp") > "2024-01-01")

def aggregate_by_user(df: pl.DataFrame) -> pl.DataFrame:
    return df.group_by("user_id").agg([
        pl.count("*").alias("count"),
        pl.sum("amount").alias("total_amount"),
    ])

pipeline.add_processor(remove_duplicates)
pipeline.add_processor(filter_recent)
pipeline.add_processor(aggregate_by_user)

# Process
stats = pipeline.process_file(
    "your_data.parquet",
    "output/",
    enable_multiprocessing=True,
)
```

## Performance Tips

### For Small Data (<1GB)
```bash
python -m data_processing process data.parquet output/ \
    --workers 4 \
    --chunk-size 5000
```

### For Medium Data (1-10GB)
```bash
python -m data_processing process data.parquet output/ \
    --workers 10 \
    --chunk-size 10000
```

### For Large Data (10-100GB)
```bash
python -m data_processing process data.parquet output/ \
    --workers 10 \
    --chunk-size 50000
```

### Monitor Memory
```python
from data_processing.utils import MemoryMonitor

monitor = MemoryMonitor(threshold_mb=20000)

# Your processing code here...

stats = monitor.get_memory_stats()
print(f"Peak Memory: {stats['peak_mb']:.2f} MB")
```

## Troubleshooting

### Out of Memory
```bash
# Reduce chunk size and workers
python -m data_processing process data.parquet output/ \
    --workers 4 \
    --chunk-size 1000
```

### Slow Processing
```bash
# Increase workers (up to num_cores - 2)
python -m data_processing process data.parquet output/ \
    --workers 10 \
    --chunk-size 50000
```

### Module Not Found
```bash
# Reinstall dependencies
make install-all
```

## Next Steps

Once you're comfortable with local usage:

1. **Docker**: `make docker-up` - Run full stack locally
2. **API**: `make api-dev` - Start REST API server
3. **Kubernetes**: Deploy to cloud (see PRODUCTION.md)
4. **Distributed**: Use PySpark for unlimited scale

## Quick Reference

```bash
# Setup
make install-all          # Install all dependencies
make generate-data        # Generate demo data
make demo                 # Run full demo

# CLI
python -m data_processing info
python -m data_processing quality-check FILE
python -m data_processing process INPUT OUTPUT
python -m data_processing cluster FILE COLUMN
python -m data_processing anonymize FILE

# Development
make test                 # Run tests
make format              # Format code
make lint                # Run linters
make clean               # Clean artifacts

# Docker (optional)
make docker-up           # Start full stack
make docker-down         # Stop stack
make api-dev             # Run API locally
```

---

**You're all set!** Start with `make install-all` and `make demo` 🚀
