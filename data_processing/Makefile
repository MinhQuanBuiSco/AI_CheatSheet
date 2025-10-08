.PHONY: help setup install install-dev test lint format clean docker-build docker-up docker-down k8s-deploy

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Setup
setup: ## Create virtual environment with uv
	@echo "Creating virtual environment with uv..."
	uv venv
	@echo ""
	@echo "✅ Virtual environment created!"
	@echo ""
	@echo "Now run:"
	@echo "  source .venv/bin/activate"
	@echo "  make install-all"

# Installation
install: ## Install production dependencies
	uv pip install -e .

install-dev: ## Install development dependencies
	uv pip install -e ".[dev]"
	pre-commit install

install-all: ## Install all optional dependencies
	uv pip install -e ".[all]"

# Development
format: ## Format code with black and isort
	black src/ tests/ examples/
	isort src/ tests/ examples/

lint: ## Run linters (ruff, mypy)
	ruff check src/ tests/
	mypy src/

test: ## Run tests with coverage
	pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html

test-fast: ## Run tests without coverage
	pytest tests/ -v

pre-commit: ## Run pre-commit hooks
	pre-commit run --all-files

clean: ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete

# Interactive Demo
run-demo: ## Run interactive demo
	python clio_demo.py

generate-logs: ## Generate sample data (10K records)
	python examples/generate_claude_usage_logs.py --conversations 10000

# API (Local Development)
api-dev: ## Run API server in development mode
	uvicorn data_processing.api.main:app --reload --host 0.0.0.0 --port 8000

api-prod: ## Run API server in production mode
	uvicorn data_processing.api.main:app --host 0.0.0.0 --port 8000 --workers 4

# CI/CD
ci-lint: ## Run CI lint checks
	ruff check src/ tests/
	black --check src/ tests/
	isort --check-only src/ tests/
	mypy src/

ci-test: ## Run CI tests
	pytest tests/ --cov=src --cov-report=xml --cov-report=term

ci-security: ## Run security scans
	bandit -r src/
	safety check

# Release
release-patch: ## Release patch version (0.0.X)
	bump2version patch

release-minor: ## Release minor version (0.X.0)
	bump2version minor

release-major: ## Release major version (X.0.0)
	bump2version major

# Demo Management (Minikube)
demo-start: ## Start Minikube and deploy demo
	@echo "🚀 Starting demo environment..."
	minikube start --memory=8g --cpus=4 --driver=docker
	@echo "✓ Minikube started"
	@echo "Deploying services..."
	bash scripts/deploy.sh
	@echo ""
	@echo "✓ Demo ready!"
	@echo ""
	@echo "Access points:"
	@echo "  • API:        http://localhost:8000"
	@echo "  • Grafana:    http://localhost:3000 (admin/admin)"
	@echo "  • Prometheus: http://localhost:9090"
	@echo "  • Spark UI:   http://localhost:8080"
	@echo "  • MinIO:      http://localhost:9001 (minioadmin/minioadmin)"
	@echo ""
	@echo "Run 'make demo-test' to test the system"

demo-stop: ## Stop Minikube cluster
	minikube stop

demo-deploy: ## Deploy/redeploy services to Minikube
	bash scripts/deploy.sh

demo-test: ## Run end-to-end demo test
	bash scripts/test.sh

demo-status: ## Show demo service status
	@echo "Minikube Status:"
	@minikube status || echo "Minikube not running"
	@echo ""
	@echo "Kubernetes Pods:"
	@kubectl get pods -n data-processing 2>/dev/null || echo "Namespace not found"
	@echo ""
	@echo "Port Forwards:"
	@ps aux | grep "port-forward" | grep -v grep || echo "No port forwards running"

demo-logs: ## Show API logs (add SERVICE=spark for other services)
	kubectl logs -n data-processing -l component=api --tail=100 -f

demo-logs-spark: ## Show Spark logs
	kubectl logs -n data-processing -l component=spark --tail=100 -f

demo-logs-all: ## Show all service logs
	kubectl logs -n data-processing --all-containers --tail=50

demo-clean: ## Clean up demo resources
	kubectl delete namespace data-processing 2>/dev/null || true
	pkill -f "kubectl port-forward" || true
	@echo "✓ Demo cleaned up"

demo-rebuild: ## Rebuild and redeploy API (quick iteration)
	@echo "🔨 Rebuilding API..."
	docker build --platform linux/arm64 -t data-processing:v1.0.0 -f Dockerfile --target production .
	@echo "📦 Loading into Minikube..."
	docker save data-processing:v1.0.0 -o /tmp/data-processing.tar
	minikube cp /tmp/data-processing.tar /tmp/data-processing.tar
	minikube ssh "docker load -i /tmp/data-processing.tar"
	rm -f /tmp/data-processing.tar
	@echo "🔄 Restarting API..."
	kubectl rollout restart deployment/data-processing-api -n data-processing
	kubectl wait --for=condition=ready pod -l component=api -n data-processing --timeout=120s
	@echo "✓ API rebuilt and restarted"

demo-dashboard: ## Open Grafana dashboard in browser
	@open http://localhost:3000 || xdg-open http://localhost:3000 || echo "Open http://localhost:3000 in your browser"

demo-port-forward: ## Setup all port forwards
	@echo "Setting up port forwards..."
	@kubectl port-forward -n data-processing svc/data-processing-api 8000:80 &
	@kubectl port-forward -n data-processing svc/grafana 3000:3000 &
	@kubectl port-forward -n data-processing svc/prometheus 9090:9090 &
	@kubectl port-forward -n data-processing svc/spark-master 8080:8080 &
	@kubectl port-forward -n data-processing svc/minio 9000:9000 9001:9001 &
	@echo "✓ Port forwards started"
	@echo "Run 'make demo-port-forward-stop' to stop them"

demo-port-forward-stop: ## Stop all port forwards
	pkill -f "kubectl port-forward" || true
	@echo "✓ Port forwards stopped"

demo-shell: ## Open shell in API pod
	kubectl exec -it -n data-processing deployment/data-processing-api -- /bin/bash

demo-restart-api: ## Restart API pods
	kubectl rollout restart deployment/data-processing-api -n data-processing
	kubectl wait --for=condition=ready pod -l component=api -n data-processing --timeout=120s

demo-scale-api: ## Scale API to 3 replicas
	kubectl scale deployment/data-processing-api --replicas=3 -n data-processing
	@echo "✓ Scaled API to 3 replicas"

demo-scale-down: ## Scale API back to 1 replica
	kubectl scale deployment/data-processing-api --replicas=1 -n data-processing
	@echo "✓ Scaled API to 1 replica"

# Quick shortcuts
demo: demo-start ## Alias for demo-start (Minikube full setup)
demo-restart: demo-clean demo-start ## Full restart of demo
demo-quick: demo-rebuild demo-test ## Quick rebuild and test

# Legacy aliases
run: run-demo ## Alias for run-demo
