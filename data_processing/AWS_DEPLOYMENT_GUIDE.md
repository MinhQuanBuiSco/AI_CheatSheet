# AWS Deployment Guide

Guide for deploying the data processing infrastructure to AWS with different Spark compute options.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        AWS Cloud                             │
│                                                              │
│  ┌──────────────┐      ┌─────────────────────────────────┐ │
│  │   FastAPI    │      │      Spark Compute              │ │
│  │   (EKS/ECS)  │─────▶│  (EMR Serverless / EKS / EMR)  │ │
│  └──────────────┘      └─────────────────────────────────┘ │
│         │                            │                      │
│         │                            │                      │
│         └────────────┬───────────────┘                      │
│                      ▼                                      │
│              ┌──────────────┐                               │
│              │   S3 Bucket  │                               │
│              │   (Storage)  │                               │
│              └──────────────┘                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Option 1: EMR Serverless (Recommended for Variable Workloads)

**Best for:**
- Intermittent workloads (batch jobs, scheduled tasks)
- Cost optimization (pay per job)
- No cluster management

### Setup

#### 1. Create EMR Serverless Application

```bash
# Create EMR Serverless application
aws emr-serverless create-application \
  --name data-processing-spark \
  --type SPARK \
  --release-label emr-7.0.0 \
  --initial-capacity '{
    "DRIVER": {
      "workerCount": 1,
      "workerConfiguration": {
        "cpu": "2vCPU",
        "memory": "4GB"
      }
    },
    "EXECUTOR": {
      "workerCount": 10,
      "workerConfiguration": {
        "cpu": "4vCPU",
        "memory": "8GB"
      }
    }
  }' \
  --maximum-capacity '{
    "cpu": "100vCPU",
    "memory": "200GB"
  }' \
  --auto-start-configuration enabled=true \
  --auto-stop-configuration enabled=true,idleTimeoutMinutes=15

# Get application ID
export EMR_APP_ID=$(aws emr-serverless list-applications --query 'applications[0].id' --output text)
echo "EMR Application ID: $EMR_APP_ID"
```

#### 2. Create IAM Role for EMR Serverless

```bash
# Create trust policy
cat > emr-serverless-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "emr-serverless.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name EMRServerlessJobRole \
  --assume-role-policy-document file://emr-serverless-trust-policy.json

# Attach S3 access policy
aws iam attach-role-policy \
  --role-name EMRServerlessJobRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

# Get role ARN
export EMR_ROLE_ARN=$(aws iam get-role --role-name EMRServerlessJobRole --query 'Role.Arn' --output text)
echo "EMR Role ARN: $EMR_ROLE_ARN"
```

#### 3. Update API Code to Use EMR Serverless

Create `src/data_processing/distributed/emr_serverless_engine.py`:

