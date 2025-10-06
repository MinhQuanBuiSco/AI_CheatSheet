# Using Spark with Kubernetes Deployment

Complete guide for using Spark distributed processing via the API deployed on Kubernetes.

## Prerequisites

1. **API is running:**
   ```bash
   kubectl get pods -n data-processing
   # Should show: data-processing-api-xxx   1/1   Running
   ```

2. **Port-forward is active:**
   ```bash
   kubectl port-forward -n data-processing svc/data-processing-api 8000:80
   # Keep this running in a separate terminal
   ```

3. **(Optional) Spark cluster deployed:**
   ```bash
   # Using Helm
   helm install spark bitnami/spark -n data-processing

   # OR standalone for testing
   kubectl run spark-master -n data-processing \
     --image=data-processing:v1.0.0 \
     --command -- /opt/spark/bin/spark-class org.apache.spark.deploy.master.Master
   kubectl expose pod spark-master -n data-processing --port=7077 --name=spark-master-svc
   ```

---

## API Endpoints

### 1. Check Spark Status

Check if Spark is available and get cluster information:

```bash
curl http://localhost:8000/spark/status
```

**Response (Spark available):**
```json
{
  "available": true,
  "pyspark_version": "3.5.0",
  "master": "spark://spark-master:7077",
  "message": "Spark is available"
}
```

**Response (Spark not available):**
```json
{
  "available": false,
  "message": "PySpark is not installed"
}
```

---

### 2. Process Data with Spark (Auto Mode)

Automatically chooses local or distributed processing based on file size:

```bash
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/large_dataset.parquet",
    "output_path": "/app/output/processed.parquet",
    "mode": "auto"
  }'
```

**Response:**
```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "accepted",
  "message": "Spark processing job started (mode: auto)",
  "worker_id": "data-processing-api-6898cf4d57-z8zqt"
}
```

**Processing Modes:**
- `auto` - Automatically choose local or Spark based on data size
- `local` - Force single-node processing (uses Polars)
- `spark` - Force distributed Spark processing

---

### 3. Process with Custom Spark Configuration

Full control over Spark cluster resources:

```bash
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/large_dataset.parquet",
    "output_path": "/app/output/spark_result.parquet",
    "mode": "spark",
    "spark_master": "spark://spark-master-svc:7077",
    "executor_memory": "4g",
    "driver_memory": "2g",
    "executor_cores": 2,
    "num_executors": 3,
    "file_type": "parquet"
  }'
```

**Parameters:**
- `input_path` (required) - Path to input file
- `output_path` (required) - Path to output file
- `mode` (optional) - Processing mode: `auto`, `local`, or `spark` (default: `auto`)
- `spark_master` (optional) - Spark master URL (default: `spark://spark-master:7077`)
- `executor_memory` (optional) - Memory per executor (default: `4g`)
- `driver_memory` (optional) - Memory for driver (default: `2g`)
- `executor_cores` (optional) - CPU cores per executor (default: `2`)
- `num_executors` (optional) - Number of executors (default: `2`)
- `file_type` (optional) - Input file type: `parquet`, `csv`, `json` (default: `parquet`)

---

### 4. Process CSV Files

```bash
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/data.csv",
    "output_path": "/app/output/processed.parquet",
    "mode": "spark",
    "file_type": "csv"
  }'
```

---

### 5. Process JSON Files

```bash
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/data.json",
    "output_path": "/app/output/processed.parquet",
    "mode": "spark",
    "file_type": "json"
  }'
```

---

### 6. High-Performance Processing (Large Datasets)

For very large datasets (10M+ records):

```bash
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/massive_dataset.parquet",
    "output_path": "/app/output/processed_massive.parquet",
    "mode": "spark",
    "spark_master": "spark://spark-master-svc:7077",
    "executor_memory": "8g",
    "driver_memory": "4g",
    "executor_cores": 4,
    "num_executors": 10
  }'
```

---

## Complete Workflow Example

### Step 1: Upload Data to Kubernetes

