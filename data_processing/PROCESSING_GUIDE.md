# Data Processing Guide

Complete guide for processing data with the API and checking results.

## Quick Start

### 1. Check Available Data

```bash
# List available demo data
ls -lh demo_data/

# Output:
# customers_small.parquet   (358K - 10K records)
# customers_medium.parquet  (3.3M - 100K records)
# customers_large.parquet   (32M - 1M records)
# usage_logs_small.parquet  (241K)
# usage_logs_medium.parquet (2.1M)
# usage_logs_large.parquet  (21M)
```

### 2. Submit Processing Job

```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/customers_small.parquet",
    "output_path": "/app/output/processed",
    "file_type": "parquet",
    "enable_pii": true,
    "num_workers": 1,
    "chunk_size": 10000
  }'
```

**Response:**
```json
{
  "job_id": "1f40a492-0053-48ff-884c-84daa50ec779",
  "status": "accepted",
  "message": "Processing job ... started on worker 437e23f27363"
}
```

### 3. Monitor Processing

```bash
# Watch logs in real-time
docker-compose logs -f api

# Or check specific job
docker-compose logs api | grep "1f40a492"

# Output shows:
# [worker_id] Job abc-123 assigned to worker abc-123
# [worker_id] Job abc-123 - Starting processing
# [worker_id] Job abc-123 - Input: /app/data/customers_small.parquet
# [worker_id] Job abc-123 completed: 10000 records processed
```

### 4. Check Output

```bash
# List output files
ls -lh demo_output/processed/

# View in Python
python3 << EOF
import polars as pl
df = pl.read_parquet("demo_output/processed/customers_small_000000.parquet")
print(df.head())
print(f"Shape: {df.shape}")
EOF
```

## Request Parameters

### Required Parameters

- **input_path**: Full path to input file (must be in `/app/data/`)
- **output_path**: Output directory (will be created in `/app/output/`)

### Optional Parameters

- **file_type**: Output format (`"parquet"`, `"csv"`, `"json"`)
  - Default: `"parquet"`

- **enable_pii**: Enable PII detection and anonymization
  - Default: `false`
  - When `true`: Emails, phones, SSNs are hashed

- **num_workers**: Number of parallel workers
  - Default: `10`
  - Use `1` for Docker (horizontal scaling instead)

- **chunk_size**: Records per chunk
  - Default: `10000`
  - Smaller = more frequent progress updates

## Examples

### Example 1: Simple Processing (No PII)

```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/usage_logs_small.parquet",
    "output_path": "/app/output/logs_processed",
    "file_type": "parquet",
    "enable_pii": false
  }'
```

### Example 2: PII Anonymization

```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/customers_medium.parquet",
    "output_path": "/app/output/customers_anonymized",
    "file_type": "parquet",
    "enable_pii": true
  }'
```

**Before (Original):**
```
email: "john.doe@example.com"
phone: "(555) 123-4567"
```

**After (Anonymized):**
```
email: "bf17357ee48179a7"  # SHA256 hash
phone: "dbd76ced251f533c"   # SHA256 hash
```

### Example 3: Convert to CSV

```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/customers_small.parquet",
    "output_path": "/app/output/customers_csv",
    "file_type": "csv",
    "enable_pii": false
  }'
```

### Example 4: Large Dataset

```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/customers_large.parquet",
    "output_path": "/app/output/large_processed",
    "file_type": "parquet",
    "enable_pii": true,
    "chunk_size": 50000
  }'

# This processes 1M records
# Takes ~10-20 seconds depending on hardware
```

## Verifying Output

### Check Processing Results

```python
import polars as pl

# Read original
original = pl.read_parquet("demo_data/customers_small.parquet")
print(f"Original: {original.shape}")
print(original.head(3))

# Read processed
processed = pl.read_parquet("demo_output/processed/customers_small_000000.parquet")
print(f"Processed: {processed.shape}")
print(processed.head(3))

# Compare PII fields
print("\nOriginal email:", original["email"][0])
print("Processed email:", processed["email"][0])
```

### Quality Check API

```bash
# Run quality check on processed data
curl -X POST http://localhost:8000/quality-check \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/app/data/customers_small.parquet"
  }'
```

**Response:**
```json
{
  "total_records": 10000,
  "total_columns": 10,
  "quality_score": 95.5,
  "issues_count": 2,
  "issues": [
    "Column 'phone' has 2.5% null values",
    "Found 10 duplicate rows (0.1% of data)"
  ]
}
```

## Batch Processing

Process multiple files:

```bash
#!/bin/bash
# process_all.sh

FILES=("customers_small" "customers_medium" "usage_logs_small")

for file in "${FILES[@]}"; do
  echo "Processing $file..."

  curl -X POST http://localhost:8000/process \
    -H "Content-Type: application/json" \
    -d '{
      "input_path": "/app/data/'$file'.parquet",
      "output_path": "/app/output/'$file'_processed",
      "file_type": "parquet",
      "enable_pii": true
    }'

  echo ""
  sleep 2
done

echo "All jobs submitted!"
```

Run it:
```bash
chmod +x process_all.sh
./process_all.sh
```

## Monitoring Processing

### Watch Real-Time Logs

```bash
# Follow all API logs
docker-compose logs -f api

# Filter for specific job
docker-compose logs -f api | grep "job-id-here"

# Watch all completed jobs
docker-compose logs -f api | grep "completed"
```

### Check Grafana Dashboard

1. Open http://localhost:3000
2. Go to "Data Processing Metrics" dashboard
3. Watch:
   - Request rate increase during processing
   - Response times
   - Total requests counter

