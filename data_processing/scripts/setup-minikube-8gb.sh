#!/bin/bash
# Setup Minikube with 8GB RAM for Spark processing
set -e

echo "🚀 Setting up Minikube with 8GB RAM and 4 CPUs..."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Stop existing Minikube
echo "${YELLOW}Stopping existing Minikube...${NC}"
minikube stop 2>/dev/null || true

# Delete existing cluster
echo "${YELLOW}Deleting existing Minikube cluster...${NC}"
minikube delete

# Create new cluster with more resources
echo "${YELLOW}Creating new Minikube cluster (8GB RAM, 4 CPUs)...${NC}"
minikube start --memory=8192 --cpus=4 --driver=docker

# Verify
echo ""
echo "${GREEN}✅ Minikube started successfully!${NC}"
echo ""
minikube status
echo ""

# Show resources
echo "${YELLOW}Cluster resources:${NC}"
kubectl top node 2>/dev/null || echo "  Memory: 8GB, CPUs: 4 (metrics not ready yet)"

echo ""
echo "${GREEN}✨ Minikube setup complete!${NC}"
echo ""
echo "📊 Cluster Configuration:"
echo "  Memory: 8GB"
echo "  CPUs:   4"
echo "  Driver: docker"
echo ""
echo "🎯 Next steps:"
echo "  1. Rebuild Docker image:"
echo "     eval \$(minikube -p minikube docker-env)"
echo "     docker build --target production -t data-processing:v1.0.0 ."
echo ""
echo "  2. Deploy everything:"
echo "     bash scripts/test-end-to-end.sh"
echo ""
