#!/bin/bash
# 🚀 ONE COMMAND to start entire development environment
# This keeps running to maintain port-forwards
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "${BLUE}═══════════════════════════════════════════════${NC}"
echo "${BLUE}  🚀 Starting Development Environment${NC}"
echo "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

# Step 1: Check Minikube resources
echo "${YELLOW}[1/6] Checking Minikube...${NC}"
if minikube status | grep -q "Running"; then
    # Check memory
    CURRENT_MEM=$(minikube config get memory 2>/dev/null || echo "2048")
    if [ "$CURRENT_MEM" -lt 12288 ]; then
        echo "${YELLOW}⚠️  Minikube has insufficient memory (${CURRENT_MEM}MB). Need 12GB.${NC}"
        echo "${YELLOW}Recreating Minikube with 12GB...${NC}"
        minikube delete
        minikube start --memory=12288 --cpus=4 --driver=docker
    else
        echo "${GREEN}✅ Minikube running with ${CURRENT_MEM}MB${NC}"
    fi
else
    echo "${YELLOW}Starting Minikube (12GB RAM, 4 CPUs)...${NC}"
    minikube start --memory=12288 --cpus=4 --driver=docker
fi
echo ""

# Step 2: Build Docker image
echo "${YELLOW}[2/6] Building Docker image...${NC}"
eval $(minikube -p minikube docker-env)

# Check if image exists and if we should rebuild
if docker images data-processing:v1.0.0 -q | grep -q .; then
    if [ "$FORCE_REBUILD" = "1" ]; then
        echo "${YELLOW}Rebuilding image (FORCE_REBUILD=1)...${NC}"
        docker build --target production -t data-processing:v1.0.0 . > /tmp/docker-build.log 2>&1
        echo "${GREEN}✅ Image rebuilt${NC}"
    else
        echo "${GREEN}✅ Image exists (set FORCE_REBUILD=1 to rebuild)${NC}"
    fi
else
    echo "${YELLOW}Building image...${NC}"
    docker build --target production -t data-processing:v1.0.0 . > /tmp/docker-build.log 2>&1
    echo "${GREEN}✅ Image built${NC}"
fi
echo ""

# Step 3: Deploy Kubernetes resources
echo "${YELLOW}[3/6] Deploying Kubernetes resources...${NC}"
kubectl create namespace data-processing 2>/dev/null || true

# Create secrets
kubectl create secret generic data-processing-secrets \
  --namespace=data-processing \
  --from-literal=postgres_host='localhost' \
  --from-literal=postgres_password='local-dev-password' \
  --from-literal=redis_url='redis://localhost:6379' \
  --from-literal=aws_access_key_id='minioadmin' \
  --from-literal=aws_secret_access_key='minioadmin' \
  --from-literal=encryption_key="$(openssl rand -base64 32)" \
  --dry-run=client -o yaml | kubectl apply -f - > /dev/null 2>&1

# Deploy all resources
kubectl apply -k deployment/k8s/base/ > /dev/null 2>&1
kubectl apply -f deployment/k8s/base/spark-cluster.yaml > /dev/null 2>&1

echo "${GREEN}✅ Resources deployed${NC}"
echo ""

# Step 4: Wait for pods
echo "${YELLOW}[4/6] Waiting for pods to be ready...${NC}"
kubectl wait --for=condition=available deployment/data-processing-api -n data-processing --timeout=180s 2>/dev/null || echo "${YELLOW}API still starting...${NC}"
kubectl wait --for=condition=ready pod -l app=minio -n data-processing --timeout=180s 2>/dev/null
kubectl wait --for=condition=ready pod -l component=spark-master -n data-processing --timeout=180s 2>/dev/null
kubectl wait --for=condition=ready pod -l component=spark-worker -n data-processing --timeout=180s 2>/dev/null

echo "${GREEN}✅ All pods ready${NC}"
echo ""

# Step 5: Create MinIO bucket
echo "${YELLOW}[5/6] Setting up MinIO bucket...${NC}"
MINIO_POD=$(kubectl get pods -n data-processing -l app=minio -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n data-processing $MINIO_POD -- sh -c "
    mkdir -p /tmp/mc-bin && \
    wget -q https://dl.min.io/client/mc/release/linux-amd64/mc -O /tmp/mc-bin/mc && \
    chmod +x /tmp/mc-bin/mc && \
    /tmp/mc-bin/mc alias set local http://localhost:9000 minioadmin minioadmin && \
    /tmp/mc-bin/mc mb local/data-processing 2>/dev/null || echo 'Bucket exists'
" 2>/dev/null

echo "${GREEN}✅ MinIO bucket ready${NC}"
echo ""

# Step 6: Start port-forwards (stays in foreground)
echo "${YELLOW}[6/6] Starting port-forwards...${NC}"

# Function to restart port-forward if it dies
keep_port_forward_alive() {
    local name=$1
    local namespace=$2
    local service=$3
    local ports=$4

    while true; do
        kubectl port-forward -n $namespace svc/$service $ports 2>&1 | while read line; do
            echo "[${name}] $line" >> /tmp/port-forward-${name}.log
        done

        echo "${YELLOW}[${name}] Port-forward died, restarting in 2s...${NC}" | tee -a /tmp/port-forward-${name}.log
        sleep 2
    done
}

# Start port-forwards in background
keep_port_forward_alive "minio" "data-processing" "minio" "9000:9000 9001:9001" &
MINIO_PF_PID=$!

keep_port_forward_alive "api" "data-processing" "data-processing-api" "8000:80" &
API_PF_PID=$!

# Wait for port-forwards to be ready
sleep 3

echo ""
echo "${GREEN}═══════════════════════════════════════════════${NC}"
echo "${GREEN}  ✨ Development Environment Ready!${NC}"
echo "${GREEN}═══════════════════════════════════════════════${NC}"
echo ""
echo "📊 Cluster Status:"
kubectl get pods -n data-processing
echo ""
echo "🌐 Access Points:"
echo "  ${GREEN}MinIO Console:${NC}  http://localhost:9001 (minioadmin/minioadmin)"
echo "  ${GREEN}MinIO API:${NC}      http://localhost:9000"
echo "  ${GREEN}Data API:${NC}       http://localhost:8000"
echo "  ${GREEN}API Docs:${NC}       http://localhost:8000/docs"
echo ""
echo "🧪 Run tests:"
echo "  ${BLUE}bash scripts/test.sh${NC}"
echo ""
echo "⏹  Stop environment:"
echo "  ${BLUE}bash scripts/dev-down.sh${NC}"
echo "  ${BLUE}(or press Ctrl+C in this terminal)${NC}"
echo ""
echo "📝 Port-forward logs:"
echo "  tail -f /tmp/port-forward-minio.log"
echo "  tail -f /tmp/port-forward-api.log"
echo ""
echo "${YELLOW}⚡ Port-forwards are running. Press Ctrl+C to stop...${NC}"

# Cleanup function
cleanup() {
    echo ""
    echo "${YELLOW}Stopping port-forwards...${NC}"
    kill $MINIO_PF_PID $API_PF_PID 2>/dev/null || true
    echo "${GREEN}✅ Port-forwards stopped${NC}"
    exit 0
}

trap cleanup INT TERM

# Keep script running
wait
