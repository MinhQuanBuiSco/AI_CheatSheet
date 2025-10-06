# Kubernetes Deployment Guide

Complete guide for deploying the data processing infrastructure on Kubernetes (local with Minikube or production clusters).

## 🚀 Quick Deploy - Local (Minikube)

**For local development with Minikube (recommended for getting started):**

```bash
# 1. Start Minikube
minikube start --cpus=2 --memory=2048

# 2. Build image in Minikube's Docker
eval $(minikube docker-env)
docker build --target production -t data-processing:v1.0.0 .

# 3. Create secrets
kubectl create namespace data-processing
kubectl create secret generic data-processing-secrets \
  --namespace=data-processing \
  --from-literal=postgres_host='localhost' \
  --from-literal=postgres_password='dev-password' \
  --from-literal=redis_url='redis://localhost:6379' \
  --from-literal=encryption_key="$(openssl rand -base64 32)"

# 4. Deploy
kubectl apply -k deployment/k8s/base/

# 5. Access API
kubectl port-forward -n data-processing svc/data-processing-api 8000:80
# Open: http://localhost:8000/docs
```

## Quick Deploy - Production (Cloud)

**For production deployment to cloud Kubernetes:**

```bash
# 1. Build and push Docker image
docker build --target production -t your-registry/data-processing:v1.0.0 .
docker push your-registry/data-processing:v1.0.0

# 2. Update deployment/k8s/base/deployment.yaml
# Change image: data-processing:v1.0.0 to your-registry/data-processing:v1.0.0
# Change imagePullPolicy: Never to Always

# 3. Deploy
kubectl apply -k deployment/k8s/base/
```

## Table of Contents

