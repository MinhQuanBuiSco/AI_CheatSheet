# Multi-stage production-grade Dockerfile for data processing infrastructure
# Optimized for both AMD64 and ARM64 (Apple Silicon)
# Uses uv for fast package management

# ============================================================================
# Stage 1: Base image with Python and system dependencies
# ============================================================================
FROM python:3.12-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package installer)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# ============================================================================
# Stage 2: Builder - Install Python dependencies with uv
# ============================================================================
FROM base as builder

WORKDIR /build

# Copy dependency files
COPY pyproject.toml README.md ./

# Create virtual environment and install dependencies with uv
RUN uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python \
    polars \
    pyarrow \
    click \
    rich \
    pydantic \
    cryptography \
    prometheus-client \
    scikit-learn \
    sentence-transformers \
    presidio-analyzer \
    presidio-anonymizer \
    psutil \
    orjson \
    blake3 \
    faker \
    pyspark==3.5.0 \
    fastapi \
    "uvicorn[standard]"

# ============================================================================
# Stage 3: Production runtime
# ============================================================================
FROM base as production

# Install Java for Spark driver functionality
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Set Java home (auto-detect architecture: arm64 or amd64)
RUN ARCH=$(dpkg --print-architecture) && \
    JAVA_DIR="/usr/lib/jvm/java-21-openjdk-${ARCH}" && \
    echo "export JAVA_HOME=${JAVA_DIR}" >> /etc/environment && \
    echo "JAVA_HOME=${JAVA_DIR}" > /etc/profile.d/java.sh && \
    chmod +x /etc/profile.d/java.sh

# Set JAVA_HOME for Docker build (will be overridden at runtime for different archs)
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-arm64
ENV PATH="$JAVA_HOME/bin:$PATH"

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser examples/ ./examples/
COPY --chown=appuser:appuser pyproject.toml ./
COPY --chown=appuser:appuser README.md ./

# Install the application using uv
RUN uv pip install --python /opt/venv/bin/python -e .

# Create necessary directories
RUN mkdir -p /app/data /app/output /app/logs && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import data_processing; print('healthy')" || exit 1

# Default command
CMD ["python", "-m", "data_processing", "info"]

# ============================================================================
# Stage 4: Development image with additional tools
# ============================================================================
FROM production as development

USER root

# Install development dependencies with uv
RUN uv pip install --python /opt/venv/bin/python \
    pytest \
    pytest-cov \
    pytest-asyncio \
    mypy \
    ruff \
    black \
    isort \
    pre-commit \
    ipython \
    jupyter

USER appuser

CMD ["/bin/bash"]

# ============================================================================
# Stage 5: Spark worker image
# ============================================================================
FROM production as spark-worker

USER root

# Install Java and required tools for Spark
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Set Java home (works for both amd64 and arm64)
RUN JAVA_DIR=$(find /usr/lib/jvm -name "java-21-openjdk-*" -type d | head -1) && \
    echo "export JAVA_HOME=${JAVA_DIR}" >> /etc/profile.d/java.sh && \
    echo "export PATH=\${JAVA_HOME}/bin:\${PATH}" >> /etc/profile.d/java.sh

ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-arm64
ENV PATH="$JAVA_HOME/bin:$PATH"

# Download and install Spark
ENV SPARK_VERSION=3.5.0
ENV HADOOP_VERSION=3

# Use ADD with caching - Docker caches downloads
ADD --chown=appuser:appuser https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz /tmp/spark.tgz

RUN tar -xzf /tmp/spark.tgz -C /opt/ && \
    mv /opt/spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION} /opt/spark && \
    rm /tmp/spark.tgz && \
    mkdir -p /opt/spark/work /opt/spark/logs && \
    chown -R appuser:appuser /opt/spark

ENV SPARK_HOME=/opt/spark
ENV PATH="$SPARK_HOME/bin:$PATH"
ENV PYSPARK_PYTHON=/opt/venv/bin/python

USER appuser

CMD ["spark-submit", "--version"]