```python
"""EMR Serverless integration for Spark jobs."""
import boto3
import time
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class EMRServerlessEngine:
    """Submit Spark jobs to EMR Serverless."""

    def __init__(
        self,
        application_id: str,
        execution_role_arn: str,
        s3_bucket: str,
        region: str = "us-east-1"
    ):
        self.application_id = application_id
        self.execution_role_arn = execution_role_arn
        self.s3_bucket = s3_bucket
        self.client = boto3.client('emr-serverless', region_name=region)

    def submit_job(
        self,
        input_path: str,
        output_path: str,
        spark_submit_params: Optional[Dict[str, Any]] = None
    ) -> str:
        """Submit Spark job to EMR Serverless.

        Args:
            input_path: S3 path to input data
            output_path: S3 path for output
            spark_submit_params: Additional Spark configuration

        Returns:
            Job run ID
        """
        # Upload PySpark script to S3
        script_s3_path = self._upload_pyspark_script()

        # Default Spark configuration
        spark_conf = {
            "spark.executor.cores": "4",
            "spark.executor.memory": "8g",
            "spark.driver.cores": "2",
            "spark.driver.memory": "4g",
        }

        if spark_submit_params:
            spark_conf.update(spark_submit_params)

        # Submit job
        response = self.client.start_job_run(
            applicationId=self.application_id,
            executionRoleArn=self.execution_role_arn,
            jobDriver={
                'sparkSubmit': {
                    'entryPoint': script_s3_path,
                    'entryPointArguments': [
                        input_path,
                        output_path
                    ],
                    'sparkSubmitParameters': self._format_spark_params(spark_conf)
                }
            },
            configurationOverrides={
                'monitoringConfiguration': {
                    's3MonitoringConfiguration': {
                        'logUri': f's3://{self.s3_bucket}/logs/'
                    }
                }
            }
        )

        job_run_id = response['jobRunId']
        logger.info(f"EMR Serverless job submitted: {job_run_id}")

        return job_run_id

    def get_job_status(self, job_run_id: str) -> Dict[str, Any]:
        """Get job status.

        Returns:
            Job status dict with state, progress, etc.
        """
        response = self.client.get_job_run(
            applicationId=self.application_id,
            jobRunId=job_run_id
        )

        return {
            'state': response['jobRun']['state'],
            'stateDetails': response['jobRun'].get('stateDetails', ''),
            'createdAt': response['jobRun']['createdAt'],
            'updatedAt': response['jobRun']['updatedAt']
        }

    def wait_for_completion(
        self,
        job_run_id: str,
        timeout: int = 3600,
        poll_interval: int = 10
    ) -> bool:
        """Wait for job to complete.

        Returns:
            True if successful, False otherwise
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = self.get_job_status(job_run_id)
            state = status['state']

            logger.info(f"Job {job_run_id}: {state}")

            if state == 'SUCCESS':
                return True
            elif state in ['FAILED', 'CANCELLED']:
                logger.error(f"Job failed: {status.get('stateDetails')}")
                return False

            time.sleep(poll_interval)

        logger.error(f"Job timed out after {timeout}s")
        return False

    def _upload_pyspark_script(self) -> str:
        """Upload PySpark processing script to S3."""
        # TODO: Upload your processing script
        # For now, return placeholder
        return f"s3://{self.s3_bucket}/scripts/process.py"

    def _format_spark_params(self, conf: Dict[str, str]) -> str:
        """Format Spark configuration as command-line parameters."""
        params = []
        for key, value in conf.items():
            params.append(f"--conf {key}={value}")
        return " ".join(params)
```

#### 4. Update API Endpoint

Modify `src/data_processing/api/main.py`:

```python
from data_processing.distributed.emr_serverless_engine import EMRServerlessEngine
import os

# Add this to your /spark/process endpoint
@app.post("/spark/process")
async def process_with_spark(request: SparkProcessRequest):
    """Process data using EMR Serverless."""

    # Check if EMR Serverless is configured
    emr_app_id = os.getenv('EMR_APPLICATION_ID')
    emr_role_arn = os.getenv('EMR_EXECUTION_ROLE_ARN')

    if emr_app_id and emr_role_arn:
        # Use EMR Serverless
        engine = EMRServerlessEngine(
            application_id=emr_app_id,
            execution_role_arn=emr_role_arn,
            s3_bucket=os.getenv('S3_BUCKET_NAME')
        )

        job_id = engine.submit_job(
            input_path=request.input_path,
            output_path=request.output_path
        )

        return {
            "job_id": job_id,
            "status": "submitted",
            "engine": "emr-serverless"
        }
    else:
        # Fallback to local Spark
        # ... existing code
```

#### 5. Deploy to EKS

```bash
# Update deployment with EMR config
kubectl set env deployment/data-processing-api -n data-processing \
  EMR_APPLICATION_ID=$EMR_APP_ID \
  EMR_EXECUTION_ROLE_ARN=$EMR_ROLE_ARN \
  S3_BUCKET_NAME=your-bucket-name
```

---

## Option 2: EKS with Spark Operator (Recommended for Consistent Workloads)

**Best for:**
- Continuous workloads
- Full control over infrastructure
- Cost optimization with spot instances

### Setup

#### 1. Install Spark Operator on EKS

```bash
# Add Spark Operator Helm repo
helm repo add spark-operator https://kubeflow.github.io/spark-operator
helm repo update

# Install Spark Operator
helm install spark-operator spark-operator/spark-operator \
  --namespace spark-operator \
  --create-namespace \
  --set webhook.enable=true \
  --set sparkJobNamespace=data-processing

# Verify installation
kubectl get pods -n spark-operator
```

#### 2. Create Spark Application CRD

