#!/bin/bash
# 🧪 Run end-to-end tests
# Assumes dev environment is already running (via dev-up.sh)
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "${BLUE}═══════════════════════════════════════════════${NC}"
echo "${BLUE}  🧪 Running End-to-End Tests${NC}"
echo "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

# Check if services are accessible
echo "${YELLOW}[1/5] Checking services...${NC}"
if ! curl -s --max-time 5 http://localhost:8000/health > /dev/null; then
    echo "${RED}❌ API not accessible at localhost:8000${NC}"
    echo "${YELLOW}Did you run 'bash scripts/dev-up.sh' first?${NC}"
    exit 1
fi

if ! curl -s --max-time 5 http://localhost:9000/minio/health/live > /dev/null; then
    echo "${RED}❌ MinIO not accessible at localhost:9000${NC}"
    echo "${YELLOW}Did you run 'bash scripts/dev-up.sh' first?${NC}"
    exit 1
fi

echo "${GREEN}✅ Services accessible${NC}"
echo ""

# Generate test data inside API pod (where polars is available)
echo "${YELLOW}[2/5] Generating test data...${NC}"
NUM_RECORDS=${NUM_RECORDS:-1000}
TEST_FILE="test-data-$(date +%s).parquet"
BUCKET="data-processing"

# Get API pod name
API_POD=$(kubectl get pods -n data-processing -l component=api -o jsonpath='{.items[0].metadata.name}')

kubectl exec -n data-processing $API_POD -- python3 -c "
import polars as pl
import random
import string
from datetime import datetime, timedelta

num_records = $NUM_RECORDS
start_date = datetime(2024, 1, 1)

df = pl.DataFrame({
    'timestamp': [start_date + timedelta(seconds=i*60) for i in range(num_records)],
    'user_id': [random.randint(1000, 9999) for _ in range(num_records)],
    'tokens_used': [random.randint(100, 10000) for _ in range(num_records)],
    'model': [random.choice(['claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku']) for _ in range(num_records)],
    'cost_usd': [round(random.uniform(0.01, 5.0), 4) for _ in range(num_records)]
})

df.write_parquet('/tmp/$TEST_FILE')
print(f'Generated {num_records} records')
"

echo "${GREEN}✅ Generated ${NUM_RECORDS} records in ${TEST_FILE}${NC}"
echo ""

# Upload to MinIO using boto3 in API pod
echo "${YELLOW}[3/5] Uploading to MinIO...${NC}"

kubectl exec -n data-processing $API_POD -- python3 -c "
import boto3
import os

s3 = boto3.client(
    's3',
    endpoint_url=os.environ.get('AWS_ENDPOINT_URL'),
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
)

# Create bucket if it doesn't exist
try:
    s3.head_bucket(Bucket='data-processing')
except:
    s3.create_bucket(Bucket='data-processing')
    print('Created bucket: data-processing')

# Upload file
s3.upload_file('/tmp/$TEST_FILE', 'data-processing', 'input/$TEST_FILE')
print('✅ Uploaded to s3://data-processing/input/$TEST_FILE')
"

INPUT_PATH="s3://${BUCKET}/input/${TEST_FILE}"
OUTPUT_PATH="s3://${BUCKET}/output/result_$(date +%s)"

echo "${GREEN}✅ Uploaded to ${INPUT_PATH}${NC}"
echo ""

# Submit processing job
echo "${YELLOW}[4/5] Submitting Spark job...${NC}"
echo "  Input:  ${INPUT_PATH}"
echo "  Output: ${OUTPUT_PATH}"
echo ""

RESPONSE=$(curl -s --max-time 10 -X POST "http://localhost:8000/spark/process" \
  -H "Content-Type: application/json" \
  -d "{
    \"input_path\": \"${INPUT_PATH}\",
    \"output_path\": \"${OUTPUT_PATH}\",
    \"mode\": \"spark\",
    \"executor_memory\": \"2g\",
    \"driver_memory\": \"1g\",
    \"executor_cores\": 2
  }")

