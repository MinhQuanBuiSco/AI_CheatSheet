#!/bin/bash
# Cleanup local Minikube deployment
set -e

echo "🧹 Cleaning up local development environment..."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Stop port-forwarding
echo "${YELLOW}Stopping port-forwarding processes...${NC}"
pkill -f "kubectl port-forward" 2>/dev/null || echo "No port-forward processes found"
echo "${GREEN}✅ Port-forwarding stopped${NC}"
echo ""

# Delete Spark cluster
echo "${YELLOW}Deleting Spark cluster...${NC}"
if kubectl get pods -n data-processing -l component=spark-master &> /dev/null; then
    kubectl delete -f deployment/k8s/base/spark-cluster.yaml 2>/dev/null || true
    echo "${GREEN}✅ Spark cluster deleted${NC}"
else
    echo "No Spark cluster found"
fi
echo ""

# Force delete any stuck pods
echo "${YELLOW}Cleaning up any stuck pods...${NC}"
kubectl delete pods -n data-processing --all --force --grace-period=0 2>/dev/null || echo "No pods to clean up"
echo "${GREEN}✅ Pods cleaned${NC}"
echo ""

# Delete namespace (this removes all resources)
echo "${YELLOW}Deleting namespace 'data-processing'...${NC}"
if kubectl get namespace data-processing &> /dev/null; then
    kubectl delete namespace data-processing --timeout=60s

    # If namespace is stuck, force delete it
    if kubectl get namespace data-processing &> /dev/null; then
        echo "${YELLOW}Namespace stuck in terminating state, force deleting...${NC}"
        kubectl get namespace data-processing -o json | \
          jq '.spec.finalizers = []' | \
          kubectl replace --raw "/api/v1/namespaces/data-processing/finalize" -f - 2>/dev/null || true
    fi

    echo "${GREEN}✅ Namespace deleted (API, MinIO, Spark, PVCs, secrets removed)${NC}"
else
    echo "${YELLOW}Namespace 'data-processing' not found${NC}"
fi
echo ""

# Ask about Docker images
echo "${YELLOW}Docker images in Minikube:${NC}"
eval $(minikube -p minikube docker-env) 2>/dev/null
docker images data-processing --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" 2>/dev/null || echo "No data-processing images found"
echo ""

read -p "Do you want to DELETE Docker images? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "${YELLOW}Deleting Docker images...${NC}"
    eval $(minikube -p minikube docker-env) 2>/dev/null
    docker rmi data-processing:v1.0.0 2>/dev/null || echo "Image not found"
    docker image prune -f > /dev/null 2>&1
    echo "${GREEN}✅ Docker images deleted${NC}"
fi
echo ""

# Ask about Minikube
read -p "Do you want to stop Minikube? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "${YELLOW}Stopping Minikube...${NC}"
    minikube stop
    echo "${GREEN}✅ Minikube stopped${NC}"
fi
echo ""

read -p "Do you want to DELETE Minikube cluster completely? (y/n): " -n 1 -r
echo
DELETED_MINIKUBE=false
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "${RED}Deleting Minikube cluster...${NC}"
    minikube delete
    DELETED_MINIKUBE=true
    echo "${GREEN}✅ Minikube cluster deleted${NC}"
fi

echo ""
echo "${GREEN}✨ Cleanup complete!${NC}"
echo ""
echo "📝 What was cleaned:"
echo "  ✅ Port-forwarding processes killed"
echo "  ✅ Spark cluster deleted"
echo "  ✅ Stuck pods force deleted"
echo "  ✅ Namespace 'data-processing' deleted"
echo "  ✅ All Kubernetes resources removed (API, MinIO, Spark, PVCs, secrets)"
echo ""

# Give smart restart instructions based on what was deleted
if [ "$DELETED_MINIKUBE" = true ]; then
    echo "🔄 To start again (Minikube deleted, will rebuild everything):"
    echo "  bash scripts/test-end-to-end.sh"
    echo ""
    echo "  ${GREEN}Note: Docker images were deleted, will rebuild automatically${NC}"
else
    echo "🔄 To start again:"
    echo "  ${YELLOW}# Rebuild Docker image (recommended - to get latest code changes):${NC}"
    echo "  FORCE_REBUILD=1 bash scripts/test-end-to-end.sh"
    echo ""
    echo "  ${YELLOW}# Or use existing Docker image:${NC}"
    echo "  bash scripts/test-end-to-end.sh"
fi
echo ""
echo "💡 Manual setup commands:"
echo "  # Setup infrastructure only:"
echo "  bash scripts/setup-minio-local.sh"
echo ""
echo "  # Setup Spark cluster only:"
echo "  bash scripts/setup-spark-cluster.sh"