```yaml
# spark-job-template.yaml
apiVersion: sparkoperator.k8s.io/v1beta2
kind: SparkApplication
metadata:
  name: data-processing-job
  namespace: data-processing
spec:
  type: Python
  mode: cluster
  image: data-processing:v1.0.0
  imagePullPolicy: Always
  mainApplicationFile: local:///app/src/data_processing/distributed/spark_job.py
  sparkVersion: "3.5.0"

  driver:
    cores: 2
    memory: "4g"
    labels:
      version: 3.5.0
    serviceAccount: data-processing-sa
    env:
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

  executor:
    cores: 4
    instances: 3
    memory: "8g"
    labels:
      version: 3.5.0

  sparkConf:
    "spark.hadoop.fs.s3a.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem"
    "spark.hadoop.fs.s3a.aws.credentials.provider": "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider"
```

#### 3. Submit Spark Jobs via API

Update your API to create SparkApplication CRDs:

```python
from kubernetes import client, config
import yaml

def submit_spark_job_k8s(input_path: str, output_path: str):
    """Submit Spark job as K8s CRD."""

    # Load K8s config
    config.load_incluster_config()
    custom_api = client.CustomObjectsApi()

    # Load SparkApplication template
    with open('spark-job-template.yaml') as f:
        spark_app = yaml.safe_load(f)

    # Update paths
    spark_app['spec']['arguments'] = [input_path, output_path]

    # Create SparkApplication
    response = custom_api.create_namespaced_custom_object(
        group="sparkoperator.k8s.io",
        version="v1beta2",
        namespace="data-processing",
        plural="sparkapplications",
        body=spark_app
    )

    return response['metadata']['name']
```

---

## Option 3: Amazon EMR (Traditional Cluster)

**Best for:**
- Long-running clusters
- Complex Spark applications
- Need for YARN resource management

### Setup

```bash
# Create EMR cluster
aws emr create-cluster \
  --name "DataProcessingCluster" \
  --release-label emr-7.0.0 \
  --applications Name=Spark \
  --ec2-attributes KeyName=your-key \
  --instance-type m5.xlarge \
  --instance-count 3 \
  --use-default-roles \
  --log-uri s3://your-bucket/logs/

# Get cluster ID
export CLUSTER_ID=$(aws emr list-clusters --active --query 'Clusters[0].Id' --output text)

# Submit Spark job
aws emr add-steps \
  --cluster-id $CLUSTER_ID \
  --steps Type=Spark,Name="DataProcessing",ActionOnFailure=CONTINUE,Args=[
    --deploy-mode,cluster,
    --master,yarn,
    s3://your-bucket/scripts/process.py,
    s3://your-bucket/input/,
    s3://your-bucket/output/
  ]
```

Update API configuration:

```python
# Point to EMR master
spark_config = SparkConfig(
    master="yarn",  # EMR uses YARN
    app_name="data-processing"
)
```

---

## Cost Comparison (Monthly, us-east-1)

| Option | Small Workload | Medium Workload | Large Workload |
|--------|---------------|-----------------|----------------|
| **EMR Serverless** | $50 (100 jobs/day, 5min) | $200 (500 jobs/day) | $1000 (24/7) |
| **EKS + Spot** | $60 (2 nodes) | $180 (6 nodes) | $600 (20 nodes) |
| **EMR Cluster** | $200 (3 nodes, 24/7) | $400 (6 nodes) | $1200 (15 nodes) |

---

## Recommended Setup

### For Most Use Cases: EMR Serverless + EKS API

```
API (EKS) → Submit Jobs → EMR Serverless → Process Data → S3
```

**Why:**
- API runs on EKS (always available)
- Spark jobs run on EMR Serverless (pay per job)
- Best cost/performance balance

### Environment Variables

```bash
# Add to your deployment
kubectl set env deployment/data-processing-api -n data-processing \
  SPARK_MODE=emr-serverless \
  EMR_APPLICATION_ID=app-xxx \
  EMR_EXECUTION_ROLE_ARN=arn:aws:iam::xxx \
  AWS_REGION=us-east-1 \
  S3_BUCKET_NAME=your-bucket
```

---

## Next Steps

1. Choose your Spark compute option
2. Run the appropriate setup script
3. Update your API configuration
4. Deploy to EKS
5. Test with sample data

For production deployment, see `scripts/setup-s3-production.sh` for S3 configuration.
