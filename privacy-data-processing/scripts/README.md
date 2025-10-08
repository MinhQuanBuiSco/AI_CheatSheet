# 🚀 Development Scripts

## Quick Start (3 Commands)

### 1. Start Development Environment
```bash
bash scripts/dev-up.sh
```
- ✅ Validates/creates Minikube with 8GB RAM
- ✅ Builds Docker image
- ✅ Deploys API, MinIO, and Spark cluster
- ✅ Starts persistent port-forwards
- ⚠️ **Runs in foreground** - keep this terminal open!

### 2. Run Tests (in another terminal)
```bash
bash scripts/test.sh
```
- ✅ Generates test data
- ✅ Uploads to MinIO
- ✅ Submits Spark processing job
- ✅ Verifies output

### 3. Stop Development Environment
```bash
# Press Ctrl+C in the terminal running dev-up.sh
# Or run from another terminal:
bash scripts/dev-down.sh --full
```

---

## Complete Workflow Example

**Terminal 1:**
```bash
# Start development environment (stays running)
bash scripts/dev-up.sh
```

**Terminal 2:**
```bash
# Wait for "✨ Development Environment Ready!" message
# Then run tests
bash scripts/test.sh

# Run more tests with different data sizes
NUM_RECORDS=10000 bash scripts/test.sh

# When done, stop everything
bash scripts/dev-down.sh --full
```

---

## Access Points

After running `dev-up.sh`, these services are available:

| Service | URL | Credentials |
|---------|-----|-------------|
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin |
| MinIO API | http://localhost:9000 | - |
| Data API | http://localhost:8000 | - |
| API Docs | http://localhost:8000/docs | - |

---

## Scripts Overview

### Core Scripts (Use These!)

#### `dev-up.sh` - Start Everything
Comprehensive startup script that validates resources, builds, deploys, and starts port-forwards.

**Environment variables:**
- `FORCE_REBUILD=1` - Force rebuild Docker image

**Features:**
- Auto-validates Minikube has 8GB RAM (recreates if not)
- Builds Docker image (with caching)
- Deploys all K8s resources
- Creates MinIO bucket
- Starts persistent port-forwards that auto-restart
- Runs in foreground with clean Ctrl+C shutdown

#### `test.sh` - Run Tests
Simple test runner that assumes environment is already running.

**Environment variables:**
- `NUM_RECORDS=1000` - Number of test records (default: 1000)

**What it does:**
- Checks services are accessible
- Generates test data with Polars
- Uploads to MinIO via boto3
- Submits Spark processing job
- Waits for completion and verifies output

#### `dev-down.sh` - Stop Everything
Clean shutdown script with multiple modes.

**Usage:**
```bash
bash scripts/dev-down.sh                    # Stop port-forwards only
bash scripts/dev-down.sh --delete-namespace # Also delete pods/services
bash scripts/dev-down.sh --stop-minikube    # Also stop Minikube
bash scripts/dev-down.sh --full             # Complete cleanup
```

---

### Additional Scripts

#### `setup-minikube-8gb.sh` - One-time Minikube Setup
Creates Minikube cluster with 8GB RAM and 4 CPUs (required for Spark).

**Note:** `dev-up.sh` calls this automatically if needed.

#### `cleanup-local.sh` - Aggressive Cleanup
Use when things go wrong and you need a fresh start.

#### `setup-s3-production.sh` - Production S3 Setup

**Purpose:** Configure AWS S3 for production deployment

**What it does:**
- ✅ Creates S3 bucket with versioning
- ✅ Sets up lifecycle policies (30-day retention)
- ✅ Creates Kubernetes secrets
- ✅ Deploys all K8s resources (if needed)
- ✅ Updates deployment for production S3 (removes MinIO endpoint)
- ✅ Waits for deployment to be ready

**Prerequisites:**
```bash
export AWS_ACCESS_KEY_ID='your-access-key'
export AWS_SECRET_ACCESS_KEY='your-secret-key'
export AWS_REGION='us-west-2'
export S3_BUCKET_NAME='my-data-processing-bucket'  # optional
```

**Usage:**
```bash
# Set credentials
export AWS_ACCESS_KEY_ID='AKIAIOSFODNN7EXAMPLE'
export AWS_SECRET_ACCESS_KEY='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
export AWS_REGION='us-west-2'

# Run setup
bash scripts/setup-s3-production.sh
```

**When to use:**
- First production deployment
- Setting up new AWS account
- Migrating from MinIO to S3

---

## Common Workflows

### First Time Setup

```bash
# Terminal 1: Start environment
bash scripts/dev-up.sh

# Terminal 2: Run tests
bash scripts/test.sh

# Explore
open http://localhost:9001  # MinIO Console
open http://localhost:8000/docs  # API Docs
```

### Daily Development

```bash
# Start environment (if not running)
bash scripts/dev-up.sh

# In another terminal, test your changes
bash scripts/test.sh

# Test with larger datasets
NUM_RECORDS=100000 bash scripts/test.sh

# When done
bash scripts/dev-down.sh
```

### Code Changes

```bash
# Keep dev-up.sh running in Terminal 1
# In Terminal 2:

# Rebuild image
eval $(minikube docker-env)
docker build --target production -t data-processing:v1.0.0 .

# Restart API
kubectl rollout restart deployment/data-processing-api -n data-processing

# Test changes
bash scripts/test.sh
```

### Production Deployment

