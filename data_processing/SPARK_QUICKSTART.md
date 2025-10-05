# PySpark with Docker - Quick Start Guide

This guide shows you how to use the PySpark distributed processing cluster with Docker.

## Prerequisites

```bash
# 1. Start all services
docker-compose up -d

# 2. Wait for services to be healthy (30-60 seconds)
docker-compose ps
```

## Architecture

```
Your Machine (localhost)
    │
    ├─→ API (port 8000) ─────────┐
    │                             │
    ├─→ Spark Master (port 8080) ◄┴─ Submits jobs
    │        │
    │        ├─→ Spark Worker 1
    │        ├─→ Spark Worker 2
    │        └─→ Spark Worker N
    │
    └─→ Data: demo_data/  → mounted to /app/data in all containers
        Output: demo_output/ → mounted to /app/output in all containers
```

## Quick Test

```bash
# 1. Generate test data (if you haven't already)
python examples/generate_claude_usage_logs.py --conversations 10000

# 2. Submit a Spark job
curl -X POST "http://localhost:8000/spark/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/claude_usage_logs.parquet",
    "output_path": "/app/output/spark_test/",
    "mode": "spark",
    "spark_master": "spark://spark-master:7077"
  }'

# 3. Check the output
ls -lh demo_output/spark_test/
```

**Expected result:**
```
✓ Job accepted
✓ Processing 10,000 records
✓ Throughput: ~2,700 rec/s
✓ Output: demo_output/spark_test/part-*.parquet
```

## Usage Examples

### Example 1: Process with Spark (Distributed)

```bash
curl -X POST "http://localhost:8000/spark/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/claude_usage_logs.parquet",
    "output_path": "/app/output/distributed/",
    "mode": "spark",
    "spark_master": "spark://spark-master:7077"
  }'
```

### Example 2: Process with Polars (Local)

```bash
curl -X POST "http://localhost:8000/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/claude_usage_logs.parquet",
    "output_path": "/app/output/local/",
    "enable_pii": true,
    "num_workers": 10
  }'
```

### Example 3: Auto Mode (Smart Selection)

```bash
curl -X POST "http://localhost:8000/spark/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/claude_usage_logs.parquet",
    "output_path": "/app/output/auto/",
    "mode": "auto"
  }'
```
- Uses **Polars** if file < 1GB
- Uses **Spark** if file > 1GB

### Example 4: Custom Spark Configuration

```bash
curl -X POST "http://localhost:8000/spark/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/large_dataset.parquet",
    "output_path": "/app/output/custom/",
    "mode": "spark",
    "spark_master": "spark://spark-master:7077",
    "executor_memory": "8g",
    "driver_memory": "4g",
    "executor_cores": 4,
    "num_executors": 8
  }'
```

## Monitoring

### 1. Spark Master UI

```bash
# Open in browser
open http://localhost:8080
```

Shows:
- Connected workers
- Running applications
- Completed jobs
- Resource usage

### 2. View Logs

```bash
# API logs (shows job submissions and results)
docker-compose logs -f api | grep "Spark Job"

# Spark master logs
docker-compose logs -f spark-master

# Spark worker logs
docker-compose logs -f spark-worker

# Persistent log files
tail -f logs/spark-master/spark.log
tail -f logs/spark-workers/spark.log
```

### 3. Check Spark Status

```bash
curl http://localhost:8000/spark/status
```

Response:
```json
{
  "available": true,
  "pyspark_version": "3.5.0",
  "master": "spark://spark-master:7077",
  "message": "Spark is available"
}
```

### 4. Check Job Status

```bash
# Get job ID from submit response, then:
curl http://localhost:8000/jobs/{job_id}
```

## Scaling

### Scale Spark Workers

```bash
# Scale to 5 workers
docker-compose up -d --scale spark-worker=5

# Verify
docker-compose ps spark-worker
```

Each worker gets:
- 4 CPU cores
- 4GB memory
- Access to shared data

### Scale API Workers

```bash
# Scale to 3 API instances
docker-compose up -d --scale api=3

# Nginx automatically load balances requests
```

## Adding Your Own Data

### Method 1: Copy Files

```bash
# Put your parquet files in demo_data/
cp /path/to/your_data.parquet demo_data/

# Process it
curl -X POST "http://localhost:8000/spark/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/your_data.parquet",
    "output_path": "/app/output/results/",
    "mode": "spark"
  }'

# Get results from demo_output/results/
```

### Method 2: Mount Custom Directory

Edit `docker-compose.yml`:

```yaml
spark-worker:
  volumes:
    - /your/data/path:/app/custom_data:ro
    - ./demo_output:/app/output
```

Then restart:
```bash
docker-compose up -d spark-worker
```

## Troubleshooting

### Problem: Job fails with "File not found"

**Solution:** Make sure file exists in `demo_data/` on your host machine.

