# Multi-stage production-grade Dockerfile for data processing infrastructure
# Optimized for both AMD64 and ARM64 (Apple Silicon)

# ============================================================================
# Stage 1: Base image with Python and system dependencies
# ============================================================================
FROM python:3.12-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ============================================================================
# Stage 2: Builder - Install Python dependencies
# ============================================================================
FROM base as builder

WORKDIR /build

# Copy dependency files
COPY pyproject.toml README.md ./

# Install dependencies to a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install production dependencies
RUN pip install --no-cache-dir \
    polars>=0.20.0 \
    pyarrow>=15.0.0 \
    click>=8.1.7 \
    rich>=13.7.0 \
    pydantic>=2.5.0 \
    cryptography>=42.0.0 \
    prometheus-client>=0.19.0 \
    scikit-learn>=1.4.0 \
    sentence-transformers>=2.3.0 \
    presidio-analyzer>=2.2.0 \
    presidio-anonymizer>=2.2.0 \
    psutil>=5.9.0 \
    orjson>=3.9.0 \
    blake3>=0.4.0 \
    faker>=22.0.0 \
    pyspark>=3.5.0 \
    fastapi>=0.109.0 \
    uvicorn[standard]>=0.27.0 \
    great-expectations>=0.18.0 \
    opentelemetry-api>=1.22.0 \
    opentelemetry-sdk>=1.22.0 \
    opentelemetry-instrumentation-fastapi>=0.43b0 \
    kafka-python>=2.0.2

# ============================================================================
# Stage 3: Production runtime
# ============================================================================
FROM base as production

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

# Install the application
RUN pip install -e .

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

# Install development dependencies
RUN pip install --no-cache-dir \
    pytest>=7.4.0 \
    pytest-cov>=4.1.0 \
    pytest-asyncio>=0.21.0 \
    mypy>=1.8.0 \
    ruff>=0.1.0 \
    black>=23.12.0 \
    isort>=5.13.0 \
    pre-commit>=3.6.0 \
    ipython>=8.20.0 \
    jupyter>=1.0.0

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

# Set Java home
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-arm64
ENV PATH="$JAVA_HOME/bin:$PATH"

# Download and install Spark
ENV SPARK_VERSION=3.5.0
ENV HADOOP_VERSION=3

# Use ADD with caching - Docker caches downloads
ADD --chown=appuser:appuser https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz /tmp/spark.tgz

RUN tar -xzf /tmp/spark.tgz -C /opt/ && \
    ln -s /opt/spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION} /opt/spark && \
    rm /tmp/spark.tgz && \
    mkdir -p /opt/spark/work /opt/spark/logs && \
    chown -R appuser:appuser /opt/spark

ENV SPARK_HOME=/opt/spark
ENV PATH="$SPARK_HOME/bin:$PATH"
ENV PYSPARK_PYTHON=/opt/venv/bin/python

USER appuser

CMD ["spark-submit", "--version"]
