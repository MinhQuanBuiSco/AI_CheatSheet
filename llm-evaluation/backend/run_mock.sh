#!/bin/bash
# Run backend in MOCK MODE (for testing without vLLM)

echo "Starting backend in MOCK MODE..."
echo "This allows testing the UI without a vLLM server"
echo ""

export MOCK_MODE=true
uvicorn backend.main:app --reload --port 8000
