#!/bin/bash
# 📊 Generate sample metrics for Grafana/Prometheus demo

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "${BLUE}═══════════════════════════════════════════════${NC}"
echo "${BLUE}  📊 Generating Sample Metrics for Demo${NC}"
echo "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

echo "${YELLOW}Calling API to generate sample metrics...${NC}"

# Call the API endpoint
RESPONSE=$(curl -s -X POST http://localhost:8000/metrics/generate-sample)

if [[ $? -eq 0 ]]; then
    echo "${GREEN}✅ Metrics generated successfully!${NC}"
    echo ""
    echo "Response:"
    echo "$RESPONSE" | python3 -m json.tool
    echo ""
    echo "${GREEN}═══════════════════════════════════════════════${NC}"
    echo "${GREEN}  ✅ Metrics Ready!${NC}"
    echo "${GREEN}═══════════════════════════════════════════════${NC}"
    echo ""
    echo "📊 View in Grafana:"
    echo "  http://localhost:3000"
    echo ""
    echo "📈 View in Prometheus:"
    echo "  http://localhost:9090/graph"
    echo ""
    echo "🔍 Check raw metrics:"
    echo "  curl http://localhost:8000/metrics | grep pii_entities"
    echo ""
else
    echo "${RED}❌ Failed to generate metrics${NC}"
    echo "Make sure the API is running: curl http://localhost:8000/health"
    exit 1
fi