```bash
# Create a temporary pod to upload data
kubectl run data-uploader -n data-processing \
  --image=busybox --restart=Never --command -- sleep 3600

# Wait for pod to be ready
kubectl wait --for=condition=ready pod/data-uploader -n data-processing

# Copy your local file
kubectl cp local_large_dataset.parquet \
  data-processing/data-uploader:/tmp/dataset.parquet

# Clean up uploader pod
kubectl delete pod data-uploader -n data-processing
```

### Step 2: Check Spark Status

```bash
curl http://localhost:8000/spark/status
```

### Step 3: Submit Processing Job

```bash
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/dataset.parquet",
    "output_path": "/app/output/result.parquet",
    "mode": "spark",
    "num_executors": 3
  }'
```

**Save the job_id from the response!**

### Step 4: Monitor Processing

```bash
# Check API logs
kubectl logs -n data-processing -l app=data-processing --tail=100 -f

# Check Spark UI (if deployed)
kubectl port-forward -n data-processing pod/spark-master 8080:8080
open http://localhost:8080
```

### Step 5: Download Results

```bash
# Create download pod
kubectl run data-downloader -n data-processing \
  --image=busybox --restart=Never --command -- sleep 3600

# Copy result file
kubectl cp data-processing/data-downloader:/app/output/result.parquet \
  ./local_result.parquet

# Clean up
kubectl delete pod data-downloader -n data-processing
```

---

## Deploy Spark Cluster on Kubernetes

### Option A: Using Helm (Recommended)

```bash
# Install Helm (if not installed)
brew install helm

# Add Bitnami chart repository
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Install Spark cluster
helm install spark bitnami/spark \
  --namespace data-processing \
  --set master.service.type=ClusterIP \
  --set master.resources.requests.memory=2Gi \
  --set master.resources.requests.cpu=1 \
  --set master.resources.limits.memory=4Gi \
  --set master.resources.limits.cpu=2 \
  --set worker.replicaCount=3 \
  --set worker.resources.requests.memory=4Gi \
  --set worker.resources.requests.cpu=2 \
  --set worker.resources.limits.memory=8Gi \
  --set worker.resources.limits.cpu=4

# Verify installation
kubectl get pods -n data-processing -l app.kubernetes.io/name=spark

# Expected output:
# spark-master-0        1/1     Running   0          2m
# spark-worker-0        1/1     Running   0          2m
# spark-worker-1        1/1     Running   0          2m
# spark-worker-2        1/1     Running   0          2m

# Get Spark master URL
kubectl get svc -n data-processing -l app.kubernetes.io/component=master
# Service: spark-master
# Use: spark://spark-master:7077
```

### Option B: Standalone Deployment

```bash
# Deploy Spark master
kubectl run spark-master -n data-processing \
  --image=data-processing:v1.0.0 \
  --port=7077 \
  --port=8080 \
  --command -- /opt/spark/bin/spark-class org.apache.spark.deploy.master.Master

# Expose Spark master
kubectl expose pod spark-master -n data-processing \
  --port=7077 --target-port=7077 --name=spark-master-svc

# Create Spark master UI service
kubectl expose pod spark-master -n data-processing \
  --port=8080 --target-port=8080 --name=spark-ui

# Deploy Spark workers
kubectl create deployment spark-worker -n data-processing \
  --image=data-processing:v1.0.0 \
  --replicas=3

# Configure workers to connect to master
kubectl set env deployment/spark-worker -n data-processing \
  SPARK_MASTER=spark://spark-master-svc:7077

# Update worker command
kubectl patch deployment spark-worker -n data-processing -p '{
  "spec": {
    "template": {
      "spec": {
        "containers": [{
          "name": "data-processing",
          "command": ["/opt/spark/bin/spark-class"],
          "args": ["org.apache.spark.deploy.worker.Worker", "spark://spark-master-svc:7077"]
        }]
      }
    }
  }
}'

# Verify deployment
kubectl get pods -n data-processing | grep spark
```

### Access Spark Web UI

```bash
# Port-forward Spark master UI
kubectl port-forward -n data-processing pod/spark-master 8080:8080

# Open in browser
open http://localhost:8080

# You'll see:
# - Cluster status
# - Active workers
# - Running/completed jobs
# - Resource usage
```

