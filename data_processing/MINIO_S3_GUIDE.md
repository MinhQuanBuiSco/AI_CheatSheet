## 📦 MinIO (Local) & S3 (Production) Storage Guide

Complete guide for using S3-compatible object storage with your Kubernetes deployment.

---

## Overview

**Local Development**: MinIO (S3-compatible)
**Production**: AWS S3, Google Cloud Storage, Azure Blob Storage

Both use the same API, so your code works everywhere!

---

## Local Development with MinIO

### Quick Setup (One Command)

```bash
./scripts/setup-minio-local.sh
```

This will:
- ✅ Deploy MinIO to Kubernetes
- ✅ Create default bucket `data-processing`
- ✅ Setup port-forwarding (9000 for API, 9001 for UI)
- ✅ Configure API to use MinIO

### Manual Setup

**1. Deploy MinIO**

```bash
# Deploy MinIO
kubectl apply -f deployment/k8s/base/minio-deployment.yaml

# Wait for MinIO to be ready
kubectl wait --for=condition=ready pod -l app=minio -n data-processing --timeout=120s

# Verify
kubectl get pods -n data-processing -l app=minio
```

**2. Access MinIO**

```bash
# Port-forward MinIO services
kubectl port-forward -n data-processing svc/minio 9000:9000 9001:9001 &

# Access MinIO Console
open http://localhost:9001
# Login: minioadmin / minioadmin
```

**3. Install MinIO Client (mc)**

```bash
# Install mc CLI
brew install minio/stable/mc

# Configure MinIO endpoint
mc alias set local http://localhost:9000 minioadmin minioadmin

# Test connection
mc admin info local
```

**4. Create Bucket**

```bash
# Create bucket
mc mb local/data-processing

# Verify
mc ls local/
```

**5. Upload Data**

```bash
# Upload single file
mc cp demo_data/claude_usage_logs.parquet local/data-processing/

# Upload directory
mc cp --recursive demo_data/ local/data-processing/demo_data/

# List files
mc ls local/data-processing/

# Example output:
# [2025-10-05 10:30:00 PST] 1.2MiB claude_usage_logs.parquet
```

**6. Use S3 Paths in API**

```bash
# Start API port-forward (in another terminal)
kubectl port-forward -n data-processing svc/data-processing-api 8000:80

# Process file from MinIO
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "s3://data-processing/claude_usage_logs.parquet",
    "output_path": "s3://data-processing/output/result.parquet",
    "mode": "auto"
  }'

# Download result
mc cp local/data-processing/output/result.parquet ./result.parquet
```

---

## Production Deployment with AWS S3

### Prerequisites

- AWS Account with S3 access
- AWS CLI configured
- IAM permissions for S3

### Quick Setup

```bash
# Set AWS credentials
export AWS_ACCESS_KEY_ID='your-access-key'
export AWS_SECRET_ACCESS_KEY='your-secret-key'
export AWS_REGION='us-west-2'
export S3_BUCKET_NAME='my-data-processing-bucket'

# Run setup script
./scripts/setup-s3-production.sh
```

### Manual Setup

**1. Create S3 Bucket**

```bash
# Create bucket
aws s3 mb s3://my-data-processing-bucket --region us-west-2

# Enable versioning (recommended)
aws s3api put-bucket-versioning \
  --bucket my-data-processing-bucket \
  --versioning-configuration Status=Enabled

# Set lifecycle policy (optional - auto-delete old files after 30 days)
cat > lifecycle.json <<EOF
{
  "Rules": [{
    "Id": "DeleteOld",
    "Status": "Enabled",
    "Prefix": "output/",
    "Expiration": {"Days": 30}
  }]
}
EOF

aws s3api put-bucket-lifecycle-configuration \
  --bucket my-data-processing-bucket \
  --lifecycle-configuration file://lifecycle.json
```

**2. Create IAM Policy**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::my-data-processing-bucket",
        "arn:aws:s3:::my-data-processing-bucket/*"
      ]
    }
  ]
}
```

**3. Create Kubernetes Secret**

```bash
kubectl create secret generic s3-credentials \
  --namespace=data-processing \
  --from-literal=aws_access_key_id='YOUR_ACCESS_KEY' \
  --from-literal=aws_secret_access_key='YOUR_SECRET_KEY' \
  --from-literal=aws_region='us-west-2'
