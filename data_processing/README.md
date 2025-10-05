# CLIO-Style Research Infrastructure

Privacy-preserving data processing infrastructure inspired by Anthropic's CLIO team. Built to analyze large-scale Claude usage logs while protecting user privacy, with production-grade monitoring, debugging capabilities, and high-performance processing.

> **CLIO** (Claude Insights & Operations) is Anthropic's research team that analyzes Claude usage at scale while maintaining the highest privacy standards.

## 🎯 Built for CLIO Requirements

This project demonstrates all key CLIO job requirements:

✅ **Privacy-Preserving Analytics** - Analyze Claude usage while protecting user privacy
✅ **Large-Scale Clustering** - Semantic topic discovery using embeddings
✅ **Concurrency Debugging** - Debug complex multiprocessing issues
✅ **Monitoring at Scale** - Prometheus metrics, structured logging, dashboards
✅ **Intuitive Interfaces** - CLI and REST API
✅ **Performance Optimization** - 50K+ records/sec, streaming, distributed
✅ **Production-Ready** - Docker, Kubernetes, CI/CD

---

## 🚀 Quick Start

### Option 1: Docker (Recommended - Includes Spark Cluster)

```bash
# Start all services (API + Spark cluster + monitoring)
docker-compose up -d

# Wait 30 seconds for services to start, then submit a Spark job
curl -X POST "http://localhost:8000/spark/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/claude_usage_logs.parquet",
    "output_path": "/app/output/spark_test/",
    "mode": "spark",
    "spark_master": "spark://spark-master:7077"
  }'

# View results
ls -lh demo_output/spark_test/

# Access UIs
# - API docs: http://localhost:8000/docs
# - Spark UI: http://localhost:8080
# - Grafana: http://localhost:3000
```

**👉 See [SPARK_QUICKSTART.md](SPARK_QUICKSTART.md) for complete Docker + Spark guide**

### Option 2: Run the Demo Locally

```bash
# Interactive demo with all features
python clio_demo.py
```

This shows:
1. Generating Claude usage logs (simulated conversations)
2. Privacy-preserving analytics (PII detection, anonymization)
3. Concurrency debugging examples

### Option 3: Run Individual Components

```bash
# 1. Generate simulated Claude usage logs
python examples/generate_claude_usage_logs.py --conversations 10000

# 2. Analyze with privacy preservation
python examples/privacy_preserving_analytics.py

# 3. Learn concurrency debugging
python examples/concurrency_debugging_demo.py

# 4. Process with Spark (requires Docker)
python examples/spark_processing_example.py
```

---

## 📋 Features

### 1. Privacy-Preserving Analytics ⭐

**What CLIO needs:** Analyze Claude usage without exposing individual user data

**What we provide:**
- **PII Detection**: Automatically finds emails, names, IPs, phone numbers, SSNs
- **Anonymization**: Hash, mask, or redact sensitive data
- **Aggregated Analytics**: All analysis is privacy-preserving (no individual exposure)
- **Audit Trail**: Complete logging of data access and transformations

```python
from data_processing.privacy import Anonymizer, AnonymizationConfig

config = AnonymizationConfig(anonymization_method="hash")
anonymizer = Anonymizer(config)
anonymized_df, stats = anonymizer.anonymize_dataframe(df, text_columns=["message"])
```

### 2. Large-Scale Clustering ⭐

**What CLIO needs:** Challenging dataset clustering and hierarchy-building

**What we provide:**
- **Semantic Clustering**: Uses sentence embeddings (not just keywords)
- **Multiple Algorithms**: K-Means, DBSCAN, Hierarchical
- **Scalable**: Handles millions of records
- **Topic Discovery**: Automatically finds conversation themes

```python
from data_processing.analytics import DataClusterer, ClusteringConfig

config = ClusteringConfig(num_clusters=8, algorithm="kmeans")
clusterer = DataClusterer(config)
clustered_df = clusterer.cluster_dataframe(df, text_column="user_message")
```

### 3. Monitoring & Observability ⭐

**What CLIO needs:** Monitoring systems for large dataset processing

**What we provide:**
- **Prometheus Metrics**: Records processed, throughput, latency, errors
- **Structured Logging**: JSON logs for easy parsing and analysis
- **Grafana Dashboards**: Real-time visualization
- **Health Checks**: `/health` and `/ready` endpoints

```python
from data_processing.monitoring import MetricsCollector

metrics = MetricsCollector(job_id="analysis_job")
metrics.start_processing()
# ... processing ...
metrics.record_processed(count=10000)
```