- [Local Deployment (Minikube)](#local-deployment-minikube)
- [Production Deployment (Cloud)](#production-deployment-cloud)
- [Prerequisites](#prerequisites)
- [Resource Configuration](#resource-configuration)
- [Storage Configuration](#storage-configuration)
- [Monitoring & Observability](#monitoring--observability)
- [Update & Rollback](#update--rollback)
- [Production Best Practices](#production-best-practices)
- [Troubleshooting](#troubleshooting)

---

## Local Deployment (Minikube)

### Step 1: Install Minikube

```bash
# Install minikube (if not already installed)
brew install minikube

# Verify installation
minikube version
```

### Step 2: Start Minikube Cluster

```bash
# Start with recommended resources
minikube start --cpus=4 --memory=8192 --disk-size=50g

# Enable metrics-server for auto-scaling
minikube addons enable metrics-server

# Verify cluster is running
kubectl cluster-info
kubectl get nodes
```

### Step 3: Build Docker Image in Minikube

**Important:** Build the image inside Minikube's Docker daemon (no push needed!)

```bash
# Point your shell to Minikube's Docker
eval $(minikube docker-env)

# Build the production image
docker build --target production -t data-processing:v1.0.0 .

# Verify image exists
docker images | grep data-processing
```

### Step 4: Update Deployment for Local Use

The deployment is already configured for local use with:
- `imagePullPolicy: Never` (uses local image)
- `storageClassName: standard` (Minikube's default)
- No security context (avoids permission issues)

No changes needed!

### Step 5: Create Secrets

```bash
# Create namespace
kubectl create namespace data-processing

# Create secrets
kubectl create secret generic data-processing-secrets \
  --namespace=data-processing \
  --from-literal=postgres_host='localhost' \
  --from-literal=postgres_password='local-dev-password' \
  --from-literal=redis_url='redis://localhost:6379' \
  --from-literal=aws_access_key_id='not-needed' \
  --from-literal=aws_secret_access_key='not-needed' \
  --from-literal=encryption_key="$(openssl rand -base64 32)"
```

### Step 6: Deploy All Resources

```bash
# Deploy everything
kubectl apply -k deployment/k8s/base/

# Watch pods come up
kubectl get pods -n data-processing -w

# Wait for all pods to be Running (1/1)
# Press Ctrl+C when done
```

Expected output:
```
NAME                                   READY   STATUS    RESTARTS   AGE
data-processing-api-xxxxxxxxxx-xxxxx   1/1     Running   0          30s
data-processing-api-xxxxxxxxxx-xxxxx   1/1     Running   0          30s
data-processing-api-xxxxxxxxxx-xxxxx   1/1     Running   0          30s
```

### Step 7: Access the API

**Option A: Port Forward (Recommended)**

```bash
# Forward local port 8000 to service
kubectl port-forward -n data-processing svc/data-processing-api 8000:80

# Keep this terminal open
# Access at: http://localhost:8000
```

In a new terminal:
```bash
# Test health endpoint
curl http://localhost:8000/health

# Open API documentation in browser
open http://localhost:8000/docs

# Check metrics
curl http://localhost:8000/metrics
```

**Option B: Minikube Service**

```bash
# Get service URL and open in browser
minikube service data-processing-api -n data-processing

# Or just get the URL
minikube service data-processing-api -n data-processing --url
```

### Step 8: Test Processing

**Basic Processing (Single-node):**

```bash
# With port-forward running, test the API
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/sample.parquet",
    "output_path": "/app/output/processed.parquet",
    "chunk_size": 10000,
    "enable_pii": true
  }'
```

**Spark Distributed Processing:**

```bash
# Check if Spark is available
curl http://localhost:8000/spark/status

# Process with Spark (auto-mode: chooses local or distributed)
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/large_dataset.parquet",
    "output_path": "/app/output/processed_spark.parquet",
    "mode": "auto",
    "file_type": "parquet"
  }'

# Force Spark distributed mode
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/large_dataset.parquet",
    "output_path": "/app/output/processed_spark.parquet",
    "mode": "spark",
    "spark_master": "spark://spark-master:7077",
    "executor_memory": "4g",
    "driver_memory": "2g",
    "executor_cores": 2,
    "num_executors": 2
  }'

# Response example:
# {
#   "job_id": "abc123...",
#   "status": "accepted",
#   "message": "Spark processing job started (mode: auto)",
#   "worker_id": "data-processing-api-xxx"
# }
```

### Step 9: Using Spark in Kubernetes

To enable Spark distributed processing, you need to deploy a Spark cluster alongside your API:

**Option A: Deploy Spark with Helm (Recommended)**

```bash
# Add Bitnami Helm repo
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Install Spark cluster in the same namespace
helm install spark bitnami/spark \
  --namespace data-processing \
  --set master.service.type=ClusterIP \
  --set master.resources.requests.memory=2Gi \
  --set master.resources.requests.cpu=1 \
  --set worker.replicaCount=3 \
  --set worker.resources.requests.memory=4Gi \
  --set worker.resources.requests.cpu=2

# Verify Spark cluster
kubectl get pods -n data-processing -l app.kubernetes.io/name=spark

# Check Spark master URL
kubectl get svc -n data-processing -l app.kubernetes.io/component=master
# URL will be: spark://spark-master:7077
```

**Option B: Standalone Spark (Minikube)**

For local testing, use the existing spark-worker image:

```bash
# Deploy Spark master
kubectl run spark-master -n data-processing \
  --image=data-processing:v1.0.0 \
  --env="SPARK_MODE=master" \
  --port=7077 \
  --command -- /opt/spark/bin/spark-class org.apache.spark.deploy.master.Master

# Expose Spark master
kubectl expose pod spark-master -n data-processing \
  --port=7077 --target-port=7077 --name=spark-master-svc

# Deploy Spark workers (3 replicas)
kubectl create deployment spark-worker -n data-processing \
  --image=data-processing:v1.0.0 \
  --replicas=3 \
  -- /opt/spark/bin/spark-class org.apache.spark.deploy.worker.Worker spark://spark-master-svc:7077

# Verify
kubectl get pods -n data-processing | grep spark
```

**Test Spark Processing:**

```bash
# Port-forward API
kubectl port-forward -n data-processing svc/data-processing-api 8000:80

# In another terminal, test Spark
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/sample.parquet",
    "output_path": "/app/output/spark_output.parquet",
    "mode": "spark",
    "spark_master": "spark://spark-master-svc:7077",
    "executor_memory": "2g",
    "num_executors": 2
  }'

# Check job status
curl http://localhost:8000/spark/status
```

**Monitor Spark Jobs:**

```bash
# Access Spark Web UI
kubectl port-forward -n data-processing pod/spark-master 8080:8080

# Open in browser
open http://localhost:8080
```

### Useful Minikube Commands

```bash
# Check cluster status
minikube status

# Open Kubernetes dashboard
minikube dashboard

# SSH into minikube VM
minikube ssh

# View minikube logs
minikube logs

# Check resource usage
kubectl top nodes
kubectl top pods -n data-processing

# Stop cluster (preserves state)
minikube stop

# Start again
minikube start

# Delete cluster completely
minikube delete
```

### Clean Up Local Deployment

```bash
# Delete all resources
kubectl delete -k deployment/k8s/base/

# Or delete namespace (faster)
kubectl delete namespace data-processing

# Stop minikube
minikube stop

# Delete minikube cluster
minikube delete
```

---

## Production Deployment (Cloud)

For deploying to AWS EKS, GKE, AKS, or other cloud Kubernetes clusters.

### Prerequisites

- **Kubernetes cluster**: AWS EKS, GKE, AKS, or similar
- **kubectl**: Configured to access your cluster
- **Docker registry**: Docker Hub, ECR, GCR, or ACR
- **Storage class**: With `ReadWriteMany` support (EFS, GCE Persistent Disk, Azure Files)

### Step 1: Build and Push Docker Image

```bash
# Build production image with specific tag
docker build --target production -t your-registry/data-processing:v1.0.0 .

# Example for Docker Hub (replace 'mqxm' with your username)
docker build --target production -t mqxm/data-processing:v1.0.0 .
docker push mqxm/data-processing:v1.0.0

# Example for AWS ECR
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 123456789.dkr.ecr.us-west-2.amazonaws.com
docker build --target production -t 123456789.dkr.ecr.us-west-2.amazonaws.com/data-processing:v1.0.0 .
docker push 123456789.dkr.ecr.us-west-2.amazonaws.com/data-processing:v1.0.0

# Example for Google GCR
docker build --target production -t gcr.io/your-project/data-processing:v1.0.0 .
docker push gcr.io/your-project/data-processing:v1.0.0
```

### Step 2: Update Deployment for Production

Edit `deployment/k8s/base/deployment.yaml`:

```bash
# Change image reference
sed -i 's|image: data-processing:v1.0.0|image: your-registry/data-processing:v1.0.0|g' \
  deployment/k8s/base/deployment.yaml

# Change imagePullPolicy to Always (pull from registry)
sed -i 's|imagePullPolicy: Never|imagePullPolicy: Always|g' \
  deployment/k8s/base/deployment.yaml

# Add security context back for production
# (Edit deployment.yaml manually to add runAsNonRoot: true, runAsUser: 1000)
```

### Step 3: Configure Secrets

**⚠️ IMPORTANT: Never commit real secrets to Git!**

**Option A: Create from command line**

```bash
kubectl create namespace data-processing

kubectl create secret generic data-processing-secrets \
  --namespace=data-processing \
  --from-literal=postgres_host='postgres.example.com' \
  --from-literal=postgres_password='YourSecurePassword123!' \
  --from-literal=redis_url='redis://redis.example.com:6379' \
  --from-literal=aws_access_key_id='AKIAIOSFODNN7EXAMPLE' \
  --from-literal=aws_secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY' \
  --from-literal=encryption_key="$(openssl rand -base64 32)"
```

**Option B: Create from file (don't commit!)**

```bash
cat > /tmp/secret-production.yaml <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: data-processing-secrets
  namespace: data-processing
type: Opaque
stringData:
  postgres_host: "postgres.example.com"
  postgres_password: "YourSecurePassword123!"
  redis_url: "redis://redis.example.com:6379"
  aws_access_key_id: "AKIAIOSFODNN7EXAMPLE"
  aws_secret_access_key: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
  encryption_key: "$(openssl rand -base64 32)"
EOF

kubectl apply -f /tmp/secret-production.yaml
rm /tmp/secret-production.yaml  # Clean up immediately
```

**Option C: Use Sealed Secrets (Recommended for GitOps)**

```bash
# Install sealed-secrets controller
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/controller.yaml

# Install kubeseal CLI
brew install kubeseal

# Create sealed secret
kubectl create secret generic data-processing-secrets \
  --namespace=data-processing \
  --from-literal=postgres_password='YourSecurePassword123!' \
  --dry-run=client -o yaml | \
  kubeseal -o yaml > deployment/k8s/base/sealed-secret.yaml

# Now you can commit sealed-secret.yaml safely
```

### Step 4: Configure Storage (If Needed)

Check available storage classes:

```bash
kubectl get storageclass
```

If `fast-ssd` doesn't exist, update `deployment/k8s/base/pvc.yaml`:

```bash
# Replace 'fast-ssd' with your available storage class
sed -i '' 's|storageClassName: fast-ssd|storageClassName: standard|g' \
  deployment/k8s/base/pvc.yaml
```

Or create a storage class:

```bash
cat <<EOF | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: kubernetes.io/aws-ebs  # Or gce-pd, azure-disk, etc.
parameters:
  type: gp3
  iops: "3000"
  throughput: "125"
EOF
```

### Step 5: Deploy All Resources

```bash
# Deploy everything with kustomize
kubectl apply -k deployment/k8s/base/
```

This creates:
- ✅ Namespace (`data-processing`)
- ✅ ServiceAccount (RBAC)
- ✅ ConfigMap (application configuration)
- ✅ Secret (credentials) - if using file method
- ✅ PersistentVolumeClaim (100Gi data + 500Gi output)
- ✅ Deployment (3 replicas with rolling update)
- ✅ Service (ClusterIP + Headless for StatefulSet-like features)
- ✅ HorizontalPodAutoscaler (auto-scale 3-20 pods)
- ✅ CronJob (scheduled processing tasks)

### Step 6: Verify Deployment

```bash
# Check all resources
kubectl get all -n data-processing

# Expected output:
# NAME                                      READY   STATUS    RESTARTS   AGE
# pod/data-processing-api-xxxxxxxxx-xxxxx   1/1     Running   0          2m
# pod/data-processing-api-xxxxxxxxx-xxxxx   1/1     Running   0          2m
# pod/data-processing-api-xxxxxxxxx-xxxxx   1/1     Running   0          2m
#
# NAME                              TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE
# service/data-processing-api       ClusterIP   10.96.xxx.xxx   <none>        80/TCP     2m
#
# NAME                                  READY   UP-TO-DATE   AVAILABLE   AGE
# deployment.apps/data-processing-api   3/3     3            3           2m

# Check pod status in detail
kubectl get pods -n data-processing -o wide

# Check logs from all pods
kubectl logs -n data-processing -l app=data-processing --tail=50

# Check HPA status
kubectl get hpa -n data-processing
# Should show current CPU/memory usage and scaling status
```

### Step 7: Expose Service

Choose the method that fits your environment:

#### Option A: LoadBalancer (Cloud Environments)

```bash
kubectl patch svc data-processing-api -n data-processing -p '{"spec":{"type":"LoadBalancer"}}'

# Wait for external IP
kubectl get svc data-processing-api -n data-processing -w

# Access via external IP
EXTERNAL_IP=$(kubectl get svc data-processing-api -n data-processing -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
curl http://$EXTERNAL_IP/health
```

#### Option B: NodePort (On-Premises/Local)

```bash
kubectl patch svc data-processing-api -n data-processing -p '{"spec":{"type":"NodePort"}}'

# Get node port
NODE_PORT=$(kubectl get svc data-processing-api -n data-processing -o jsonpath='{.spec.ports[0].nodePort}')

# Access via any node IP
NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
curl http://$NODE_IP:$NODE_PORT/health
```

#### Option C: Ingress (Recommended for Production)

```bash
# Prerequisites: Install nginx-ingress controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.9.0/deploy/static/provider/cloud/deploy.yaml

# Create ingress resource
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: data-processing-ingress
  namespace: data-processing
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: "letsencrypt-prod"  # If using cert-manager
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - data-processing.example.com
    secretName: data-processing-tls
  rules:
  - host: data-processing.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: data-processing-api
            port:
              number: 80
EOF

# Access via domain
curl https://data-processing.example.com/health
```

#### Option D: Port Forward (Development/Testing)

```bash
# Forward local port 8000 to service
kubectl port-forward -n data-processing svc/data-processing-api 8000:80

# Access locally
curl http://localhost:8000/health
curl http://localhost:8000/docs  # API documentation
```

### Step 8: Test the Deployment

```bash
# Health check
curl http://localhost:8000/health
# Expected: {"status":"healthy"}

# Readiness check
curl http://localhost:8000/ready
# Expected: {"status":"ready"}

# API documentation (Swagger UI)
open http://localhost:8000/docs

# Prometheus metrics
curl http://localhost:8000/metrics

# Process a file via API
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/sample.parquet",
    "output_path": "/app/output/processed.parquet",
    "chunk_size": 10000,
    "enable_pii_detection": true
  }'

# Check processing status
curl http://localhost:8000/status
```

---

## Resource Configuration

### Current Settings

From `deployment/k8s/base/deployment.yaml`:

```yaml
resources:
  requests:
    cpu: "500m"      # 0.5 CPU cores (guaranteed)
    memory: "1Gi"    # 1GB RAM (guaranteed)
  limits:
    cpu: "2000m"     # 2 CPU cores (maximum)
    memory: "4Gi"    # 4GB RAM (maximum)
```

### Auto-Scaling Configuration

From `deployment/k8s/base/hpa.yaml`:

```yaml
minReplicas: 3        # Minimum pods
maxReplicas: 20       # Maximum pods
metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        averageUtilization: 70    # Scale up when CPU > 70%
  - type: Resource
    resource:
      name: memory
      target:
        averageUtilization: 80    # Scale up when memory > 80%
```

### Adjust Resources for Your Workload

**Light workload (< 100K records/day):**

```bash
kubectl patch deployment data-processing-api -n data-processing -p '{
  "spec": {
    "template": {
      "spec": {
        "containers": [{
          "name": "api",
          "resources": {
            "requests": {"cpu": "250m", "memory": "512Mi"},
            "limits": {"cpu": "1000m", "memory": "2Gi"}
          }
        }]
      }
    }
  }
}'

kubectl patch hpa data-processing-api-hpa -n data-processing -p '{
  "spec": {"minReplicas": 2, "maxReplicas": 10}
}'
```

**Heavy workload (> 10M records/day):**

```bash
kubectl patch deployment data-processing-api -n data-processing -p '{
  "spec": {
    "template": {
      "spec": {
        "containers": [{
          "name": "api",
          "resources": {
            "requests": {"cpu": "2000m", "memory": "4Gi"},
            "limits": {"cpu": "8000m", "memory": "16Gi"}
          }
        }]
      }
    }
  }
}'

kubectl patch hpa data-processing-api-hpa -n data-processing -p '{
  "spec": {"minReplicas": 5, "maxReplicas": 50}
}'
```

**Manual scaling (disable HPA):**

```bash
# Delete HPA
kubectl delete hpa data-processing-api-hpa -n data-processing

# Scale manually
kubectl scale deployment data-processing-api -n data-processing --replicas=10
```

---

## Storage Configuration

### Persistent Volume Claims

From `deployment/k8s/base/pvc.yaml`:

```yaml
# Data PVC (read-only, for input files)
data-processing-data-pvc:
  accessModes: ReadOnlyMany
  storage: 100Gi
  storageClass: fast-ssd

# Output PVC (read-write, for results)
data-processing-output-pvc:
  accessModes: ReadWriteMany
  storage: 500Gi
  storageClass: fast-ssd
```

### Upload Data to PVC

**Method 1: Using kubectl cp**

```bash
# Create a temporary pod with PVC mounted
kubectl run -n data-processing data-uploader \
  --image=busybox \
  --restart=Never \
  --overrides='
{
  "spec": {
    "containers": [{
      "name": "uploader",
      "image": "busybox",
      "command": ["sleep", "3600"],
      "volumeMounts": [{
        "name": "data",
        "mountPath": "/data"
      }]
    }],
    "volumes": [{
      "name": "data",
      "persistentVolumeClaim": {
        "claimName": "data-processing-data-pvc"
      }
    }]
  }
}'

# Wait for pod to be ready
kubectl wait --for=condition=ready pod/data-uploader -n data-processing

# Copy files
kubectl cp local-file.parquet data-processing/data-uploader:/data/
kubectl cp demo_data/ data-processing/data-uploader:/data/demo_data/

# Verify
kubectl exec -n data-processing data-uploader -- ls -lh /data

# Clean up
kubectl delete pod data-uploader -n data-processing
```

**Method 2: Using a Job**

```bash
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: data-upload
  namespace: data-processing
spec:
  template:
    spec:
      containers:
      - name: uploader
        image: amazon/aws-cli:latest
        command:
        - /bin/sh
        - -c
        - |
          aws s3 sync s3://your-bucket/data/ /data/ --region us-west-2
        volumeMounts:
        - name: data
          mountPath: /data
        env:
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: data-processing-secrets
              key: aws_access_key_id
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: data-processing-secrets
              key: aws_secret_access_key
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: data-processing-data-pvc
      restartPolicy: OnFailure
EOF
```

### Resize PVC

```bash
# Check if storageClass allows volume expansion
kubectl get storageclass fast-ssd -o jsonpath='{.allowVolumeExpansion}'

# Edit PVC to request more storage
kubectl patch pvc data-processing-output-pvc -n data-processing -p '{"spec":{"resources":{"requests":{"storage":"1Ti"}}}}'

# Monitor resize
kubectl get pvc data-processing-output-pvc -n data-processing -w
```

---

## Monitoring & Observability

### View Logs

```bash
# All API pods (live tail)
kubectl logs -n data-processing -l component=api --tail=100 -f

# Specific pod
kubectl logs -n data-processing data-processing-api-xxx -f

# Previous crashed pod (for debugging)
kubectl logs -n data-processing data-processing-api-xxx --previous

# All containers in a pod
kubectl logs -n data-processing data-processing-api-xxx --all-containers=true

# Save logs to file
kubectl logs -n data-processing -l component=api --tail=1000 > api-logs.txt
```

### Metrics & Prometheus

The deployment includes Prometheus annotations:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"
  prometheus.io/path: "/metrics"
```

**View metrics directly:**

```bash
kubectl exec -n data-processing data-processing-api-xxx -- curl localhost:8000/metrics
```

**Setup Prometheus (if not already deployed):**

```bash
# Add Prometheus Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install Prometheus
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues=false \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false

# Port-forward to Prometheus UI
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090

# Port-forward to Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
# Default credentials: admin / prom-operator
```

### Debug Pod Issues

```bash
# Describe pod (view events, conditions, etc.)
kubectl describe pod -n data-processing data-processing-api-xxx

# Get pod YAML
kubectl get pod -n data-processing data-processing-api-xxx -o yaml

# Check resource usage
kubectl top pod -n data-processing

# Check node resource usage
kubectl top nodes

# Execute command in pod
kubectl exec -n data-processing data-processing-api-xxx -- ls -la /app/data

# Interactive shell
kubectl exec -it -n data-processing data-processing-api-xxx -- /bin/bash

# Check environment variables
kubectl exec -n data-processing data-processing-api-xxx -- env | sort

# Test network connectivity
kubectl exec -n data-processing data-processing-api-xxx -- curl http://postgres:5432
kubectl exec -n data-processing data-processing-api-xxx -- nslookup postgres
```

### Health Checks Configuration

From `deployment/k8s/base/deployment.yaml`:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30    # Wait 30s before first check
  periodSeconds: 10          # Check every 10s
  timeoutSeconds: 5          # Timeout after 5s
  failureThreshold: 3        # Restart after 3 failures

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 10    # Wait 10s before first check
  periodSeconds: 5           # Check every 5s
  timeoutSeconds: 3          # Timeout after 3s
  failureThreshold: 3        # Remove from service after 3 failures
```

---

## Update & Rollback

### Rolling Update

```bash
# Update image to new version
kubectl set image deployment/data-processing-api -n data-processing \
  api=your-registry/data-processing:v2.0.0

# Watch rollout progress
kubectl rollout status deployment/data-processing-api -n data-processing

# View rollout history
kubectl rollout history deployment/data-processing-api -n data-processing

# Pause rollout (if issues detected)
kubectl rollout pause deployment/data-processing-api -n data-processing

# Resume rollout
kubectl rollout resume deployment/data-processing-api -n data-processing
```

### Rollback

```bash
# Rollback to previous version
kubectl rollout undo deployment/data-processing-api -n data-processing

# Rollback to specific revision
kubectl rollout history deployment/data-processing-api -n data-processing
kubectl rollout undo deployment/data-processing-api -n data-processing --to-revision=3
```

### Update Configuration

```bash
# Edit ConfigMap
kubectl edit configmap data-processing-config -n data-processing

# Or patch specific values
kubectl patch configmap data-processing-config -n data-processing -p '{
  "data": {
    "chunk_size": "20000",
    "num_workers": "20"
  }
}'

# Restart pods to pick up changes
kubectl rollout restart deployment/data-processing-api -n data-processing
```

### Update Secrets

```bash
# Update secret value
kubectl patch secret data-processing-secrets -n data-processing -p '{
  "stringData": {
    "postgres_password": "NewSecurePassword456!"
  }
}'

# Or edit interactively
kubectl edit secret data-processing-secrets -n data-processing

# Restart pods to use new secret
kubectl rollout restart deployment/data-processing-api -n data-processing
```

---

## Production Best Practices

### 1. Use Specific Image Tags

❌ **Don't:**
```yaml
image: data-processing:latest
```

✅ **Do:**
```yaml
image: your-registry/data-processing:v1.2.3
```

### 2. Implement Pod Disruption Budgets

```bash
cat <<EOF | kubectl apply -f -
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: data-processing-api-pdb
  namespace: data-processing
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: data-processing
      component: api
EOF
```

### 3. Enable Network Policies

```bash
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: data-processing-api-netpol
  namespace: data-processing
spec:
  podSelector:
    matchLabels:
      app: data-processing
      component: api
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 5432  # PostgreSQL
    - protocol: TCP
      port: 6379  # Redis
EOF
```

### 4. Use Resource Quotas

```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ResourceQuota
metadata:
  name: data-processing-quota
  namespace: data-processing
spec:
  hard:
    requests.cpu: "50"
    requests.memory: "100Gi"
    limits.cpu: "100"
    limits.memory: "200Gi"
    persistentvolumeclaims: "10"
EOF
```

### 5. Backup Strategy

```bash
# Backup all manifests
kubectl get all,configmap,secret,pvc,hpa -n data-processing -o yaml > backup.yaml

# Backup PVC data (using Velero)
velero backup create data-processing-backup \
  --include-namespaces data-processing \
  --storage-location default

# Or use snapshot (if supported by storage class)
kubectl create -f - <<EOF
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: data-pvc-snapshot
  namespace: data-processing
spec:
  volumeSnapshotClassName: csi-snapclass
  source:
    persistentVolumeClaimName: data-processing-output-pvc
EOF
```

### 6. Security Scanning

```bash
# Scan Docker image for vulnerabilities
docker scan your-registry/data-processing:v1.0.0

# Or use Trivy
trivy image your-registry/data-processing:v1.0.0

# Scan Kubernetes manifests
kubesec scan deployment/k8s/base/deployment.yaml
```

### 7. Enable Audit Logging

Configure your cluster to log API server events for compliance.

### 8. Use GitOps

Consider using ArgoCD or Flux for declarative deployments:

```bash
# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Create application
cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: data-processing
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/your-org/data-processing
    targetRevision: main
    path: deployment/k8s/base
  destination:
    server: https://kubernetes.default.svc
    namespace: data-processing
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
EOF
```

---

## Troubleshooting

### Local Deployment (Minikube) Issues

**Issue: "Error loading ASGI app. Could not import module"**

This means uvicorn can't find the Python module. Solution:

```bash
# 1. Make sure you built with --target production
eval $(minikube docker-env)
docker build --target production -t data-processing:v1.0.0 .

# 2. Verify the image
docker images | grep data-processing

# 3. Restart deployment
kubectl rollout restart deployment/data-processing-api -n data-processing
```

**Issue: Pods in CrashLoopBackOff with "Connection refused" on port 8000**

The app is running as Spark worker instead of the API. Solution:

```bash
# Rebuild targeting the production stage (not spark-worker)
eval $(minikube docker-env)
docker build --target production -t data-processing:v1.0.0 .

# Restart pods
kubectl delete pods -n data-processing -l app=data-processing
```

**Issue: "The connection to the server localhost:8080 was refused"**

Minikube isn't running. Solution:

```bash
# Start minikube
minikube start --cpus=4 --memory=8192

# Verify
kubectl get nodes
```

**Issue: Pods stuck in "Pending" state**

PVC can't bind or insufficient resources. Solution:

```bash
# Check PVC status
kubectl get pvc -n data-processing

# If storage class issue, PVCs are already configured for 'standard'
# Check if minikube has enough resources
minikube status
minikube addons list

# If needed, delete and restart minikube with more resources
minikube delete
minikube start --cpus=4 --memory=8192 --disk-size=50g
```

**Issue: "imagePullBackOff: image not found"**

You forgot to build in minikube's docker. Solution:

```bash
# Switch to minikube's docker
eval $(minikube docker-env)

# Rebuild
docker build --target production -t data-processing:v1.0.0 .

# Verify in minikube's docker
docker images | grep data-processing
```

**Issue: Port-forward shows "connection refused"**

App isn't running inside pods. Solution:

```bash
# Check pod logs
kubectl logs -n data-processing -l app=data-processing

# Check if pods are actually running
kubectl get pods -n data-processing

# If pods show 0/1, check logs for errors
kubectl describe pod -n data-processing <pod-name>
```

**Issue: Minikube service command gives "no node port"**

Service is ClusterIP (not exposed). This is normal. Solution:

```bash
# Use port-forward instead (recommended)
kubectl port-forward -n data-processing svc/data-processing-api 8000:80

# Or change to NodePort
kubectl patch svc data-processing-api -n data-processing -p '{"spec":{"type":"NodePort"}}'
minikube service data-processing-api -n data-processing
```

---

### Production Deployment Issues

**Issue: ImagePullBackOff**

```bash
# Check image pull errors
kubectl describe pod -n data-processing <pod-name> | grep -A 10 Events

# Common fixes:
# 1. Verify image exists
docker pull your-registry/data-processing:v1.0.0

# 2. Create image pull secret (for private registries)
kubectl create secret docker-registry regcred \
  --docker-server=your-registry.com \
  --docker-username=your-username \
  --docker-password=your-password \
  --docker-email=your-email@example.com \
  -n data-processing

# 3. Add to deployment
kubectl patch deployment data-processing-api -n data-processing -p '{
  "spec": {
    "template": {
      "spec": {
        "imagePullSecrets": [{"name": "regcred"}]
      }
    }
  }
}'
```

**Issue: CrashLoopBackOff**

```bash
# Check logs
kubectl logs -n data-processing <pod-name> --previous

# Common causes:
# - Application error (check logs)
# - Missing environment variables
# - Failed health checks (increase initialDelaySeconds)
# - Insufficient resources

# Increase resources if OOMKilled
kubectl get pod -n data-processing <pod-name> -o jsonpath='{.status.containerStatuses[0].lastState}'
```

**Issue: Pending State**

```bash
# Check why pod is pending
kubectl describe pod -n data-processing <pod-name>

# Common causes:
# - Insufficient resources in cluster
# - PVC not bound
# - Node selector/affinity not matching

# Check node resources
kubectl describe nodes | grep -A 5 "Allocated resources"

# Check PVC status
kubectl get pvc -n data-processing
```

### PVC Not Binding

```bash
# Check PVC status
kubectl describe pvc data-processing-data-pvc -n data-processing

# Check if storageClass exists
kubectl get storageclass

# If 'fast-ssd' doesn't exist, update PVC
kubectl patch pvc data-processing-data-pvc -n data-processing -p '{
  "spec": {
    "storageClassName": "standard"
  }
}'
```

### Service Not Accessible

```bash
# Check service
kubectl get svc -n data-processing
kubectl describe svc data-processing-api -n data-processing

# Check endpoints (should list pod IPs)
kubectl get endpoints data-processing-api -n data-processing

# If no endpoints, check pod labels match service selector
kubectl get pods -n data-processing --show-labels
kubectl get svc data-processing-api -n data-processing -o yaml | grep -A 5 selector

# Test from within cluster
kubectl run -n data-processing test-pod --image=curlimages/curl:latest --rm -it --restart=Never -- \
  curl http://data-processing-api/health
```

### HPA Not Scaling

```bash
# Check HPA status
kubectl get hpa -n data-processing
kubectl describe hpa data-processing-api-hpa -n data-processing

# Check if metrics-server is running
kubectl get deployment metrics-server -n kube-system

# Check pod metrics
kubectl top pod -n data-processing

# If metrics show <unknown>, install metrics-server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

### High Memory Usage

```bash
# Check memory usage
kubectl top pod -n data-processing

# Increase memory limits
kubectl patch deployment data-processing-api -n data-processing -p '{
  "spec": {
    "template": {
      "spec": {
        "containers": [{
          "name": "api",
          "resources": {
            "limits": {"memory": "8Gi"}
          }
        }]
      }
    }
  }
}'

# Or reduce chunk_size in ConfigMap
kubectl patch configmap data-processing-config -n data-processing -p '{
  "data": {"chunk_size": "5000"}
}'
```

### DNS Resolution Issues

```bash
# Test DNS from pod
kubectl exec -n data-processing <pod-name> -- nslookup kubernetes.default

# Check CoreDNS
kubectl get pods -n kube-system -l k8s-app=kube-dns

# Check CoreDNS logs
kubectl logs -n kube-system -l k8s-app=kube-dns
```

---

## Clean Up

### Delete Everything

```bash
# Delete all resources using kustomize
kubectl delete -k deployment/k8s/base/

# Or delete namespace (removes everything inside)
kubectl delete namespace data-processing
```

### Delete Specific Resources

```bash
# Delete deployment
kubectl delete deployment data-processing-api -n data-processing

# Delete service
kubectl delete svc data-processing-api -n data-processing

# Delete HPA
kubectl delete hpa data-processing-api-hpa -n data-processing

# Delete PVC (WARNING: This deletes data!)
kubectl delete pvc data-processing-data-pvc data-processing-output-pvc -n data-processing
```

### Preserve Data

```bash
# Delete everything except PVCs
kubectl delete deployment,svc,hpa,configmap,secret -n data-processing --all

# PVCs remain for later use
kubectl get pvc -n data-processing
```

---

## Advanced Topics

### Multi-Environment Setup

```
deployment/k8s/
├── base/              # Common resources
├── overlays/
│   ├── dev/           # Development overrides
│   ├── staging/       # Staging overrides
│   └── production/    # Production overrides
```

**Deploy to different environments:**

```bash
# Development
kubectl apply -k deployment/k8s/overlays/dev/

# Production
kubectl apply -k deployment/k8s/overlays/production/
```

### Blue-Green Deployment

```bash
# Deploy green version
kubectl apply -f deployment-green.yaml

# Test green version
kubectl port-forward deployment/data-processing-api-green 8001:8000

# Switch traffic
kubectl patch svc data-processing-api -p '{"spec":{"selector":{"version":"green"}}}'

# Rollback if needed
kubectl patch svc data-processing-api -p '{"spec":{"selector":{"version":"blue"}}}'
```

### Canary Deployment

Use Istio, Linkerd, or Flagger for progressive traffic shifting.

---

## Support

For issues or questions:

1. Check logs: `kubectl logs -n data-processing -l app=data-processing`
2. Review events: `kubectl get events -n data-processing --sort-by='.lastTimestamp'`
3. Consult documentation: See `README.md`, `ARCHITECTURE.md`
4. Open issue: GitHub repository

---

## Summary

You now have a production-grade Kubernetes deployment with:

✅ High availability (3+ replicas)
✅ Auto-scaling (HPA based on CPU/memory)
✅ Rolling updates with zero downtime
✅ Health checks (liveness + readiness)
✅ Resource management (requests + limits)
✅ Persistent storage (100Gi data + 500Gi output)
✅ Security (non-root user, secrets, RBAC)
✅ Monitoring (Prometheus annotations)
✅ Load balancing (service + optional ingress)

**Next steps:**
- Set up monitoring (Prometheus + Grafana)
- Configure ingress with TLS
- Implement backup strategy
- Enable GitOps with ArgoCD/Flux
- Add alerting rules

---

## Quick Reference

### Local Deployment (Copy-Paste)

```bash
# Complete local deployment in one go
minikube start --cpus=4 --memory=8192 && \
minikube addons enable metrics-server && \
eval $(minikube docker-env) && \
docker build --target production -t data-processing:v1.0.0 . && \
kubectl create namespace data-processing && \
kubectl create secret generic data-processing-secrets \
  --namespace=data-processing \
  --from-literal=postgres_host='localhost' \
  --from-literal=postgres_password='dev' \
  --from-literal=redis_url='redis://localhost:6379' \
  --from-literal=encryption_key="$(openssl rand -base64 32)" && \
kubectl apply -k deployment/k8s/base/ && \
echo "Waiting for pods to start..." && \
kubectl wait --for=condition=ready pod -l app=data-processing -n data-processing --timeout=120s && \
echo "✅ Deployment complete! Run: kubectl port-forward -n data-processing svc/data-processing-api 8000:80"
```

### Useful Commands

```bash
# Check status
kubectl get pods -n data-processing

# View logs
kubectl logs -n data-processing -l app=data-processing --tail=50 -f

# Access API
kubectl port-forward -n data-processing svc/data-processing-api 8000:80

# Test health
curl http://localhost:8000/health

# Open dashboard
minikube dashboard

# Clean up
kubectl delete namespace data-processing

# Stop minikube
minikube stop
```

### Rebuild After Code Changes

```bash
# Quick rebuild and redeploy
eval $(minikube docker-env) && \
docker build --target production -t data-processing:v1.0.0 . && \
kubectl rollout restart deployment/data-processing-api -n data-processing && \
kubectl rollout status deployment/data-processing-api -n data-processing
```

### Spark API Examples (with curl)

**Prerequisites:** Port-forward must be running: `kubectl port-forward -n data-processing svc/data-processing-api 8000:80`

```bash
# 1. Check Spark availability
curl http://localhost:8000/spark/status

# 2. Process with Spark (auto-mode)
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/large_dataset.parquet",
    "output_path": "/app/output/spark_result.parquet",
    "mode": "auto"
  }'

# 3. Force Spark distributed mode with custom config
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

# 4. Process CSV file with Spark
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/data.csv",
    "output_path": "/app/output/processed.parquet",
    "mode": "spark",
    "file_type": "csv"
  }'

# 5. Check all available endpoints
curl http://localhost:8000/docs  # OpenAPI documentation
```

### Deploy Spark Cluster (Quick)

```bash
# Option 1: Using Helm (recommended)
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install spark bitnami/spark -n data-processing \
  --set worker.replicaCount=3

# Option 2: Standalone (for testing)
kubectl run spark-master -n data-processing \
  --image=data-processing:v1.0.0 \
  --command -- /opt/spark/bin/spark-class org.apache.spark.deploy.master.Master && \
kubectl expose pod spark-master -n data-processing --port=7077 --name=spark-master-svc

# Verify Spark cluster
kubectl get pods -n data-processing | grep spark

# Access Spark UI
kubectl port-forward -n data-processing pod/spark-master 8080:8080
open http://localhost:8080
```