```bash
# 1. Setup AWS credentials
export AWS_ACCESS_KEY_ID='...'
export AWS_SECRET_ACCESS_KEY='...'
export AWS_REGION='us-west-2'

# 2. Setup S3
bash scripts/setup-s3-production.sh

# 3. Deploy
kubectl apply -k deployment/k8s/base/
```

---

## Troubleshooting

### "API not accessible" in test.sh

**Cause:** Development environment not running

**Fix:**
```bash
# Ensure dev-up.sh is running in another terminal
# Wait for "✨ Development Environment Ready!" message
# Then run test.sh
```

### Port-forwards keep dying

**Cause:** This is normal when port-forward processes terminate

**Fix:** ✅ Already fixed! `dev-up.sh` auto-restarts port-forwards

**Check logs:**
```bash
tail -f /tmp/port-forward-minio.log
tail -f /tmp/port-forward-api.log
```

### Insufficient resources error

**Cause:** Minikube has less than 8GB RAM

**Fix:**
```bash
# dev-up.sh checks this automatically
# Or manually recreate:
bash scripts/setup-minikube-8gb.sh
```

### Pods not starting

```bash
# Check pod status
kubectl get pods -n data-processing

# Check specific pod logs
kubectl logs -n data-processing -l app=data-processing-api
kubectl logs -n data-processing -l component=spark-master
kubectl logs -n data-processing -l component=spark-worker
kubectl logs -n data-processing -l app=minio
```

### Test hangs at "Waiting for job completion"

```bash
# Check Spark logs
kubectl logs -n data-processing -l component=spark-master --tail=50
kubectl logs -n data-processing -l component=spark-worker --tail=50

# Check MinIO bucket in browser
open http://localhost:9001
```

### Fresh start needed

```bash
# Nuclear option - delete everything
bash scripts/dev-down.sh --full
bash scripts/cleanup-local.sh

# Then start fresh
bash scripts/dev-up.sh
```

---

## Script Dependencies

### System Requirements
- **macOS** (or Linux)
- **Minikube** - Kubernetes local cluster
- **Docker** - Container runtime
- **kubectl** - Kubernetes CLI
- **Python 3.12+** - For data generation
- **curl** - For API testing

### Optional Tools
- **mc** - MinIO Client (installed automatically by scripts)
- **helm** - For Spark cluster deployment
- **aws-cli** - For production S3 setup

### Python Dependencies
```bash
pip install polars pyarrow
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Minikube Cluster                    │
│  ┌───────────────────────────────────────────────────┐  │
│  │         Namespace: data-processing                │  │
│  │                                                   │  │
│  │  ┌──────────────┐  ┌─────────────┐  ┌─────────┐  │  │
│  │  │              │  │             │  │         │  │  │
│  │  │   FastAPI    │  │   MinIO     │  │  Spark  │  │  │
│  │  │     API      │  │   (S3)      │  │ Cluster │  │  │
│  │  │              │  │             │  │         │  │  │
│  │  └──────┬───────┘  └──────┬──────┘  └────┬────┘  │  │
│  │         │                 │              │       │  │
│  └─────────┼─────────────────┼──────────────┼───────┘  │
└────────────┼─────────────────┼──────────────┼──────────┘
             │                 │              │
        Port-forward      Port-forward   (internal)
             │                 │
     ┌───────┴─────────┬───────┴──────┐
     │                 │              │
  :8000            :9000/:9001    :7077/:8080
     │                 │              │
localhost:8000  localhost:9000  (not exposed)

                              dev-up.sh keeps
                              port-forwards alive!
```

---

## Environment Variables Reference

### dev-up.sh
```bash
FORCE_REBUILD=1     # Force rebuild Docker image
```

### test.sh
```bash
NUM_RECORDS=1000    # Number of test records (default: 1000)
```

### setup-s3-production.sh
```bash
AWS_ACCESS_KEY_ID=...           # AWS access key
AWS_SECRET_ACCESS_KEY=...       # AWS secret key
AWS_REGION=us-west-2            # AWS region
S3_BUCKET_NAME=my-bucket        # S3 bucket name (optional)
```

---

## Tips & Tricks

**Force rebuild:**
```bash
FORCE_REBUILD=1 bash scripts/dev-up.sh
```

**Large test datasets:**
```bash
NUM_RECORDS=100000 bash scripts/test.sh
```

**Monitor resources:**
```bash
kubectl top nodes
kubectl top pods -n data-processing
minikube dashboard
```

**View logs:**
```bash
kubectl logs -n data-processing -l app=data-processing-api -f
kubectl logs -n data-processing -l component=spark-master -f
tail -f /tmp/port-forward-minio.log
```

---

## Migration from Old Scripts

The following scripts have been **removed** and replaced with the new 3-command workflow:

| Old Script | Replacement |
|------------|-------------|
| `test-end-to-end.sh` | `test.sh` |
| `setup-minio-local.sh` | `dev-up.sh` |
| `start-port-forward.sh` | `dev-up.sh` (built-in) |
| `stop-port-forward.sh` | `dev-down.sh` |
| `generate-test-data.sh` | `test.sh` (built-in) |
| `setup-spark-cluster.sh` | `dev-up.sh` (built-in) |

---

## Next Steps

After running the scripts:

1. **Explore MinIO Console**: http://localhost:9001
2. **Try API Documentation**: http://localhost:8000/docs
3. **Check out guides**: `MINIO_S3_GUIDE.md`, `K8S_DEPLOYMENT_GUIDE.md`
4. **Deploy to production**: Use `setup-s3-production.sh`
