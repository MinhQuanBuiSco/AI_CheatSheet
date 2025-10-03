# Production Deployment Guide

Complete guide for deploying the data processing infrastructure to production.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Load Balancer                            │
└────────────────┬────────────────────────────────────────────────┘
                 │
      ┌──────────┴──────────┐
      │                     │
┌─────▼─────┐        ┌──────▼──────┐
│  FastAPI  │        │   FastAPI   │
│  Pod 1    │        │   Pod 2-N   │
└─────┬─────┘        └──────┬──────┘
      │                     │
      └──────────┬──────────┘
                 │
    ┌────────────┴────────────┐
    │                         │
┌───▼────┐  ┌──────┐  ┌──────▼─────┐
│Postgres│  │ Redis │  │   Kafka    │
└────────┘  └───────┘  └────────────┘
    │
┌───▼────────┐  ┌──────────┐  ┌────────┐
│ Prometheus │  │ Grafana  │  │  Spark │
└────────────┘  └──────────┘  └────────┘
```

## Prerequisites

- Kubernetes cluster (EKS, GKE, AKS, or self-hosted)
- kubectl configured
- Docker registry access (GitHub Container Registry, ECR, GCR, etc.)
- Helm 3+ (optional, for easier deployment)
- Terraform (for infrastructure provisioning)

## Quick Start

### 1. Local Development

```bash
# Install dependencies
make install-all

# Run tests
make test

# Start local stack
make docker-up

# Access services:
# - API: http://localhost:8000
# - Grafana: http://localhost:3000
# - Prometheus: http://localhost:9090
```

### 2. Build and Push Images

```bash
# Build multi-arch images
docker buildx build --platform linux/amd64,linux/arm64 \
  -t ghcr.io/yourusername/data-processing:latest \
  --target production \
  --push .

# Build Spark worker
docker buildx build --platform linux/amd64,linux/arm64 \
  -t ghcr.io/yourusername/data-processing-spark:latest \
  --target spark-worker \
  --push .
```

### 3. Deploy to Kubernetes

```bash
# Create namespace and secrets
kubectl create namespace data-processing

# Create secrets (update values first!)
kubectl create secret generic data-processing-secrets \
  --from-literal=postgres_password=YOUR_PASSWORD \
  --from-literal=redis_url=redis://redis:6379 \
  --from-literal=aws_access_key_id=YOUR_KEY \
  --from-literal=aws_secret_access_key=YOUR_SECRET \
  -n data-processing

# Deploy using Kustomize
kubectl apply -k deployment/k8s/base/

# Check deployment
kubectl get all -n data-processing

# Watch rollout
kubectl rollout status deployment/data-processing-api -n data-processing
```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `LOG_LEVEL` | Logging level | INFO | No |
| `API_HOST` | API host | 0.0.0.0 | No |
| `API_PORT` | API port | 8000 | No |
| `POSTGRES_HOST` | PostgreSQL host | localhost | Yes |
| `POSTGRES_PASSWORD` | PostgreSQL password | - | Yes |
| `REDIS_URL` | Redis connection URL | - | Yes |
| `AWS_ACCESS_KEY_ID` | AWS access key | - | For S3 |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | - | For S3 |

### ConfigMap

Edit `deployment/k8s/base/configmap.yaml`:

```yaml
data:
  log_level: "INFO"
  num_workers: "10"
  chunk_size: "10000"
  enable_pii_detection: "true"
```

## Scaling

### Horizontal Pod Autoscaling

HPA is configured to scale based on CPU and memory:

```yaml
minReplicas: 3
maxReplicas: 20
targetCPUUtilizationPercentage: 70
targetMemoryUtilizationPercentage: 80
```

### Manual Scaling

```bash
# Scale API pods
kubectl scale deployment data-processing-api --replicas=10 -n data-processing

# Scale Spark workers
kubectl scale deployment spark-worker --replicas=5 -n data-processing
```

## Monitoring

### Prometheus Metrics

Metrics exposed at `/metrics`:

- `api_requests_total` - Total API requests
- `api_duration_seconds` - Request duration
- `records_processed_total` - Total records processed
- `processing_duration_seconds` - Processing duration
- `cpu_usage_percent` - CPU usage
- `memory_usage_mb` - Memory usage

### Grafana Dashboards

Access Grafana at `http://grafana.your-domain.com` (default: admin/admin)