```

**4. Update Deployment for Production**

Edit `deployment/k8s/base/deployment.yaml`:

```yaml
env:
# Remove MinIO endpoint, use real S3
- name: AWS_ACCESS_KEY_ID
  valueFrom:
    secretKeyRef:
      name: s3-credentials
      key: aws_access_key_id
- name: AWS_SECRET_ACCESS_KEY
  valueFrom:
    secretKeyRef:
      name: s3-credentials
      key: aws_secret_access_key
- name: AWS_REGION
  valueFrom:
    secretKeyRef:
      name: s3-credentials
      key: aws_region
# Remove AWS_ENDPOINT_URL for production S3
```

**5. Deploy Updated Configuration**

```bash
kubectl apply -k deployment/k8s/base/
kubectl rollout restart deployment/data-processing-api -n data-processing
```

**6. Upload Data to S3**

```bash
# Upload file
aws s3 cp demo_data/claude_usage_logs.parquet \
  s3://my-data-processing-bucket/data/

# Upload directory
aws s3 sync demo_data/ s3://my-data-processing-bucket/data/

# List files
aws s3 ls s3://my-data-processing-bucket/data/
```

**7. Process Files from S3**

```bash
curl -X POST https://your-api-domain.com/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "s3://my-data-processing-bucket/data/claude_usage_logs.parquet",
    "output_path": "s3://my-data-processing-bucket/output/result.parquet",
    "mode": "spark"
  }'
```

---

## Using MinIO Console (Web UI)

### Access Console

```bash
# Port-forward (if not already running)
kubectl port-forward -n data-processing svc/minio 9001:9001 &

# Open in browser
open http://localhost:9001
```

**Login:**
- Username: `minioadmin`
- Password: `minioadmin`

### Features

1. **Buckets**: Create/delete buckets
2. **Browser**: Upload/download files via drag-and-drop
3. **Access Keys**: Create additional access keys
4. **Monitoring**: View metrics and usage
5. **Settings**: Configure retention policies

---

## API Examples

### Basic Processing

```bash
# Process from S3/MinIO
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "s3://data-processing/input.parquet",
    "output_path": "s3://data-processing/output.parquet",
    "mode": "auto"
  }'
```

### With Custom Spark Configuration

```bash
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "s3://data-processing/large_dataset.parquet",
    "output_path": "s3://data-processing/processed.parquet",
    "mode": "spark",
    "executor_memory": "8g",
    "num_executors": 4
  }'
```

### Process CSV from S3

```bash
curl -X POST http://localhost:8000/spark/process \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "s3://data-processing/data.csv",
    "output_path": "s3://data-processing/output.parquet",
    "file_type": "csv",
    "mode": "auto"
  }'
```

---

## Python SDK Examples

### Using boto3 Directly

```python
import boto3
import os

# For MinIO (local)
s3_client = boto3.client(
    's3',
    endpoint_url='http://localhost:9000',
    aws_access_key_id='minioadmin',
    aws_secret_access_key='minioadmin',
)

# For production S3
s3_client = boto3.client(
    's3',
    region_name='us-west-2',
)

# Upload file
s3_client.upload_file('local_file.parquet', 'my-bucket', 'data/file.parquet')

# Download file
s3_client.download_file('my-bucket', 'output/result.parquet', 'result.parquet')

# List files
response = s3_client.list_objects_v2(Bucket='my-bucket', Prefix='data/')
for obj in response.get('Contents', []):
    print(obj['Key'])
```

### Using Polars with S3

```python
import polars as pl

# Read from S3 (works with MinIO too!)
df = pl.read_parquet(
    "s3://data-processing/file.parquet",
    storage_options={
        "aws_access_key_id": "minioadmin",
        "aws_secret_access_key": "minioadmin",
        "aws_endpoint_url": "http://localhost:9000",  # MinIO only
    }
)

# Write to S3
df.write_parquet(
    "s3://data-processing/output.parquet",
    storage_options={
        "aws_access_key_id": "minioadmin",
        "aws_secret_access_key": "minioadmin",
        "aws_endpoint_url": "http://localhost:9000",  # MinIO only
    }
)
```

---

## Environment Variables

### Local (MinIO)

```bash
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin
export AWS_ENDPOINT_URL=http://localhost:9000
export AWS_REGION=us-east-1
```

### Production (S3)

```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-west-2
# Don't set AWS_ENDPOINT_URL for real S3
```

---

## Troubleshooting

### Issue: "Connection refused" to MinIO

```bash
# Check if MinIO is running
kubectl get pods -n data-processing -l app=minio

