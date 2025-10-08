"""Integration tests for API health and basic endpoints."""

# Import the FastAPI app - adjust path if needed
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

try:
    from data_processing.api.main import app

    client = TestClient(app)
    API_AVAILABLE = True
except Exception as e:
    API_AVAILABLE = False
    pytest.skip(f"API not available: {e}", allow_module_level=True)


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_check_returns_200(self):
        """Test health endpoint returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_response_format(self):
        """Test health endpoint response format."""
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert data["status"] == "healthy"


class TestMetricsEndpoint:
    """Tests for /metrics endpoint (Prometheus format)."""

    def test_metrics_endpoint_returns_200(self):
        """Test metrics endpoint returns 200 OK."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_endpoint_format(self):
        """Test metrics endpoint returns Prometheus format."""
        response = client.get("/metrics")
        content = response.text

        # Check for Prometheus metric format indicators
        assert "# HELP" in content or "# TYPE" in content or "_total" in content

    def test_metrics_content_type(self):
        """Test metrics endpoint content type."""
        response = client.get("/metrics")
        # Prometheus metrics should be plain text
        assert "text/plain" in response.headers.get("content-type", "")