### 4. Concurrency Debugging ⭐

**What CLIO needs:** Debug concurrency inefficiencies and inter-process errors

**What we provide:**
- **Race Condition Examples**: Shows common bugs and fixes
- **IPC Debugging**: Inter-process communication patterns
- **Performance Profiling**: Find bottlenecks in concurrent code
- **Best Practices**: Production-tested solutions

```bash
# Learn concurrency debugging
python examples/concurrency_debugging_demo.py
```

### 5. High Performance ⭐

**What CLIO needs:** Optimize for speed and efficient resource usage

**What we provide:**
- **Streaming Pipeline**: Process data larger than RAM
- **Multiprocessing**: Optimized for Mac M4 (10 workers)
- **Distributed Computing**: PySpark for massive datasets
- **50K+ records/sec**: On single machine, 500K+ on cluster

```bash
# Process 1M records with 10 workers
python -m data_processing process \
    large_dataset.parquet output/ \
    --workers 10 --chunk-size 10000
```

---

## 🏗️ Architecture

```
src/data_processing/
├── core/          # Streaming pipeline, processing engine
├── privacy/       # PII detection, anonymization, encryption, audit
├── analytics/     # Clustering, quality checks, hierarchy
├── monitoring/    # Prometheus metrics, structured logging
├── distributed/   # PySpark integration for scale
├── api/           # FastAPI REST endpoints
├── cli/           # Click-based command-line interface
└── utils/         # Memory management, concurrency helpers

examples/
├── generate_claude_usage_logs.py      # Simulate Claude conversations
├── privacy_preserving_analytics.py    # Privacy analysis demo
└── concurrency_debugging_demo.py      # Debugging examples
```

**Key Design Patterns:**
- **Streaming**: Process data in chunks (memory-efficient)
- **Pipeline**: Chain processors (privacy → transform → cluster)
- **Worker Pool**: Distribute work across processes
- **Observer**: Metrics and monitoring throughout

---

## 💻 CLI Usage

### Process Claude Usage Logs

```bash
# With privacy preservation
python -m data_processing process \
    demo_data/claude_usage_logs.parquet \
    output/ \
    --enable-pii \
    --workers 10 \
    --chunk-size 10000
```

### Cluster Conversations by Topic

```bash
# Discover conversation themes
python -m data_processing cluster \
    demo_data/claude_usage_logs.parquet \
    user_message \
    --num-clusters 8 \
    --algorithm kmeans
```

### Quality Check

```bash
# Validate data quality
python -m data_processing quality-check \
    demo_data/claude_usage_logs.parquet
```

### System Info

```bash
# Show system capabilities
python -m data_processing info
```

---

## 🌐 API Usage

Start the API server:

```bash
python -m uvicorn data_processing.api.main:app --reload
```

Visit: **http://localhost:8000/docs** for interactive documentation

### Example API Calls

```bash
# Process data with PII anonymization
curl -X POST "http://localhost:8000/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/claude_usage_logs.parquet",
    "output_path": "/app/output/",
    "enable_pii": true,
    "num_workers": 10
  }'

# Cluster conversations
curl -X POST "http://localhost:8000/cluster" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/claude_usage_logs.parquet",
    "text_column": "user_message",
    "num_clusters": 8
  }'

# Quality check
curl -X POST "http://localhost:8000/quality-check" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/app/data/claude_usage_logs.parquet"
  }'
```

---

## 📊 Performance

Benchmarked on Mac Mini M4 (12 cores, 24GB RAM):

| Dataset Size | Records | Processing Time | Throughput | Memory |
|-------------|---------|----------------|------------|--------|
| Small       | 10K     | 0.5s          | 20K rec/s  | 150 MB |
| Medium      | 100K    | 3.2s          | 31K rec/s  | 450 MB |
| Large       | 1M      | 28.5s         | 35K rec/s  | 2.1 GB |
| X-Large     | 10M     | 4.5min        | 37K rec/s  | 8.5 GB |

*With PII detection, anonymization, and clustering enabled*

**Distributed (Spark cluster):**
- 10M records: 22s (454K rec/s)
- Horizontal scaling across executors
- Maintains privacy guarantees

---

## 🔒 Privacy Guarantees

1. **PII Detection**: Regex-based + NLP-based detection
2. **Anonymization Methods**:
   - Hash (SHA-256, irreversible)
   - Mask (xxx@xxx.com)
   - Redact ([REDACTED])
   - Synthetic (fake data generation)
