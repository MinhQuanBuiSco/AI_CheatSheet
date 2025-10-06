# 🚀 Deployment Guide - Data Processing Infrastructure with Spark

Complete guide for deploying the data processing infrastructure with Spark cluster on Kubernetes (Minikube).

---

## 📋 Prerequisites

### Required Tools
- **Docker Desktop** (with at least 16GB RAM allocated)
- **Minikube** (`brew install minikube`)
- **kubectl** (`brew install kubectl`)

### System Requirements
- macOS with ARM64 (Apple Silicon) or AMD64
- Minimum 16GB system RAM
- 20GB free disk space

---

## 🛠️ Quick Start

### 1. Clean Up (if redeploying)
```bash
bash scripts/cleanup.sh
```

### 2. Deploy Everything
```bash
bash scripts/deploy.sh
```

### 3. Run Tests
```bash
bash scripts/test.sh
```

---

## 📝 Detailed Deployment Steps

### Step 1: Verify Prerequisites
```bash
# Check Docker
docker --version

# Check Minikube
minikube version

# Check kubectl
kubectl version --client
```

### Step 2: Configure Docker Desktop
1. Open Docker Desktop → Settings → Resources
2. Set Memory to **16GB**
3. Set CPUs to **4 cores**
4. Apply & Restart

### Step 3: Start Minikube
```bash
# Start with 12GB RAM and 4 CPUs
minikube start --memory=12288 --cpus=4 --driver=docker

# Verify
minikube status
```

### Step 4: Build Docker Image
```bash
# For Apple Silicon (ARM64)
docker build --platform linux/arm64 -t data-processing:v1.0.0 -f Dockerfile --target production .

# For Intel/AMD (AMD64)
docker build --platform linux/amd64 -t data-processing:v1.0.0 -f Dockerfile --target production .
```

### Step 5: Load Image into Minikube
```bash
# Save image
docker save data-processing:v1.0.0 -o /tmp/data-processing-v1.0.0.tar

# Copy to Minikube
minikube cp /tmp/data-processing-v1.0.0.tar /tmp/data-processing-v1.0.0.tar

# Load in Minikube
minikube ssh "docker load -i /tmp/data-processing-v1.0.0.tar"

# Cleanup
rm /tmp/data-processing-v1.0.0.tar
```

### Step 6: Create Namespace
```bash
kubectl create namespace data-processing
```

### Step 7: Deploy Resources
```bash
# Apply in correct order
kubectl apply -f deployment/k8s/base/pvc.yaml
kubectl apply -f deployment/k8s/base/minio-deployment.yaml
kubectl apply -f deployment/k8s/base/spark-cluster.yaml
kubectl apply -f deployment/k8s/base/deployment.yaml
```

### Step 8: Wait for Pods
```bash
# Watch pods come up
kubectl get pods -n data-processing -w

# Or wait for each component
kubectl wait --for=condition=ready pod -l app=minio -n data-processing --timeout=120s
kubectl wait --for=condition=ready pod -l component=spark-master -n data-processing --timeout=120s
kubectl wait --for=condition=ready pod -l component=spark-worker -n data-processing --timeout=120s
kubectl wait --for=condition=ready pod -l component=api -n data-processing --timeout=120s
```

### Step 9: Setup Port Forwards
```bash
# API
kubectl port-forward -n data-processing svc/data-processing-api 8000:80 &

# MinIO
kubectl port-forward -n data-processing svc/minio 9000:9000 9001:9001 &

# Spark Master UI
kubectl port-forward -n data-processing svc/spark-master 8080:8080 &
```

### Step 10: Verify Deployment
```bash
# Check API health
curl http://localhost:8000/health

# Check MinIO
curl http://localhost:9000/minio/health/live

# Check Spark Master
curl http://localhost:8080
```

---

## 🧪 Testing

### Run Full Test Suite
```bash
bash scripts/test.sh
```