```bash
# Check file exists
ls -lh demo_data/claude_usage_logs.parquet

# File must be accessible to workers
# Both API and Spark workers mount demo_data/ to /app/data/
```

### Problem: Workers not connecting to master

**Solution:** Check worker logs and restart.

```bash
# Check logs
docker-compose logs spark-worker | grep "master"

# Restart workers
docker-compose restart spark-worker
```

### Problem: Out of memory

**Solution:** Increase executor memory in docker-compose.yml.

```yaml
spark-worker:
  environment:
    - SPARK_WORKER_MEMORY=8g  # Increase from 4g
```

Then restart:
```bash
docker-compose up -d spark-worker
```

### Problem: Slow performance

**Causes & Solutions:**

1. **Too much cluster overhead for small files**
   - Use local mode for files < 1GB
   - Use auto mode to automatically choose

2. **Not enough workers**
   ```bash
   docker-compose up -d --scale spark-worker=5
   ```

3. **Insufficient resources**
   - Check Docker Desktop settings
   - Allocate more CPU/Memory

## Performance Guide

### When to Use Spark vs Local

**Use Spark (Distributed) when:**
- Dataset > 1GB
- Need horizontal scaling
- Running in production cluster
- Processing very large datasets (10M+ records)

**Use Local (Polars) when:**
- Dataset < 1GB
- Development/testing
- Fast iteration needed
- Single machine is sufficient

**Use Auto mode when:**
- Unsure about dataset size
- Want automatic optimization
- Convenience over control

### Performance Tips

1. **Right-size executors**
   ```bash
   # For 10GB file on 4-worker cluster:
   "executor_memory": "4g",
   "executor_cores": 2,
   "num_executors": 4
   ```

2. **Use appropriate file format**
   - Parquet: Best for Spark (columnar, compressed)
   - CSV: Slower (row-based, uncompressed)

3. **Partition large files**
   ```python
   # When generating data, partition by date/category
   df.write.partitionBy("date").parquet("output/")
   ```

## API Reference

### POST /spark/process

**Request Body:**
```json
{
  "input_path": "/app/data/file.parquet",
  "output_path": "/app/output/result/",
  "mode": "spark",  // "local", "spark", or "auto"
  "spark_master": "spark://spark-master:7077",
  "file_type": "parquet",  // "parquet", "csv", "json"
  "executor_memory": "4g",
  "driver_memory": "2g",
  "executor_cores": 2,
  "num_executors": 4
}
```

**Response:**
```json
{
  "job_id": "d8967ac1-d01d-40f0-bf5a-031240c94cde",
  "status": "accepted",
  "message": "Spark processing job started (mode: spark)",
  "worker_id": "bc5a46d76731"
}
```

### GET /spark/status

**Response:**
```json
{
  "available": true,
  "pyspark_version": "3.5.0",
  "master": "spark://spark-master:7077",
  "message": "Spark is available"
}
```

## Complete Example Workflow

```bash
# 1. Start services
docker-compose up -d

# 2. Wait for health checks
sleep 30

# 3. Generate test data
python examples/generate_claude_usage_logs.py --conversations 100000

# 4. Check Spark status
curl http://localhost:8000/spark/status

# 5. Submit job
JOB_RESPONSE=$(curl -s -X POST "http://localhost:8000/spark/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/claude_usage_logs.parquet",
    "output_path": "/app/output/production/",
    "mode": "spark",
    "spark_master": "spark://spark-master:7077"
  }')

# 6. Extract job ID
JOB_ID=$(echo $JOB_RESPONSE | jq -r '.job_id')
echo "Job ID: $JOB_ID"

# 7. Monitor progress
docker-compose logs -f api | grep "$JOB_ID"

# 8. View Spark UI
open http://localhost:8080

# 9. Check results
ls -lh demo_output/production/

# 10. View persistent logs
tail -50 logs/spark-workers/spark.log
```

## Next Steps

1. **Read the main README**: See [README.md](README.md) for full project overview
2. **Explore the API**: Visit http://localhost:8000/docs for interactive API documentation
3. **Monitor metrics**: Open http://localhost:3000 for Grafana dashboards
4. **Scale the cluster**: Try `docker-compose up -d --scale spark-worker=10`
5. **Process your data**: Add your files to `demo_data/` and submit jobs

## Quick Commands Reference

```bash
# Start everything
docker-compose up -d

# Stop everything
docker-compose down

# View all logs
docker-compose logs -f

# Restart service
docker-compose restart spark-worker

# Scale workers
docker-compose up -d --scale spark-worker=5

# Check status
docker-compose ps

# Submit Spark job
curl -X POST "http://localhost:8000/spark/process" \
  -H "Content-Type: application/json" \
  -d '{"input_path":"/app/data/claude_usage_logs.parquet","output_path":"/app/output/test/","mode":"spark"}'

# Check Spark UI
open http://localhost:8080

# View API docs
open http://localhost:8000/docs
```