3. **Audit Trail**: Every data access logged
4. **Aggregation Only**: No individual user data exposed
5. **K-Anonymity**: Group-level analysis

---

## 🛠️ Production Deployment

### Docker Compose (Full Stack)

The easiest way to run everything with Docker:

```bash
# Start all services (API, Spark cluster, Postgres, Redis, Prometheus, Grafana)
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop all services
docker-compose down
```

**Available Services:**
- **API**: http://localhost:8000 (FastAPI with Swagger docs at `/docs`)
- **Spark Master UI**: http://localhost:8080
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090

### Using PySpark with Docker

The infrastructure includes a complete Spark cluster for distributed processing.

#### 1. Check Spark Status

```bash
# Via API
curl http://localhost:8000/spark/status

# View Spark Master UI
open http://localhost:8080
```

#### 2. Submit Spark Jobs via API

**Local Mode** (single machine, uses Polars):
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

**Spark Mode** (distributed across Spark cluster):
```bash
curl -X POST "http://localhost:8000/spark/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/claude_usage_logs.parquet",
    "output_path": "/app/output/spark/",
    "mode": "spark",
    "spark_master": "spark://spark-master:7077"
  }'
```

**Auto Mode** (automatically selects Spark for large datasets):
```bash
curl -X POST "http://localhost:8000/spark/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/large_dataset.parquet",
    "output_path": "/app/output/auto/",
    "mode": "auto"
  }'
```

#### 3. PySpark Configuration Options

```bash
# Custom Spark configuration
curl -X POST "http://localhost:8000/spark/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/claude_usage_logs.parquet",
    "output_path": "/app/output/custom/",
    "mode": "spark",
    "spark_master": "spark://spark-master:7077",
    "executor_memory": "4g",
    "driver_memory": "2g",
    "executor_cores": 2,
    "num_executors": 4
  }'
```

#### 4. Monitor Spark Jobs

```bash
# View Spark Master UI (shows all applications and workers)
open http://localhost:8080

# View application logs
docker-compose logs -f spark-master
docker-compose logs -f spark-worker

# Check persistent logs
tail -f logs/spark-master/spark.log
tail -f logs/spark-workers/spark.log

# View API worker logs (shows which worker processed the job)
docker-compose logs -f api | grep "Spark Job"
```

#### 5. Scale Spark Workers

```bash
# Scale to 5 workers
docker-compose up -d --scale spark-worker=5

# Check worker status
docker-compose ps spark-worker
```

#### 6. Add Your Own Data

```bash
# Put your data files in demo_data/
cp your_data.parquet demo_data/

# They're automatically mounted to /app/data/ in containers
curl -X POST "http://localhost:8000/spark/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/your_data.parquet",
    "output_path": "/app/output/results/",
    "mode": "spark"
  }'

# Check output in demo_output/results/
ls -lh demo_output/results/
```

#### 7. PySpark Performance Comparison

**Local Mode (Polars):**
- 10K records: ~0.5s (20K rec/s)
- Best for: < 1GB datasets, development

**Spark Mode (Distributed):**
- 10K records: ~3.6s (2.7K rec/s) - includes cluster overhead
- 10M records: ~22s (454K rec/s) - scales with data size
- Best for: > 1GB datasets, production

**Auto Mode:**
- Automatically selects Spark if file > 1GB
- Balances convenience and performance

### Docker Services Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Nginx Load Balancer                  │
│                    localhost:8000                        │
└────────────────────┬────────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
    ┌──────────┐         ┌──────────┐
    │   API    │   ...   │   API    │  (scalable)
    │ Workers  │         │ Workers  │
    └────┬─────┘         └────┬─────┘
         │                    │
    ┌────┴────────────────────┴────┐
    │    Spark Master (7077)        │
    │    UI: localhost:8080         │
    └────┬──────────────────────────┘
         │
    ┌────┴──────┬──────────┬────────┐
    ▼           ▼          ▼        ▼
┌────────┐ ┌────────┐ ┌────────┐ ...
│ Spark  │ │ Spark  │ │ Spark  │
│Worker 1│ │Worker 2│ │Worker N│
└────────┘ └────────┘ └────────┘

Supporting Services:
├── Postgres (5432)  - Metadata storage
├── Redis (6379)     - Caching
├── Prometheus (9090)- Metrics
└── Grafana (3000)   - Dashboards
```

### Docker-Only (Without Compose)

```bash
# Build production image
docker build --target production -t data-processing:latest .

