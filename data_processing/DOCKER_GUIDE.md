# Docker Usage Guide

Complete guide for running the data processing infrastructure with Docker.

## Quick Start (3 Commands)

```bash
# 1. Build all Docker images
make docker-build

# 2. Start the entire stack
make docker-up

# 3. Check status
docker-compose ps
```

## What Gets Started

Running `make docker-up` starts **12 services**:

```
✅ data-processing-nginx    - Nginx Load Balancer     :8000
✅ data-processing-api      - FastAPI REST API        (internal)
✅ data-processing-postgres - PostgreSQL Database     :5432
✅ data-processing-redis    - Redis Cache             :6379
✅ data-processing-kafka    - Kafka Message Queue     :9092
✅ data-processing-zookeeper- Zookeeper               :2181
✅ data-processing-prometheus- Prometheus Metrics     :9090
✅ data-processing-grafana  - Grafana Dashboards      :3000
✅ spark-master             - Spark Master            :7077, :8080
✅ spark-worker (x2)        - Spark Workers
```

## Access the Services

### 1. FastAPI REST API (via Nginx Load Balancer)
```bash
# Open in browser
open http://localhost:8000/docs

# Or use curl
curl http://localhost:8000/health
```

**Architecture:**
- All requests go through Nginx load balancer on port 8000
- Nginx distributes requests across multiple API instances
- Scale horizontally: `docker-compose up -d --scale api=3`

**Available endpoints:**
- `GET /` - API info
- `GET /health` - Health check
- `GET /docs` - Interactive API documentation (Swagger)
- `GET /metrics` - Prometheus metrics
- `POST /process` - Process data file
- `POST /quality-check` - Run quality check

### 2. Grafana Dashboards
```bash
open http://localhost:3000
```
- **Username**: admin
- **Password**: admin

**What you can see:**
- Real-time processing metrics
- CPU and memory usage
- Request throughput
- Error rates
- Custom dashboards

### 3. Prometheus Metrics
```bash
open http://localhost:9090
```

**Example queries:**
```promql
# API request rate
rate(api_requests_total[5m])

# Records processed per second
rate(records_processed_total[1m])

# Memory usage
memory_usage_mb
```

### 4. Spark UI
```bash
open http://localhost:8080
```

View Spark cluster status, running jobs, and worker nodes.

## Horizontal Scaling

The API service supports horizontal scaling for high-throughput workloads:

```bash
# Scale API to 3 instances
docker-compose up -d --scale api=3

# Check running instances
docker-compose ps api

# Scale down to 1 instance
docker-compose up -d --scale api=1

# View load balancing in action
docker-compose logs -f nginx
```

**How it works:**
- Nginx load balancer distributes requests across all API instances
- Each API instance processes requests single-threaded (no multiprocessing)
- Scale horizontally by adding more containers instead of more workers per container
- Each container gets unique HOSTNAME for tracking (visible in logs)

## Using the API

### Process Data via API

```bash
# 1. Copy your data into any API container (nginx routes to all)
docker-compose ps -q api | head -1 | xargs -I {} docker cp demo_data/customers_small.parquet {}:/app/data/

# 2. Call the API to process it
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/customers_small.parquet",
    "output_path": "/app/output/processed",
    "file_type": "parquet",
    "enable_pii": true,
    "num_workers": 10,
    "chunk_size": 10000
  }'

# Response:
{
  "job_id": "abc-123-def-456",
  "status": "accepted",
  "message": "Processing job abc-123-def-456 started"
}
```

### Quality Check via API

```bash
curl -X POST http://localhost:8000/quality-check \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/app/data/customers_small.parquet"
  }'

# Response:
{
  "total_records": 10000,
  "total_columns": 10,
  "quality_score": 87.5,
  "issues_count": 5,
  "issues": [
    "Column 'phone' has 5.0% null values",
    "Found 200 duplicate rows (2.0% of data)"
  ]
}
```

## Development Workflow

### 1. Start Services
```bash
# Start all services in background
make docker-up

# Or start specific service
docker-compose up -d api
docker-compose up -d postgres
```

### 2. View Logs
```bash
# All services
make docker-logs

# Specific service
docker-compose logs -f api
docker-compose logs -f postgres

# Last 100 lines
docker-compose logs --tail=100 api
```

### 3. Execute Commands in Container
```bash
# Open shell in API container
docker-compose exec api /bin/bash

# Now you're inside the container, run commands:
python -m data_processing info
python -m data_processing process /app/data/input.parquet /app/output/
```

### 4. Run Tests in Container
```bash
docker-compose exec api pytest tests/ -v
```

### 5. Stop Services
```bash
# Stop all services
make docker-down

# Or stop specific service
docker-compose stop api
```

## Docker Images

### Production Image
```bash
# Build production image
docker build -t data-processing:latest --target production .

# Run production image
docker run -p 8000:8000 \
  -v $(pwd)/demo_data:/app/data:ro \
  -v $(pwd)/output:/app/output \
  data-processing:latest \
  uvicorn data_processing.api.main:app --host 0.0.0.0 --port 8000
```

