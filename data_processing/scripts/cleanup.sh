#!/bin/bash
# 🧹 Clean up all resources and prepare for fresh deployment

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "${BLUE}═══════════════════════════════════════════════${NC}"
echo "${BLUE}  🧹 Cleaning Up Data Processing Infrastructure${NC}"
echo "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

# Step 1: Kill port-forwards
echo "${YELLOW}[1/5] Killing port-forward processes...${NC}"
pkill -f "port-forward" 2>/dev/null && echo "${GREEN}✅ Port-forwards killed${NC}" || echo "${YELLOW}⚠️  No port-forwards running${NC}"
echo ""

# Step 2: Delete Kubernetes resources
echo "${YELLOW}[2/5] Deleting Kubernetes resources...${NC}"
if kubectl get namespace data-processing &>/dev/null; then
    kubectl delete namespace data-processing --timeout=120s
    echo "${GREEN}✅ Namespace deleted${NC}"
else
    echo "${YELLOW}⚠️  Namespace doesn't exist${NC}"
fi
echo ""

# Step 3: Clean up Docker images
echo "${YELLOW}[3/5] Cleaning up Docker images...${NC}"
if docker images | grep -q "data-processing"; then
    docker rmi $(docker images | grep data-processing | awk '{print $3}') -f 2>/dev/null
    echo "${GREEN}✅ Docker images removed${NC}"
else
    echo "${YELLOW}⚠️  No data-processing images found${NC}"
fi
echo ""

# Step 4: Clean up temporary files
echo "${YELLOW}[4/5] Cleaning up temporary files...${NC}"
rm -f /tmp/data-processing-v1.0.0.tar
rm -f test-data-*.parquet
echo "${GREEN}✅ Temporary files cleaned${NC}"
echo ""

# Step 5: Verify cleanup
echo "${YELLOW}[5/5] Verifying cleanup...${NC}"
if kubectl get namespace data-processing &>/dev/null; then
    echo "${RED}❌ Namespace still exists${NC}"
    exit 1
fi

if docker images | grep -q "data-processing"; then
    echo "${YELLOW}⚠️  Some Docker images still exist${NC}"
fi

echo "${GREEN}✅ Cleanup verification passed${NC}"
echo ""

echo "${GREEN}═══════════════════════════════════════════════${NC}"
echo "${GREEN}  ✅ Cleanup Complete!${NC}"
echo "${GREEN}═══════════════════════════════════════════════${NC}"
echo ""
echo "Next steps:"
echo "  1. Run: bash scripts/deploy.sh"
echo "  2. Run: bash scripts/test.sh"
echo ""
