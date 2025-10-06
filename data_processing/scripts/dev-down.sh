#!/bin/bash
# ⏹  Stop development environment
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "${BLUE}═══════════════════════════════════════════════${NC}"
echo "${BLUE}  ⏹  Stopping Development Environment${NC}"
echo "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

# Parse arguments
DELETE_NAMESPACE=false
STOP_MINIKUBE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --delete-namespace)
            DELETE_NAMESPACE=true
            shift
            ;;
        --stop-minikube)
            STOP_MINIKUBE=true
            shift
            ;;
        --full)
            DELETE_NAMESPACE=true
            STOP_MINIKUBE=true
            shift
            ;;
        *)
            echo "${RED}Unknown option: $1${NC}"
            echo "Usage: $0 [--delete-namespace] [--stop-minikube] [--full]"
            exit 1
            ;;
    esac
done

# Step 1: Stop port-forwards
echo "${YELLOW}[1/3] Stopping port-forwards...${NC}"
pkill -f "kubectl port-forward" 2>/dev/null && echo "${GREEN}✅ Port-forwards stopped${NC}" || echo "${YELLOW}No port-forwards running${NC}"

# Clean up log files
rm -f /tmp/port-forward-*.log
echo ""

# Step 2: Handle namespace
if [ "$DELETE_NAMESPACE" = true ]; then
    echo "${YELLOW}[2/3] Deleting namespace 'data-processing'...${NC}"
    kubectl delete namespace data-processing --timeout=60s 2>/dev/null && echo "${GREEN}✅ Namespace deleted${NC}" || echo "${YELLOW}Namespace not found or already deleted${NC}"
else
    echo "${YELLOW}[2/3] Keeping namespace (use --delete-namespace to remove)${NC}"
    kubectl get pods -n data-processing 2>/dev/null || echo "${YELLOW}Namespace not found${NC}"
fi
echo ""

# Step 3: Handle Minikube
if [ "$STOP_MINIKUBE" = true ]; then
    echo "${YELLOW}[3/3] Stopping Minikube...${NC}"
    minikube stop && echo "${GREEN}✅ Minikube stopped${NC}" || echo "${YELLOW}Minikube not running${NC}"
else
    echo "${YELLOW}[3/3] Keeping Minikube running (use --stop-minikube to stop)${NC}"
    if minikube status > /dev/null 2>&1; then
        echo "${GREEN}Minikube is running${NC}"
    else
        echo "${YELLOW}Minikube is not running${NC}"
    fi
fi
echo ""

echo "${GREEN}═══════════════════════════════════════════════${NC}"
echo "${GREEN}  ✅ Cleanup Complete${NC}"
echo "${GREEN}═══════════════════════════════════════════════${NC}"
echo ""

if [ "$DELETE_NAMESPACE" = false ]; then
    echo "${BLUE}💡 Tip:${NC} To fully clean up, run:"
    echo "   ${BLUE}bash scripts/dev-down.sh --full${NC}"
    echo ""
fi

echo "📝 What was cleaned up:"
echo "  ✅ Port-forwards stopped"
if [ "$DELETE_NAMESPACE" = true ]; then
    echo "  ✅ Namespace deleted (all pods, services, deployments)"
else
    echo "  ⏸  Namespace kept (pods still running)"
fi
if [ "$STOP_MINIKUBE" = true ]; then
    echo "  ✅ Minikube stopped"
else
    echo "  ⏸  Minikube kept running"
fi
echo ""

if [ "$STOP_MINIKUBE" = false ] && [ "$DELETE_NAMESPACE" = false ]; then
    echo "🚀 To restart:"
    echo "   ${BLUE}bash scripts/dev-up.sh${NC}"
    echo ""
fi