---

## Monitoring Spark Jobs

### Check API Logs

```bash
# Real-time logs from all API pods
kubectl logs -n data-processing -l app=data-processing --tail=100 -f

# Logs from specific pod
kubectl logs -n data-processing data-processing-api-xxx -f

# Search for Spark-related logs
kubectl logs -n data-processing -l app=data-processing | grep -i spark
```

### Check Spark Master Logs

```bash
# If using Helm
kubectl logs -n data-processing spark-master-0

# If using standalone
kubectl logs -n data-processing spark-master
```

### Check Spark Worker Logs

```bash
# If using Helm
kubectl logs -n data-processing spark-worker-0

# If using standalone
kubectl logs -n data-processing -l app=spark-worker
```

### Access Spark Web UI

```bash
# Port-forward to Spark UI
kubectl port-forward -n data-processing pod/spark-master-0 8080:8080

# Open browser
open http://localhost:8080
```

---

## Performance Tuning

### Small Datasets (< 1GB)

Use local mode (faster for small data):

```bash
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/small.parquet",
    "output_path": "/app/output/result.parquet",
    "mode": "local"
  }'
```

### Medium Datasets (1GB - 10GB)

Use auto mode with moderate resources:

```bash
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/medium.parquet",
    "output_path": "/app/output/result.parquet",
    "mode": "auto",
    "executor_memory": "4g",
    "num_executors": 2
  }'
```

### Large Datasets (> 10GB)

Force Spark mode with high resources:

```bash
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/large.parquet",
    "output_path": "/app/output/result.parquet",
    "mode": "spark",
    "executor_memory": "8g",
    "driver_memory": "4g",
    "executor_cores": 4,
    "num_executors": 10
  }'
```

---

## Troubleshooting

### Issue: "Spark is not available"

```bash
# Check if PySpark is installed in the image
kubectl exec -n data-processing data-processing-api-xxx -- pip list | grep pyspark

# If missing, rebuild image with Spark support
eval $(minikube docker-env)
docker build --target production -t data-processing:v1.0.0 .
kubectl rollout restart deployment/data-processing-api -n data-processing
```

### Issue: "Connection refused to spark-master"

```bash
# Check if Spark master is running
kubectl get pods -n data-processing | grep spark-master

# Check Spark master service
kubectl get svc -n data-processing | grep spark-master

# Test connectivity from API pod
kubectl exec -n data-processing data-processing-api-xxx -- \
  nc -zv spark-master-svc 7077
```

### Issue: Spark jobs failing

```bash
# Check Spark master logs
kubectl logs -n data-processing spark-master-0

# Check worker logs
kubectl logs -n data-processing spark-worker-0

# Check for resource constraints
kubectl top pods -n data-processing
kubectl describe pod -n data-processing spark-worker-0
```

### Issue: Out of memory errors

Increase executor memory:

```bash
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/large.parquet",
    "output_path": "/app/output/result.parquet",
    "executor_memory": "16g",
    "driver_memory": "8g"
  }'
```

---

## Clean Up

### Remove Spark Cluster (Helm)

```bash
helm uninstall spark -n data-processing
```

### Remove Spark Cluster (Standalone)

```bash
kubectl delete deployment spark-worker -n data-processing
kubectl delete pod spark-master -n data-processing
kubectl delete svc spark-master-svc spark-ui -n data-processing
```

### Remove Everything

```bash
kubectl delete namespace data-processing
```

---

## Summary

**Quick Commands:**

```bash
# 1. Deploy Spark cluster
helm install spark bitnami/spark -n data-processing

# 2. Port-forward API
kubectl port-forward -n data-processing svc/data-processing-api 8000:80

# 3. Check Spark status
curl http://localhost:8000/spark/status

# 4. Process data
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{"input_path":"/app/data/file.parquet","output_path":"/app/output/result.parquet","mode":"auto"}'

# 5. Monitor via Spark UI
kubectl port-forward -n data-processing spark-master-0 8080:8080
open http://localhost:8080
```

**API Documentation:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Metrics: http://localhost:8000/metrics
