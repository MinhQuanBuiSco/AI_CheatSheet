#!/bin/bash
# 🚀 Complete deployment of Data Processing Infrastructure with Spark Cluster

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "${BLUE}═══════════════════════════════════════════════${NC}"
echo "${BLUE}  🚀 Deploying Data Processing Infrastructure${NC}"
echo "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

# Step 1: Check prerequisites
echo "${YELLOW}[1/8] Checking prerequisites...${NC}"

# Check Minikube
if ! command -v minikube &> /dev/null; then
    echo "${RED}❌ Minikube not found. Please install: brew install minikube${NC}"
    exit 1
fi

# Check kubectl
if ! command -v kubectl &> /dev/null; then
    echo "${RED}❌ kubectl not found. Please install: brew install kubectl${NC}"
    exit 1
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "${RED}❌ Docker not found. Please install Docker Desktop${NC}"
    exit 1
fi

echo "${GREEN}✅ Prerequisites satisfied${NC}"
echo ""

# Step 2: Verify Minikube
echo "${YELLOW}[2/8] Verifying Minikube...${NC}"

if ! minikube status &>/dev/null; then
    echo "${YELLOW}Starting Minikube with 12GB RAM...${NC}"
    minikube start --memory=12288 --cpus=4 --driver=docker
else
    # Check memory
    CURRENT_MEM=$(minikube ssh "cat /proc/meminfo | grep MemTotal | awk '{print \$2/1024}'" 2>/dev/null | cut -d'.' -f1)
    if [ "$CURRENT_MEM" -lt 12288 ]; then
        echo "${YELLOW}⚠️  Minikube has insufficient memory (${CURRENT_MEM}MB). Need 12GB.${NC}"
        echo "${YELLOW}Recreating Minikube with 12GB...${NC}"
        minikube delete
        minikube start --memory=12288 --cpus=4 --driver=docker
    else
        echo "${GREEN}✅ Minikube running with sufficient resources${NC}"
    fi
fi
echo ""

# Step 3: Build Docker image
echo "${YELLOW}[3/8] Building Docker image...${NC}"

# Detect architecture
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    PLATFORM="linux/arm64"
else
    PLATFORM="linux/amd64"
fi

echo "Building for platform: $PLATFORM"
docker build --platform $PLATFORM -t data-processing:v1.0.0 -f Dockerfile --target production .

echo "${GREEN}✅ Docker image built${NC}"
echo ""

# Step 4: Load image into Minikube
echo "${YELLOW}[4/8] Loading image into Minikube...${NC}"

# Save image to tar
docker save data-processing:v1.0.0 -o /tmp/data-processing-v1.0.0.tar

# Copy to Minikube and load
minikube cp /tmp/data-processing-v1.0.0.tar /tmp/data-processing-v1.0.0.tar
minikube ssh "docker load -i /tmp/data-processing-v1.0.0.tar"

# Cleanup
rm -f /tmp/data-processing-v1.0.0.tar

echo "${GREEN}✅ Image loaded into Minikube${NC}"
echo ""

# Step 5: Create namespace
echo "${YELLOW}[5/8] Creating namespace and resources...${NC}"

kubectl create namespace data-processing --dry-run=client -o yaml | kubectl apply -f -

echo "${GREEN}✅ Namespace created${NC}"
echo ""

# Step 6: Apply Kubernetes manifests
echo "${YELLOW}[6/8] Applying Kubernetes manifests...${NC}"

# Apply in correct order
kubectl apply -f deployment/k8s/base/serviceaccount.yaml
kubectl apply -f deployment/k8s/base/config.yaml
kubectl apply -f deployment/k8s/base/pvc.yaml
kubectl apply -f deployment/k8s/base/minio-deployment.yaml
kubectl apply -f deployment/k8s/base/spark-cluster.yaml
kubectl apply -f deployment/k8s/base/service.yaml
kubectl apply -f deployment/k8s/base/deployment.yaml

echo "${GREEN}✅ Manifests applied${NC}"
echo ""

# Step 7: Wait for pods to be ready
echo "${YELLOW}[7/8] Waiting for pods to be ready...${NC}"

echo "  Waiting for MinIO..."
kubectl wait --for=condition=ready pod -l app=minio -n data-processing --timeout=120s

echo "  Waiting for Spark Master..."
kubectl wait --for=condition=ready pod -l component=spark-master -n data-processing --timeout=120s

echo "  Waiting for Spark Worker..."
kubectl wait --for=condition=ready pod -l component=spark-worker -n data-processing --timeout=120s

echo "  Waiting for API..."
kubectl wait --for=condition=ready pod -l component=api -n data-processing --timeout=120s

echo "${GREEN}✅ All pods ready${NC}"
echo ""

# Step 8: Setup port-forwards
echo "${YELLOW}[8/8] Setting up port-forwards...${NC}"

# Kill existing port-forwards
pkill -f "port-forward" 2>/dev/null || true
sleep 2

# Start new port-forwards in background
kubectl port-forward -n data-processing svc/data-processing-api 8000:80 >/dev/null 2>&1 &
kubectl port-forward -n data-processing svc/minio 9000:9000 9001:9001 >/dev/null 2>&1 &
kubectl port-forward -n data-processing svc/spark-master 8080:8080 >/dev/null 2>&1 &

sleep 3
echo "${GREEN}✅ Port-forwards established${NC}"
echo ""

# Final status
echo "${GREEN}═══════════════════════════════════════════════${NC}"
echo "${GREEN}  ✅ Deployment Complete!${NC}"
echo "${GREEN}═══════════════════════════════════════════════${NC}"
echo ""
echo "📊 Resources deployed:"
kubectl get pods -n data-processing
echo ""
echo "🌐 Access points:"
echo "  API:               http://localhost:8000/health"
echo "  MinIO Console:     http://localhost:9001 (minioadmin/minioadmin)"
echo "  Spark Master UI:   http://localhost:8080"
echo ""
echo "🧪 Run tests:"
echo "  bash scripts/test.sh"
echo ""
echo "🔍 View logs:"
echo "  kubectl logs -n data-processing -l component=api --tail=50"
echo "  kubectl logs -n data-processing -l component=spark-master --tail=50"
echo "  kubectl logs -n data-processing -l component=spark-worker --tail=50"
echo ""
