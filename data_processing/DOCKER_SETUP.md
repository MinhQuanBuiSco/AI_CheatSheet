# Docker Setup Summary

## What We Built

A complete production-ready data processing infrastructure with:

✅ **FastAPI REST API** with horizontal scaling  
✅ **Apache Spark 3.5.0** distributed cluster  
✅ **PySpark 3.5.0** for Python integration  
✅ **Monitoring stack** (Prometheus + Grafana)  
✅ **Caching & storage** (Redis + PostgreSQL)  
✅ **Load balancing** (Nginx)  

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    Your Machine                             │
│                                                             │
│  demo_data/              demo_output/         logs/         │
│  └── *.parquet     ←→    └── results/   ←→   └── *.log     │
│       ↕                       ↕                   ↕         │
└───────┼───────────────────────┼───────────────────┼─────────┘
        │                       │                   │
        │  Volume Mounts        │                   │
        ↓                       ↓                   ↓
┌────────────────────────────────────────────────────────────┐
│              Docker Containers (11 services)                │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │   Nginx Load Balancer :80 → localhost:8000          │  │
│  └─────────────┬────────────────────────────────────────┘  │
│                │                                            │
│       ┌────────┴────────┐                                  │
│       ▼                 ▼                                   │
│  ┌─────────┐       ┌─────────┐                            │
│  │  API-1  │  ...  │  API-N  │  (Scalable Workers)        │
│  │ :8000   │       │ :8000   │                            │
│  └────┬────┘       └────┬────┘                            │
│       │                 │                                   │
│       │ Submits Jobs    │                                   │
│       ↓                 ↓                                   │
│  ┌──────────────────────────────────┐                      │
│  │   Spark Master :7077             │                      │
│  │   UI: localhost:8080             │                      │
│  └──────────┬───────────────────────┘                      │
│             │                                               │
│    ┌────────┼────────┬────────┐                           │
│    ▼        ▼        ▼        ▼                            │
│  ┌────┐  ┌────┐  ┌────┐  ┌────┐                          │
│  │ W1 │  │ W2 │  │ W3 │  │ WN │  (Spark Workers)          │
│  │ 4c │  │ 4c │  │ 4c │  │ 4c │  Scalable: --scale=N     │
│  │ 4g │  │ 4g │  │ 4g │  │ 4g │                           │
│  └────┘  └────┘  └────┘  └────┘                          │
│                                                             │
│  Supporting Services:                                       │
│  ├─ PostgreSQL :5432    (Metadata)                        │
│  ├─ Redis :6379         (Caching)                         │
│  ├─ Prometheus :9090    (Metrics)                         │
│  └─ Grafana :3000       (Dashboards)                      │
└─────────────────────────────────────────────────────────────┘
```

## Files Created/Modified

### 1. Dockerfile (Multi-stage)
```dockerfile
# Stage 1: base          - Python 3.12 + system deps
# Stage 2: builder       - Install packages with uv
# Stage 3: production    - API runtime with Java 21
# Stage 4: development   - Adds dev tools
# Stage 5: spark-worker  - Spark 3.5.0 runtime
```

**Key fixes:**
- Added OpenJDK 21 to production stage (for Spark driver)
- Pinned PySpark to 3.5.0 (matches Spark cluster)
- Fixed Spark worker permissions (chown /opt/spark)
- Used `mv` instead of symlink for Spark installation

### 2. docker-compose.yml
```yaml
services:
  api:           # FastAPI with Java (Spark driver)
  spark-master:  # Spark 3.5.0 master
  spark-worker:  # Scalable workers (default: 2)
  postgres:      # Metadata storage
  redis:         # Caching
  prometheus:    # Metrics collection
  grafana:       # Visualization
  nginx:         # Load balancer
```

**Key fixes:**
- Added data volumes to spark-worker (was missing!)
- Mounted demo_data/ to /app/data in workers
- Mounted demo_output/ to /app/output in workers
- Added log4j2.properties volume mounts

### 3. Source Code Fixes

**spark_engine.py:**
- Fixed `getActiveSession()` check for stopped sessions
- Added fallback for `getActiveJobIds()` API change in PySpark 3.5
- Properly cleanup stopped sessions before creating new ones

**distributed_pipeline.py:**
- No changes needed (already correct!)

**api/main.py:**
- Already had comprehensive logging
- Worker ID tracking working

## Services & Ports

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| API | 8000 | http://localhost:8000 | REST API |
| API Docs | 8000 | http://localhost:8000/docs | Swagger UI |
| Spark Master | 7077 | spark://localhost:7077 | Spark cluster |
| Spark UI | 8080 | http://localhost:8080 | Job monitoring |
| PostgreSQL | 5432 | localhost:5432 | Metadata |
| Redis | 6379 | localhost:6379 | Cache |
| Prometheus | 9090 | http://localhost:9090 | Metrics |
| Grafana | 3000 | http://localhost:3000 | Dashboards |

## Common Commands

```bash
# Start everything
docker-compose up -d

# View logs
docker-compose logs -f api              # API logs
docker-compose logs -f spark-master     # Master logs
docker-compose logs -f spark-worker     # Worker logs

# Scale workers
docker-compose up -d --scale spark-worker=5

# Restart service
docker-compose restart api

# Stop everything
docker-compose down

# Check status
docker-compose ps

# Execute commands in container
docker-compose exec api python -m data_processing info
docker-compose exec spark-master /opt/spark/bin/spark-shell --version
```

## Testing the Setup

```bash
# 1. Start services
docker-compose up -d && sleep 30

# 2. Check Spark status
curl http://localhost:8000/spark/status

# 3. Submit test job
curl -X POST "http://localhost:8000/spark/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/claude_usage_logs.parquet",
    "output_path": "/app/output/test/",
    "mode": "spark"
  }'

# 4. Verify output
ls -lh demo_output/test/

# 5. View Spark UI
open http://localhost:8080
```

## Issues Fixed

1. **PySpark version mismatch** → Pinned to 3.5.0
2. **Missing Java in API** → Added OpenJDK 21
3. **Worker permissions** → Fixed /opt/spark/work ownership
4. **Stopped session reuse** → Added session health checks
5. **Data not in workers** → Added volume mounts
6. **API changes** → Fixed getActiveJobIds() compatibility

## Performance Results

**Successful test:**
```
✓ Engine: spark
✓ Records: 10,000
✓ Time: 3.61s
✓ Throughput: 2,771 rec/s
✓ Output: part-00000-*.snappy.parquet
```

## Next Steps

1. Read [SPARK_QUICKSTART.md](SPARK_QUICKSTART.md)
2. Try scaling: `docker-compose up -d --scale spark-worker=10`
3. Process your own data in `demo_data/`
4. Monitor jobs at http://localhost:8080
5. View dashboards at http://localhost:3000

## Troubleshooting

See [SPARK_QUICKSTART.md](SPARK_QUICKSTART.md) Troubleshooting section.