This will:
1. Generate 1000 test records
2. Upload to MinIO (s3://data-processing/input/)
3. Submit Spark job for processing
4. Verify output in MinIO (s3://data-processing/output/)

### Manual Test
```bash
# Submit a job manually
curl -X POST "http://localhost:8000/spark/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "s3://data-processing/input/test.parquet",
    "output_path": "s3://data-processing/output/result",
    "mode": "spark",
    "executor_memory": "2g",
    "driver_memory": "1g",
    "executor_cores": 2
  }'
```

---

## 🌐 Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| **API** | http://localhost:8000 | - |
| **API Health** | http://localhost:8000/health | - |
| **MinIO Console** | http://localhost:9001 | minioadmin / minioadmin |
| **MinIO S3 API** | http://localhost:9000 | minioadmin / minioadmin |
| **Spark Master UI** | http://localhost:8080 | - |

---

## 🔍 Debugging

### Check Logs
```bash
# API logs
kubectl logs -n data-processing -l component=api --tail=50

# Spark Master logs
kubectl logs -n data-processing -l component=spark-master --tail=50

# Spark Worker logs
kubectl logs -n data-processing -l component=spark-worker --tail=50

# MinIO logs
kubectl logs -n data-processing -l app=minio --tail=50
```

### Check Resources
```bash
# All pods
kubectl get pods -n data-processing

# All services
kubectl get svc -n data-processing

# Persistent volumes
kubectl get pvc -n data-processing
```

### Common Issues

#### 1. Pods Stuck in Pending
**Cause**: Insufficient resources
```bash
# Check Minikube resources
minikube ssh "free -h"
minikube ssh "df -h"

# Increase Minikube memory
minikube delete
minikube start --memory=12288 --cpus=4
```

#### 2. ImagePullBackOff
**Cause**: Image not in Minikube's Docker
```bash
# Reload image
minikube image load data-processing:v1.0.0
```

#### 3. Spark Job Fails with S3 Error
**Cause**: Missing credentials or JARs
```bash
# Check API pod has credentials
kubectl exec -n data-processing -l component=api -- env | grep AWS

# Check JAR files exist
kubectl exec -n data-processing -l component=api -- ls -la /app/jars/
```

#### 4. Executor Connection Failed
**Cause**: Driver networking issue
```bash
# Check POD_IP is set
kubectl exec -n data-processing -l component=api -- env | grep POD_IP

# Check driver host in logs
kubectl logs -n data-processing -l component=api --tail=100 | grep "driver host"
```

---

## 🧹 Cleanup

### Full Cleanup
```bash
bash scripts/cleanup.sh
```

### Manual Cleanup
```bash
# Delete namespace (removes all resources)
kubectl delete namespace data-processing

# Remove Docker images
docker rmi data-processing:v1.0.0

# Kill port-forwards
pkill -f "port-forward"

# Stop Minikube (optional)
minikube stop

# Delete Minikube (complete reset)
minikube delete
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Kubernetes (Minikube)                 │
│                                                              │
│  ┌────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   FastAPI      │  │  Spark Master   │  │    MinIO     │ │
│  │   (Driver)     │◄─┤  spark://7077   │  │  S3 Storage  │ │
│  │  Port: 8000    │  │  UI: 8080       │  │  Port: 9000  │ │
│  └────────┬───────┘  └────────┬────────┘  └──────┬───────┘ │
│           │                   │                   │          │
│           │                   ▼                   │          │
│           │          ┌─────────────────┐          │          │
│           │          │  Spark Worker   │          │          │
│           └─────────►│  Executors      │◄─────────┘          │
│                      │  2 cores, 2GB   │  (Read/Write S3)    │
│                      └─────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

### Components

1. **FastAPI (3 replicas)**: REST API, Spark driver
2. **Spark Master (1 replica)**: Cluster coordinator
3. **Spark Worker (1 replica)**: Task executor
4. **MinIO (1 replica)**: S3-compatible storage

---

## 📚 Key Files

| File | Purpose |
|------|---------|
| `scripts/deploy.sh` | Complete deployment automation |
| `scripts/cleanup.sh` | Full cleanup automation |
| `scripts/test.sh` | End-to-end testing |
| `Dockerfile` | Multi-stage Docker image with Spark support |
| `deployment/k8s/base/deployment.yaml` | API deployment with POD_IP |
| `deployment/k8s/base/spark-cluster.yaml` | Spark master + worker |
| `src/data_processing/distributed/spark_engine.py` | Spark session with driver networking |

---

## ✅ Success Criteria

After deployment, you should see:
- ✅ All pods in `Running` state
- ✅ API health check returns `200 OK`
- ✅ Spark Master UI shows 1 active worker
- ✅ MinIO console accessible
- ✅ Test script completes successfully
- ✅ Output files in MinIO bucket

---

## 🎓 Next Steps

1. **Scale workers**: Increase `replicas` in `spark-cluster.yaml`
2. **Add monitoring**: Deploy Prometheus + Grafana
3. **Production setup**: Use AWS S3, EKS, and production credentials
4. **Optimize**: Tune Spark memory, cores, and partitions

---

## 🆘 Support

If issues persist:
1. Check logs for all components
2. Verify Minikube has sufficient resources
3. Ensure Docker image is correctly loaded
4. Review the error descriptions in this guide