### Development Image
```bash
# Build dev image (includes dev tools)
docker build -t data-processing-dev:latest --target development .

# Run with interactive shell
docker run -it --rm \
  -v $(pwd):/app \
  data-processing-dev:latest \
  /bin/bash
```

### Spark Worker Image
```bash
# Build Spark image
docker build -t data-processing-spark:latest --target spark-worker .

# Run Spark submit
docker run --rm \
  -v $(pwd)/demo_data:/app/data \
  data-processing-spark:latest \
  spark-submit --master local[*] /app/examples/spark_example.py
```

## Common Tasks

### Process Large Dataset
```bash
# 1. Start stack
make docker-up

# 2. Copy data
docker cp large_dataset.parquet data-processing-api:/app/data/

# 3. Process with API
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/large_dataset.parquet",
    "output_path": "/app/output/",
    "enable_pii": true,
    "num_workers": 10
  }'

# 4. Monitor in Grafana
open http://localhost:3000

# 5. Get results
docker cp data-processing-api:/app/output/. ./output/
```

### Run Scheduled Processing
```bash
# The stack includes a cron-like scheduler
# Edit docker-compose.yml to add your schedule

# Example: Daily processing at 2 AM
services:
  scheduler:
    image: data-processing:latest
    command: >
      sh -c "while true; do
        sleep 86400;
        python -m data_processing process /app/data/daily.parquet /app/output/
      done"
```

### Database Access
```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U dataprocessing -d metadata

# Run queries
\dt  # List tables
SELECT * FROM processing_jobs LIMIT 10;
```

### Redis Access
```bash
# Connect to Redis
docker-compose exec redis redis-cli

# Redis commands
KEYS *
GET some_key
```

### Kafka Testing
```bash
# Create topic
docker-compose exec kafka kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic data-processing \
  --partitions 3 \
  --replication-factor 1

# Produce messages
docker-compose exec kafka kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --topic data-processing

# Consume messages
docker-compose exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic data-processing \
  --from-beginning
```

## Troubleshooting

### Container Won't Start
```bash
# Check logs
docker-compose logs api

# Check container status
docker-compose ps

# Restart specific service
docker-compose restart api
```

### Out of Memory
```bash
# Check memory usage
docker stats

# Increase Docker memory limit
# Docker Desktop -> Settings -> Resources -> Memory
```

### Port Already in Use
```bash
# Check what's using the port
lsof -i :8000

# Kill the process or change port in docker-compose.yml
```

### Clean Everything
```bash
# Stop and remove all containers
docker-compose down

# Remove volumes (WARNING: deletes data)
docker-compose down -v

# Remove all images
docker rmi $(docker images -q data-processing*)

# Complete cleanup
make clean
docker system prune -a
```

## Multi-Architecture Builds

Build for both Intel and Apple Silicon:

```bash
# Create builder
docker buildx create --name mybuilder --use

# Build for multiple platforms
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t yourusername/data-processing:latest \
  --target production \
  --push .
```

## Docker Compose Commands Reference

```bash
# Start
docker-compose up -d                    # Start all services
docker-compose up -d api postgres       # Start specific services

# Stop
docker-compose down                     # Stop all services
docker-compose stop api                 # Stop specific service

# Logs
docker-compose logs -f                  # Follow all logs
docker-compose logs -f api              # Follow specific service
docker-compose logs --tail=100 api      # Last 100 lines

# Execute
docker-compose exec nginx /bin/sh          # Nginx shell (alpine)
docker-compose ps -q api | head -1 | xargs docker exec -it {} /bin/bash  # API shell

# Scale
docker-compose up -d --scale api=3         # Scale API workers
docker-compose up -d --scale spark-worker=5  # Scale Spark workers

# Rebuild
docker-compose build                    # Rebuild all
docker-compose build api                # Rebuild specific service

# Status
docker-compose ps                       # List services
docker-compose top                      # Show running processes
```

## Production Deployment

For production deployment:

1. **Use orchestration**: Kubernetes, Docker Swarm
2. **External databases**: Managed PostgreSQL, Redis
3. **Load balancing**: Nginx, Traefik, cloud LB
4. **Monitoring**: Prometheus + Grafana + AlertManager
5. **Secrets**: Vault, AWS Secrets Manager
6. **Logging**: ELK stack, Datadog, CloudWatch

See `PRODUCTION.md` for full production deployment guide.

## Performance Tips

### 1. Use Volumes for Data
```yaml
volumes:
  - ./data:/app/data:ro     # Read-only for safety
  - ./output:/app/output    # Read-write for results
```

### 2. Limit Resources
```yaml
deploy:
  resources:
    limits:
      cpus: '4'
      memory: 8G
    reservations:
      cpus: '2'
      memory: 4G
```

### 3. Use Networks
```yaml
networks:
  frontend:  # API, web services
  backend:   # Databases, queues
```

### 4. Health Checks
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

## Next Steps

1. ✅ Start with `make docker-up`
2. ✅ Explore API at http://localhost:8000/docs
3. ✅ Check Grafana dashboards at http://localhost:3000
4. ✅ Process some data via API
5. ✅ Monitor metrics in Prometheus

For Kubernetes deployment, see `deployment/k8s/` and `PRODUCTION.md`