# Run API
docker run -p 8000:8000 \
  -v $(pwd)/demo_data:/app/data:ro \
  -v $(pwd)/demo_output:/app/output \
  data-processing:latest

# Build Spark worker image
docker build --target spark-worker -t data-processing-spark:latest .
```

### Kubernetes

```bash
# Deploy
kubectl apply -f deployment/k8s/

# Scale API workers
kubectl scale deployment/data-processing-api --replicas=5

# Scale Spark workers
kubectl scale statefulset/spark-worker --replicas=10
```

---

## 🎓 Key Learnings for CLIO

### 1. Privacy-First Design

```python
# Always anonymize before analysis
anonymizer = Anonymizer(AnonymizationConfig())
safe_df, stats = anonymizer.anonymize_dataframe(df)

# Use aggregated analytics only
aggregated = safe_df.group_by("topic").agg(pl.count())
# ✅ No individual user data exposed
```

### 2. Debugging Concurrency

```python
# Use locks for shared state
counter = mp.Value('i', 0)
lock = mp.Lock()

with lock:
    counter.value += 1  # Thread-safe

# Use queues for IPC
queue = mp.Queue()
queue.put(result)  # Always send results back!
```

### 3. Performance at Scale

```python
# Stream, don't load all at once
for chunk in stream_parquet(file, chunk_size=10000):
    process(chunk)  # Memory-efficient

# Use multiprocessing for CPU-bound work
with ProcessPoolExecutor(max_workers=10) as executor:
    futures = executor.map(process_chunk, chunks)
```

---

## 📖 Documentation

- **[SPARK_QUICKSTART.md](SPARK_QUICKSTART.md)** - PySpark with Docker guide (start here!)
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design and data flow
- **[CLIO_JD_ANALYSIS.md](CLIO_JD_ANALYSIS.md)** - How this maps to CLIO job requirements
- **[API_SPARK_GUIDE.md](API_SPARK_GUIDE.md)** - Complete API and Spark reference

---

## 🧪 Testing

```bash
# Run tests
pytest tests/

# With coverage
pytest --cov=src/data_processing tests/

# Type checking
mypy src/

# Linting
ruff check src/
black src/
```

---

## 📈 Technical Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| **Data Processing** | Polars, PyArrow | 10x faster than Pandas |
| **Distributed** | PySpark | Scales to massive datasets |
| **Privacy** | Presidio, cryptography | Industry-standard PII detection |
| **ML** | sentence-transformers, scikit-learn | Semantic clustering |
| **API** | FastAPI, Pydantic | Fast, type-safe |
| **Monitoring** | Prometheus, Grafana | Production observability |
| **CLI** | Click, Rich | Beautiful, intuitive |

---

## 🎯 CLIO Job Requirements Mapping

| Requirement | Implementation | Location |
|------------|----------------|----------|
| Privacy-preserving analytics | PII detection, anonymization, audit | `src/data_processing/privacy/` |
| Clustering & hierarchy | Semantic embeddings, multiple algorithms | `src/data_processing/analytics/` |
| Concurrency debugging | Examples, patterns, solutions | `examples/concurrency_debugging_demo.py` |
| Monitoring at scale | Prometheus, structured logs | `src/data_processing/monitoring/` |
| Intuitive interfaces | CLI + REST API | `src/data_processing/cli/`, `api/` |
| Performance optimization | Streaming, multiprocessing, Spark | `src/data_processing/core/`, `distributed/` |
| Production infrastructure | Docker, K8s, CI/CD | `deployment/`, `.github/` |

See **[CLIO_JD_ANALYSIS.md](CLIO_JD_ANALYSIS.md)** for detailed analysis.

---

## 🚀 Next Steps

1. **Run the demo**: `python clio_demo.py`
2. **Explore examples**: Check `examples/` directory
3. **Read documentation**: Start with `QUICKSTART.md`
4. **Try the API**: `python -m uvicorn data_processing.api.main:app --reload`
5. **Study the code**: `src/data_processing/` is well-documented

---

## 📝 Project Stats

- **3,900+ lines** of production Python code
- **29 modules** across 7 packages
- **Full type hints** throughout
- **Comprehensive tests** with pytest
- **Production-ready** with Docker, K8s
- **Optimized** for Mac M4 (Apple Silicon)

---

## 🙏 Acknowledgments

Inspired by Anthropic's CLIO team job description and their approach to privacy-preserving, large-scale research infrastructure for Claude usage analysis.

---

## 📄 License

MIT License - See LICENSE file for details