echo "Response: ${RESPONSE}"
echo ""

# Check if job was submitted successfully
if echo "$RESPONSE" | grep -q "error"; then
    echo "${RED}❌ Job submission failed${NC}"
    echo "$RESPONSE"
    exit 1
fi

echo "${GREEN}✅ Job submitted successfully${NC}"
echo ""

# Wait for job completion (check MinIO for output)
echo "${YELLOW}[5/5] Waiting for job completion...${NC}"
echo "  Checking for _SUCCESS marker every 5 seconds..."
echo ""

MAX_WAIT=180  # 3 minutes
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    # Check if _SUCCESS file exists (indicates job completion)
    OUTPUT_KEY="${OUTPUT_PATH#s3://$BUCKET/}"
    SUCCESS_KEY="${OUTPUT_KEY}/_SUCCESS"

    # Check if _SUCCESS file exists using boto3 in API pod
    SUCCESS_EXISTS=$(kubectl exec -n data-processing $API_POD -- python3 -c "
import boto3
import os

s3 = boto3.client(
    's3',
    endpoint_url=os.environ.get('AWS_ENDPOINT_URL'),
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
)

try:
    s3.head_object(Bucket='data-processing', Key='$SUCCESS_KEY')
    print('true')
except:
    print('false')
" 2>/dev/null)

    if [ "$SUCCESS_EXISTS" = "true" ]; then
        echo ""
        echo "${GREEN}✅ Job completed successfully: ${OUTPUT_PATH}${NC}"

        # Verify file contents using API pod
        echo ""
        echo "${YELLOW}Verifying output...${NC}"

        kubectl exec -n data-processing $API_POD -- python3 -c "
import boto3
import os
import polars as pl

s3 = boto3.client(
    's3',
    endpoint_url=os.environ.get('AWS_ENDPOINT_URL'),
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
)

# List files in output directory
prefix = '$OUTPUT_KEY/'
response = s3.list_objects_v2(Bucket='data-processing', Prefix=prefix)
parquet_files = [obj['Key'] for obj in response.get('Contents', []) if obj['Key'].endswith('.parquet')]

if parquet_files:
    # Download first parquet file
    parquet_file = parquet_files[0]
    s3.download_file('data-processing', parquet_file, '/tmp/output.parquet')

    # Read and verify
    df = pl.read_parquet('/tmp/output.parquet')
    print(f'Output contains {len(df)} records')
    print(f'Columns: {df.columns}')
    print(f'Sample data:')
    print(df.head(3))
else:
    print('No parquet files found in output')
"

        echo ""
        echo "${GREEN}═══════════════════════════════════════════════${NC}"
        echo "${GREEN}  ✅ All tests passed!${NC}"
        echo "${GREEN}═══════════════════════════════════════════════${NC}"
        echo ""
        echo "📊 Test Results:"
        echo "  Input records:  ${NUM_RECORDS}"
        echo "  Input path:     ${INPUT_PATH}"
        echo "  Output path:    ${OUTPUT_PATH}"
        echo ""
        echo "🌐 View in MinIO Console: http://localhost:9001"
        echo ""

        exit 0
    fi

    sleep 5
    ELAPSED=$((ELAPSED + 5))
    echo -n "."
done

echo ""
echo "${RED}❌ Timeout waiting for output file (${MAX_WAIT}s)${NC}"
echo ""
echo "🔍 Debugging tips:"
echo "  1. Check Spark logs:"
echo "     kubectl logs -n data-processing -l component=spark-master --tail=50"
echo "     kubectl logs -n data-processing -l component=spark-worker --tail=50"
echo ""
echo "  2. Check API logs:"
echo "     kubectl logs -n data-processing -l component=api --tail=50"
echo ""
echo "  3. Check MinIO bucket:"
echo "     Open http://localhost:9001 (minioadmin/minioadmin)"
echo ""

exit 1
