#!/bin/bash
# Setup AWS S3 for production deployment
set -e

echo "🚀 Configuring AWS S3 for production..."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check required environment variables
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "${RED}❌ Error: AWS credentials not set${NC}"
    echo ""
    echo "Please set the following environment variables:"
    echo "  export AWS_ACCESS_KEY_ID='your-access-key'"
    echo "  export AWS_SECRET_ACCESS_KEY='your-secret-key'"
    echo "  export AWS_REGION='us-west-2'  # optional, defaults to us-east-1"
    echo ""
    exit 1
fi

# Get AWS region (default to us-east-1)
AWS_REGION=${AWS_REGION:-us-east-1}
BUCKET_NAME=${S3_BUCKET_NAME:-data-processing-$(date +%s)}

echo "${YELLOW}Configuration:${NC}"
echo "  Region: $AWS_REGION"
echo "  Bucket: $BUCKET_NAME"
echo ""

# Create S3 bucket
echo "${YELLOW}Creating S3 bucket: $BUCKET_NAME${NC}"
if [ "$AWS_REGION" = "us-east-1" ]; then
    aws s3 mb s3://$BUCKET_NAME
else
    aws s3 mb s3://$BUCKET_NAME --region $AWS_REGION
fi

echo "${GREEN}✅ Bucket created${NC}"

# Enable versioning (recommended for production)
echo "${YELLOW}Enabling versioning...${NC}"
aws s3api put-bucket-versioning \
    --bucket $BUCKET_NAME \
    --versioning-configuration Status=Enabled

# Set lifecycle policy (optional - auto-delete old files)
echo "${YELLOW}Setting up lifecycle policy (30-day retention for processed files)...${NC}"
cat > /tmp/lifecycle.json <<EOF
{
  "Rules": [
    {
      "Id": "DeleteOldProcessedFiles",
      "Status": "Enabled",
      "Prefix": "output/",
      "Expiration": {
        "Days": 30
      }
    }
  ]
}
EOF

aws s3api put-bucket-lifecycle-configuration \
    --bucket $BUCKET_NAME \
    --lifecycle-configuration file:///tmp/lifecycle.json

rm /tmp/lifecycle.json

echo "${GREEN}✅ Lifecycle policy configured${NC}"

# Create Kubernetes secret for S3 credentials
echo "${YELLOW}Creating Kubernetes secret...${NC}"

# Check if namespace exists
if ! kubectl get namespace data-processing &> /dev/null; then
    kubectl create namespace data-processing
fi

# Create or update all secrets
kubectl create secret generic data-processing-secrets \
  --namespace=data-processing \
  --from-literal=postgres_host='localhost' \
  --from-literal=postgres_password='prod-password' \
  --from-literal=redis_url='redis://localhost:6379' \
  --from-literal=aws_access_key_id=$AWS_ACCESS_KEY_ID \
  --from-literal=aws_secret_access_key=$AWS_SECRET_ACCESS_KEY \
  --from-literal=encryption_key="$(openssl rand -base64 32)" \
  --dry-run=client -o yaml | kubectl apply -f - > /dev/null 2>&1

kubectl create secret generic s3-credentials \
  --namespace=data-processing \
  --from-literal=aws_access_key_id=$AWS_ACCESS_KEY_ID \
  --from-literal=aws_secret_access_key=$AWS_SECRET_ACCESS_KEY \
  --from-literal=aws_region=$AWS_REGION \
  --from-literal=bucket_name=$BUCKET_NAME \
  --dry-run=client -o yaml | kubectl apply -f - > /dev/null 2>&1

echo "${GREEN}✅ Kubernetes secrets created${NC}"

# Update deployment configuration for production
echo "${YELLOW}Updating deployment configuration for production S3...${NC}"

# Create a temporary patch to remove MinIO endpoint
cat > /tmp/deployment-patch.yaml <<EOF
spec:
  template:
    spec:
      containers:
      - name: api
        env:
        - name: AWS_ACCESS_KEY_ID
          value: "$AWS_ACCESS_KEY_ID"
        - name: AWS_SECRET_ACCESS_KEY
          value: "$AWS_SECRET_ACCESS_KEY"
        - name: AWS_REGION
          value: "$AWS_REGION"
EOF

# Check if deployment exists, if not deploy everything
if ! kubectl get deployment data-processing-api -n data-processing &> /dev/null; then
    echo "${YELLOW}Deploying all Kubernetes resources for production...${NC}"

    # Temporarily update deployment.yaml to remove MinIO endpoint
    cp deployment/k8s/base/deployment.yaml deployment/k8s/base/deployment.yaml.bak
    sed -i.tmp '/AWS_ENDPOINT_URL/d' deployment/k8s/base/deployment.yaml

    kubectl apply -k deployment/k8s/base/

    # Restore original file
    mv deployment/k8s/base/deployment.yaml.bak deployment/k8s/base/deployment.yaml
    rm -f deployment/k8s/base/deployment.yaml.tmp

    echo "${YELLOW}Waiting for API deployment...${NC}"
    kubectl wait --for=condition=available deployment/data-processing-api -n data-processing --timeout=120s 2>/dev/null || echo "${YELLOW}API still starting...${NC}"
else
    # Update existing deployment
    echo "${YELLOW}Updating existing API deployment for production S3...${NC}"

    # Remove MinIO endpoint and update credentials
    kubectl set env deployment/data-processing-api -n data-processing \
      AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
      AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
      AWS_REGION=$AWS_REGION \
      AWS_ENDPOINT_URL- \
      > /dev/null 2>&1
fi

rm -f /tmp/deployment-patch.yaml

echo "${GREEN}✅ Production S3 setup complete!${NC}"
echo ""
echo "📝 S3 Bucket Information:"
echo "  Bucket Name: $BUCKET_NAME"
echo "  Region:      $AWS_REGION"
echo "  URL:         s3://$BUCKET_NAME"
echo ""
echo "📚 Upload data to S3:"
echo "  aws s3 cp demo_data/claude_usage_logs.parquet s3://$BUCKET_NAME/data/"
echo "  aws s3 ls s3://$BUCKET_NAME/data/"
echo ""
echo "🎯 Use S3 paths in API:"
echo "  curl -X POST https://your-api.com/spark/process \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"input_path\":\"s3://$BUCKET_NAME/data/claude_usage_logs.parquet\",\"output_path\":\"s3://$BUCKET_NAME/output/result.parquet\",\"mode\":\"auto\"}'"
echo ""
echo "💡 Tip: Add this to your deployment config:"
echo "  AWS_ACCESS_KEY_ID: (from secret)"
echo "  AWS_SECRET_ACCESS_KEY: (from secret)"
echo "  AWS_REGION: $AWS_REGION"
echo "  AWS_ENDPOINT_URL: (remove for production S3)"
