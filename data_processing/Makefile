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

# Data generation
generate-data: ## Generate synthetic demo data
	python examples/generate_synthetic_data.py

demo: ## Run complete demonstration
	python examples/demo_pipeline.py

# Docker
docker-build: ## Build Docker images (all targets)
	@echo "Building production image..."
	docker build -t data-processing:latest --target production .
	@echo "Building development image..."
	docker build -t data-processing-dev:latest --target development .
	@echo "Building Spark worker image (this takes time - downloads ~350MB)..."
	docker build -t data-processing-spark:latest --target spark-worker .

docker-build-fast: ## Build only production and dev images (skip Spark)
	@echo "Building production image..."
	docker build -t data-processing:latest --target production .
	@echo "Building development image..."
	docker build -t data-processing-dev:latest --target development .
	@echo "✓ Fast build complete (Spark skipped)"

docker-up: ## Start Docker Compose stack (all services)
	docker-compose up -d

docker-up-fast: ## Start Docker Compose (without Spark)
	docker-compose up -d api postgres redis kafka zookeeper prometheus grafana

docker-down: ## Stop Docker Compose stack
	docker-compose down

docker-logs: ## Show Docker logs
	docker-compose logs -f

docker-shell: ## Open shell in development container
	docker-compose run --rm app /bin/bash

docker-scale-api: ## Scale API to 3 instances
	docker-compose up -d --scale api=3

docker-scale-api-down: ## Scale API back to 1 instance
	docker-compose up -d --scale api=1

# Kubernetes
k8s-deploy: ## Deploy to Kubernetes (using Kustomize)
	kubectl apply -k deployment/k8s/base/

k8s-delete: ## Delete Kubernetes deployment
	kubectl delete -k deployment/k8s/base/

k8s-status: ## Check Kubernetes deployment status
	kubectl get all -n data-processing

k8s-logs: ## Show Kubernetes logs
	kubectl logs -n data-processing -l app=data-processing --tail=100 -f

# API
api-dev: ## Run API server in development mode
	uvicorn data_processing.api.main:app --reload --host 0.0.0.0 --port 8000

api-prod: ## Run API server in production mode
	uvicorn data_processing.api.main:app --host 0.0.0.0 --port 8000 --workers 4

# Monitoring
prometheus-up: ## Start Prometheus
	docker-compose up -d prometheus

grafana-up: ## Start Grafana
	docker-compose up -d grafana

monitoring-up: ## Start all monitoring services
	docker-compose up -d prometheus grafana

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