### Prometheus Queries

```bash
# Total processing requests
curl -s 'http://localhost:9090/api/v1/query?query=api_requests_total{endpoint="/process"}' | python3 -m json.tool

# Processing rate
curl -s 'http://localhost:9090/api/v1/query?query=rate(api_requests_total{endpoint="/process"}[5m])' | python3 -m json.tool
```

## Advanced: Horizontal Scaling

Process large workloads by scaling API workers:

```bash
# Scale to 3 API workers
docker-compose up -d --scale api=3

# Submit multiple jobs in parallel
for i in {1..10}; do
  curl -X POST http://localhost:8000/process \
    -H "Content-Type: application/json" \
    -d '{
      "input_path": "/app/data/customers_medium.parquet",
      "output_path": "/app/output/batch_'$i'",
      "file_type": "parquet",
      "enable_pii": true
    }' &
done
wait

# Jobs are automatically distributed across 3 workers
# Check which worker handled each job:
docker-compose logs api | grep "assigned to worker"
```

## Output File Locations

All output is written to `demo_output/`:

```
demo_output/
├── processed/
│   └── customers_small_000000.parquet
├── customers_anonymized/
│   └── customers_medium_000000.parquet
└── large_processed/
    └── customers_large_000000.parquet
```

**File naming:**
- Input: `customers_small.parquet`
- Output: `customers_small_000000.parquet` (with chunk number)
- Multiple chunks: `_000000`, `_000001`, `_000002`, etc.

## Reading Processed Data

### Using Polars (Recommended)

```python
import polars as pl

# Single file
df = pl.read_parquet("demo_output/processed/customers_small_000000.parquet")

# All files in directory (auto-merge chunks)
df = pl.read_parquet("demo_output/processed/*.parquet")

print(df.head())
print(f"Total records: {len(df)}")
print(f"Columns: {df.columns}")
```

### Using Pandas

```python
import pandas as pd

df = pd.read_parquet("demo_output/processed/customers_small_000000.parquet")
print(df.head())
```

### Using PyArrow

```python
import pyarrow.parquet as pq

table = pq.read_table("demo_output/processed/customers_small_000000.parquet")
df = table.to_pandas()
print(df.head())
```

## Performance Tips

### 1. Chunk Size

- **Small files (<10MB)**: `chunk_size: 10000`
- **Medium files (10-100MB)**: `chunk_size: 50000`
- **Large files (>100MB)**: `chunk_size: 100000`

### 2. PII Processing

- PII anonymization adds ~20-30% overhead
- Only enable if needed: `enable_pii: false` for non-sensitive data

### 3. File Format

**Parquet** (recommended):
- Fastest read/write
- Smallest file size
- Preserves data types

**CSV**:
- Human-readable
- Larger files
- Slower processing

**JSON**:
- Good for nested data
- Largest files
- Slowest

### 4. Horizontal Scaling

```bash
# For high throughput, scale workers:
docker-compose up -d --scale api=5

# Each worker processes jobs independently
# Nginx load balancer distributes requests
```

## Troubleshooting

### Job Stuck/Not Completing

```bash
# Check logs for errors
docker-compose logs api | grep -E "(error|Error|failed)"

# Check container health
docker-compose ps api

# Restart if needed
docker-compose restart api
```

### Output File Not Found

```bash
# Check if path exists
ls demo_output/

# Check container has access
docker-compose exec api ls /app/output/

# Verify job completed
docker-compose logs api | grep "completed"
```

### PII Not Anonymized

```bash
# Verify enable_pii is true in request
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"enable_pii": true, ...}'

# Check logs for PII processing
docker-compose logs api | grep -i "pii"
```

### Performance Issues

```bash
# Check resource usage
docker stats

# Reduce chunk_size if memory issues
# Increase chunk_size if CPU underutilized

# Scale horizontally for throughput
docker-compose up -d --scale api=3
```

## Complete Example Workflow

```bash
#!/bin/bash
# Complete data processing workflow

echo "=== Data Processing Workflow ==="

# 1. Check input data
echo "1. Checking input data..."
ls -lh demo_data/customers_medium.parquet

# 2. Submit processing job
echo "2. Submitting processing job..."
RESPONSE=$(curl -s -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/customers_medium.parquet",
    "output_path": "/app/output/final_output",
    "file_type": "parquet",
    "enable_pii": true,
    "chunk_size": 10000
  }')

echo "$RESPONSE" | python3 -m json.tool

# Extract job ID
JOB_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
echo "Job ID: $JOB_ID"

# 3. Wait for completion
echo "3. Waiting for job completion..."
sleep 5

# 4. Check logs
echo "4. Checking logs..."
docker-compose logs api | grep "$JOB_ID" | grep "completed"

# 5. Verify output
echo "5. Verifying output..."
ls -lh demo_output/final_output/

# 6. Inspect data
echo "6. Inspecting processed data..."
python3 << EOF
import polars as pl
df = pl.read_parquet("demo_output/final_output/*.parquet")
print(f"✅ Processed {len(df):,} records")
print(f"✅ Columns: {df.columns}")
print(f"✅ File size: {df.estimated_size('mb'):.2f} MB")
print("\nFirst 5 rows:")
print(df.head())
EOF

echo "✅ Processing workflow complete!"
```

## Next Steps

1. ✅ Try processing demo data
2. ✅ Check anonymized output
3. ✅ Monitor in Grafana dashboard
4. ✅ Scale API workers for throughput
5. ✅ Process your own data files
