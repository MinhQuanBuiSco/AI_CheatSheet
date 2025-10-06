#!/bin/bash
# Setup Spark cluster in Minikube
set -e

echo "⚡ Setting up Spark cluster in Minikube..."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "${YELLOW}Installing Spark cluster (using official Apache Spark images)...${NC}"

# Create namespace if it doesn't exist
kubectl create namespace data-processing 2>/dev/null || true

# Deploy Spark cluster using official Apache Spark images
kubectl apply -f deployment/k8s/base/spark-cluster.yaml

if [ $? -ne 0 ]; then
    echo "${RED}❌ Failed to deploy Spark cluster${NC}"
    exit 1
fi

echo "${GREEN}✅ Spark cluster resources created${NC}"
echo ""

# Wait for Spark master to be ready
echo "${YELLOW}Waiting for Spark master to be ready...${NC}"
kubectl wait --for=condition=ready pod -l component=spark-master -n data-processing --timeout=300s

if [ $? -ne 0 ]; then
    echo "${RED}❌ Spark master failed to start${NC}"
    echo "Check logs: kubectl logs -n data-processing -l component=spark-master"
    exit 1
fi

echo "${GREEN}✅ Spark master is ready${NC}"
echo ""

# Wait for Spark workers to be ready
echo "${YELLOW}Waiting for Spark workers to be ready...${NC}"
kubectl wait --for=minikube start =ready pod -l component=spark-worker -n data-processing --timeout=300s

if [ $? -ne 0 ]; then
    echo "${YELLOW}⚠️  Spark workers taking longer than expected${NC}"
    echo "Check status: kubectl get pods -n data-processing -l component=spark-worker"
else
    echo "${GREEN}✅ Spark workers are ready${NC}"
fi
echo ""

echo ""
echo "${GREEN}✅ Spark cluster setup complete!${NC}"
echo ""
echo "📊 Cluster Information:"
echo "  Master URL:  spark://spark-master:7077"
echo "  Master UI:   http://localhost:8080 (after port-forward)"
echo "  Workers:     2"
echo ""

# Get pod status
echo "📝 Pod Status:"
kubectl get pods -n data-processing -l component

echo ""
echo "🔗 Port-forward Spark Master UI (optional):"
echo "  kubectl port-forward -n data-processing svc/spark-master 8080:8080"
echo ""
echo "🎯 Use in API:"
echo "  Spark master is already configured as: spark://spark-master:7077"
echo "  Change mode to 'auto' or 'spark' in your API requests"
echo ""