Pre-configured dashboards:
1. **API Performance**: Request rates, latency, errors
2. **Data Processing**: Throughput, queue depth, processing time
3. **System Resources**: CPU, memory, disk usage
4. **Spark Cluster**: Executors, tasks, shuffle

### Alerts

Configure alerts in `deployment/prometheus/alerts.yml`:

```yaml
groups:
  - name: data_processing
    rules:
      - alert: HighErrorRate
        expr: rate(api_errors_total[5m]) > 0.05
        annotations:
          summary: "High error rate detected"
```

## Security

### 1. Secrets Management

**Production**: Use external secrets management

```bash
# Sealed Secrets
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/controller.yaml

# External Secrets Operator
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets -n external-secrets
```

### 2. Network Policies

```bash
kubectl apply -f deployment/k8s/network-policies.yaml
```

### 3. Pod Security

- Runs as non-root user (UID 1000)
- Read-only root filesystem
- No privilege escalation
- Capabilities dropped

### 4. Image Scanning

CI/CD includes Trivy scanning:

```bash
# Manual scan
trivy image ghcr.io/yourusername/data-processing:latest
```

## Backup and Disaster Recovery

### PostgreSQL Backups

```bash
# Daily automated backups
kubectl create cronjob postgres-backup \
  --image=postgres:16 \
  --schedule="0 2 * * *" \
  -- pg_dump -h postgres -U dataprocessing metadata > /backups/db-$(date +%Y%m%d).sql
```

### Data Backups

Configure PVC snapshots or use cloud-native backup solutions:

- AWS: EBS snapshots
- GCP: Persistent Disk snapshots
- Azure: Disk snapshots

## Performance Tuning

### Kubernetes Resources

Tune requests/limits based on workload:

```yaml
resources:
  requests:
    cpu: "2000m"      # 2 cores
    memory: "4Gi"
  limits:
    cpu: "4000m"      # 4 cores
    memory: "8Gi"
```

### PySpark Configuration

For distributed processing:

```python
spark_config = SparkConfig(
    master="k8s://https://kubernetes.default.svc",
    executor_memory="8g",
    driver_memory="4g",
    num_executors=10,
)
```

### Database Tuning

PostgreSQL connection pooling:

```python
# Use pgbouncer
POSTGRES_URL = "postgresql://user:pass@pgbouncer:6432/metadata?pool_size=20"
```

## Troubleshooting

### Check Logs

```bash
# API logs
kubectl logs -n data-processing -l app=data-processing --tail=100 -f

# Specific pod
kubectl logs -n data-processing data-processing-api-xxx -f

# Previous pod (after crash)
kubectl logs -n data-processing data-processing-api-xxx --previous
```

### Debug Pod

```bash
# Exec into pod
kubectl exec -it -n data-processing data-processing-api-xxx -- /bin/bash

# Run diagnostics
kubectl run debug --rm -i --tty --image=busybox -n data-processing -- sh
```

### Common Issues

**1. Out of Memory**
```bash
# Check memory usage
kubectl top pods -n data-processing

# Increase memory limits
kubectl set resources deployment data-processing-api \
  --limits=memory=16Gi -n data-processing
```

**2. Slow Processing**
```bash
# Scale workers
kubectl scale deployment data-processing-api --replicas=20 -n data-processing

# Check PVC performance
kubectl get pvc -n data-processing
```

**3. Database Connection Issues**
```bash
# Test connectivity
kubectl run pg-test --rm -i --tty --image=postgres:16 -n data-processing \
  -- psql -h postgres -U dataprocessing -d metadata
```

## Cost Optimization

### 1. Use Spot/Preemptible Instances

```yaml
nodeSelector:
  cloud.google.com/gke-preemptible: "true"  # GKE
  eks.amazonaws.com/capacityType: SPOT      # EKS
```

### 2. Autoscaling

- HPA for API pods
- Cluster autoscaler for nodes
- Karpenter for advanced provisioning

### 3. Resource Optimization

```bash
# Right-size requests
kubectl get vpa -n data-processing

# Monitor waste
kubectl cost -n data-processing
```

## Compliance

### Data Privacy (GDPR, CCPA)

- PII detection enabled by default
- Audit logging for all data access
- Data retention policies
- Right to be forgotten support

### SOC 2 / ISO 27001

- Access control (RBAC)
- Encryption at rest and in transit
- Audit trails
- Vulnerability scanning

## Support

- Documentation: `/docs` endpoint
- Health check: `/health`
- Metrics: `/metrics`
- API docs: `/docs` (Swagger UI)

## License

MIT License