# Check service
kubectl get svc -n data-processing minio

# Restart port-forward
pkill -f "kubectl port-forward.*minio"
kubectl port-forward -n data-processing svc/minio 9000:9000 9001:9001 &
```

### Issue: "Access Denied" errors

```bash
# Check credentials
kubectl exec -n data-processing data-processing-api-xxx -- env | grep AWS

# Verify bucket exists
mc ls local/data-processing/

# Check bucket policy
mc admin policy list local
```

### Issue: Files not appearing in MinIO

```bash
# List all files
mc ls --recursive local/data-processing/

# Check specific path
mc ls local/data-processing/your-path/

# Verify upload
mc stat local/data-processing/file.parquet
```

### Issue: Slow uploads/downloads

MinIO performance tips:
- Use `mc mirror` for large directories
- Enable multipart uploads for files > 64MB
- Increase network bandwidth limits

---

## Best Practices

### Local Development

1. **Use MinIO** for S3-compatible local testing
2. **Keep credentials simple**: `minioadmin/minioadmin` is fine locally
3. **Port-forward** MinIO for easy access
4. **Use mc client** for file management
5. **Test with same S3 paths** as production

### Production

1. **Use IAM roles** instead of access keys when possible
2. **Enable versioning** on S3 buckets
3. **Set lifecycle policies** to auto-delete old data
4. **Use separate buckets** for different environments (dev/staging/prod)
5. **Monitor costs** - S3 can get expensive with large data
6. **Enable encryption** at rest (S3 SSE-S3 or SSE-KMS)
7. **Use CloudFront** for frequent reads

### Security

1. **Never commit** AWS credentials to git
2. **Use Kubernetes secrets** for credentials
3. **Limit IAM permissions** to only what's needed
4. **Enable bucket policies** to restrict access
5. **Use VPC endpoints** for S3 in production (faster, no internet egress)

---

## Migration: MinIO → S3

When moving from local to production:

**1. Update environment variables:**

```bash
# Remove MinIO endpoint
kubectl set env deployment/data-processing-api -n data-processing \
  AWS_ENDPOINT_URL-

# Update credentials
kubectl set env deployment/data-processing-api -n data-processing \
  AWS_ACCESS_KEY_ID=$PROD_ACCESS_KEY \
  AWS_SECRET_ACCESS_KEY=$PROD_SECRET_KEY \
  AWS_REGION=us-west-2
```

**2. Sync data from MinIO to S3:**

```bash
# Download from MinIO
mc mirror local/data-processing /tmp/minio-data/

# Upload to S3
aws s3 sync /tmp/minio-data/ s3://my-production-bucket/

# Verify
aws s3 ls s3://my-production-bucket/ --recursive
```

**3. Update API calls to use new bucket:**

```bash
# Old (MinIO)
s3://data-processing/file.parquet

# New (S3)
s3://my-production-bucket/file.parquet
```

---

## Quick Reference

### MinIO Commands

```bash
# Setup
./scripts/setup-minio-local.sh

# Access Console
open http://localhost:9001

# Upload file
mc cp file.parquet local/data-processing/

# Download file
mc cp local/data-processing/result.parquet ./

# List files
mc ls local/data-processing/

# Delete file
mc rm local/data-processing/file.parquet

# Mirror directory
mc mirror demo_data/ local/data-processing/demo_data/
```

### S3 Commands

```bash
# Setup
./scripts/setup-s3-production.sh

# Upload
aws s3 cp file.parquet s3://my-bucket/

# Download
aws s3 cp s3://my-bucket/result.parquet ./

# List
aws s3 ls s3://my-bucket/

# Sync directory
aws s3 sync demo_data/ s3://my-bucket/data/
```

---

## Summary

✅ **Local**: MinIO provides S3-compatible storage in Kubernetes
✅ **Production**: AWS S3 for scalable, durable cloud storage
✅ **Same API**: Code works identically in both environments
✅ **Easy setup**: Automated scripts for both MinIO and S3
✅ **Full integration**: Spark and API support S3 paths natively

**Next Steps:**
1. Run `./scripts/setup-minio-local.sh`
2. Upload test data via MinIO Console
3. Process using S3 paths: `s3://data-processing/file.parquet`
4. For production, run `./scripts/setup-s3-production.sh`
