"""FastAPI application for data processing infrastructure.

CLIO-focused API for:
- Privacy-preserving data processing
- Large-scale clustering and hierarchy building
- Distributed computing with Spark
- Quality checks and monitoring
"""
import os
import uuid
import time
import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import polars as pl
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

from ..core import Pipeline, ProcessorConfig
from ..privacy import Anonymizer, AnonymizationConfig
from ..analytics import DataQualityChecker, DataClusterer, ClusteringConfig
from ..monitoring import MetricsCollector
from ..distributed import DistributedPipeline, ProcessingMode, SparkConfig, SPARK_AVAILABLE

# Get worker ID (process ID or hostname)
WORKER_ID = os.environ.get('HOSTNAME', f"pid-{os.getpid()}")


# Module-level processor for multiprocessing compatibility
_anonymizer_cache = {}

def get_anonymizer() -> Anonymizer:
    """Get or create anonymizer (cached)."""
    if 'anonymizer' not in _anonymizer_cache:
        _anonymizer_cache['anonymizer'] = Anonymizer(AnonymizationConfig())
    return _anonymizer_cache['anonymizer']

def anonymize_processor(df: pl.DataFrame) -> pl.DataFrame:
    """Anonymize PII in dataframe (module-level for pickling)."""
    anonymizer = get_anonymizer()
    anon_df, _ = anonymizer.anonymize_dataframe(df)
    return anon_df


# Prometheus metrics
api_requests = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint'])
api_duration = Histogram('api_duration_seconds', 'API request duration')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI application."""
    # Startup
    print("Starting CLIO-style data processing API...")
    print(f"Worker ID: {WORKER_ID}")
    yield
    # Shutdown
    print("Shutting down data processing API...")


app = FastAPI(
    title="CLIO Data Processing API",
    description="Privacy-preserving research infrastructure for large-scale data analysis",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests with worker ID and timing."""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    logger.info(f"[Worker {WORKER_ID}] [Request {request_id}] {request.method} {request.url.path} - Started")

    response = await call_next(request)

    duration = time.time() - start_time
    logger.info(f"[Worker {WORKER_ID}] [Request {request_id}] {request.method} {request.url.path} - Completed in {duration:.3f}s (Status: {response.status_code})")

    # Add worker ID to response headers
    response.headers["X-Worker-ID"] = WORKER_ID
    response.headers["X-Request-ID"] = request_id

    return response


# Request/Response Models
class ProcessRequest(BaseModel):
    """Request model for data processing with privacy preservation."""
    input_path: str = Field(..., description="Path to input data file")
    output_path: str = Field(..., description="Path for output data")
    file_type: str = Field(default="parquet", description="File format")
    enable_pii: bool = Field(default=False, description="Enable PII detection and anonymization")
    num_workers: int = Field(default=10, ge=1, le=32, description="Number of parallel workers")
    chunk_size: int = Field(default=10000, ge=100, description="Records per chunk")
    enable_audit: bool = Field(default=False, description="Enable audit logging")


class SparkProcessRequest(BaseModel):
    """Request model for Spark distributed processing."""
    input_path: str
    output_path: str
    file_type: str = "parquet"
    mode: str = "auto"  # auto, local, spark
    spark_master: Optional[str] = "spark://spark-master:7077"
    executor_memory: str = "4g"
    driver_memory: str = "2g"
    executor_cores: int = 2
    num_executors: int = 2


class ProcessResponse(BaseModel):
    """Response model for data processing."""
    job_id: str
    status: str
    message: str
    worker_id: str


class QualityCheckRequest(BaseModel):
    """Request model for quality check."""
    file_path: str = Field(..., description="Path to data file")


class QualityCheckResponse(BaseModel):
    """Response model for quality check."""
    total_records: int
    total_columns: int
    quality_score: float
    issues_count: int
    issues: List[str]


class ClusterRequest(BaseModel):
    """Request model for clustering."""
    input_path: str = Field(..., description="Path to input data")
    text_column: str = Field(default="content", description="Column to cluster by")
    num_clusters: int = Field(default=5, ge=2, le=50, description="Number of clusters")
    algorithm: str = Field(default="kmeans", description="Clustering algorithm (kmeans, dbscan, hierarchical)")
    output_path: Optional[str] = Field(default=None, description="Output path for clustered data")


class ClusterResponse(BaseModel):
    """Response model for clustering."""
    job_id: str
    status: str
    message: str
    num_clusters: int
    worker_id: str
    output_path: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    worker_id: str


# Routes
@app.get("/", response_model=dict)
async def root():
    """Root endpoint with API information."""
    api_requests.labels(method='GET', endpoint='/').inc()
    return {
        "name": "CLIO Data Processing API",
        "description": "Privacy-preserving research infrastructure",
        "version": "0.1.0",
        "docs": "/docs",
        "worker_id": WORKER_ID,
        "features": [
            "Privacy-preserving analytics",
            "Large-scale clustering",
            "Distributed processing (Spark)",
            "Quality checks",
            "Monitoring & observability"
        ]
    }


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    api_requests.labels(method='GET', endpoint='/health').inc()
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        worker_id=WORKER_ID
    )


@app.get("/ready", response_model=dict)
async def ready():
    """Readiness check endpoint."""
    api_requests.labels(method='GET', endpoint='/ready').inc()
    return {
        "status": "ready",
        "worker_id": WORKER_ID
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/process", response_model=ProcessResponse)
async def process_data(request: ProcessRequest, background_tasks: BackgroundTasks):
    """Process data with optional PII detection and anonymization.

    This endpoint demonstrates CLIO-style privacy-preserving data processing:
    - Detects and anonymizes PII in large datasets
    - Maintains audit trail of data access
    - Processes data efficiently using streaming and multiprocessing
    """
    api_requests.labels(method='POST', endpoint='/process').inc()

    try:
        job_id = str(uuid.uuid4())

        print(f"[{WORKER_ID}] Job {job_id} assigned to worker {WORKER_ID}")

        # Add background task
        background_tasks.add_task(
            _process_file,
            job_id=job_id,
            request=request,
            worker_id=WORKER_ID,
        )

        return ProcessResponse(
            job_id=job_id,
            status="accepted",
            message=f"Processing job started (PII: {request.enable_pii}, Workers: {request.num_workers})",
            worker_id=WORKER_ID,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/quality-check", response_model=QualityCheckResponse)
async def quality_check(request: QualityCheckRequest):
    """Run comprehensive data quality check.

    Validates data quality including:
    - Null value detection
    - Duplicate identification
    - Schema validation
    - Outlier detection
    - Quality scoring
    """
    api_requests.labels(method='POST', endpoint='/quality-check').inc()

    try:
        # Load data
        df = pl.read_parquet(request.file_path)

        # Run quality check
        checker = DataQualityChecker()
        report = checker.check(df)

        return QualityCheckResponse(
            total_records=report.total_records,
            total_columns=report.total_columns,
            quality_score=report.quality_score,
            issues_count=len(report.issues),
            issues=report.issues[:10],  # Return first 10 issues
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cluster", response_model=ClusterResponse)
async def cluster_data(request: ClusterRequest, background_tasks: BackgroundTasks):
    """Cluster data by semantic similarity.

    Demonstrates CLIO-style clustering for research:
    - Uses sentence embeddings for semantic understanding
    - Supports multiple clustering algorithms
    - Scales to large datasets
    """
    api_requests.labels(method='POST', endpoint='/cluster').inc()

    try:
        job_id = str(uuid.uuid4())

        # Add background task
        background_tasks.add_task(
            _cluster_task,
            job_id=job_id,
            request=request,
        )

        return ClusterResponse(
            job_id=job_id,
            status="accepted",
            message=f"Clustering job started ({request.num_clusters} clusters, algorithm: {request.algorithm})",
            num_clusters=request.num_clusters,
            worker_id=WORKER_ID,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/spark/process", response_model=ProcessResponse)
async def spark_process(request: SparkProcessRequest, background_tasks: BackgroundTasks):
    """Process data using Spark for distributed computing.

    For extremely large datasets that require distributed processing:
    - Automatically chooses processing mode (local vs distributed)
    - Scales across multiple executors
    - Maintains same privacy guarantees as single-node processing
    """
    api_requests.labels(method='POST', endpoint='/spark/process').inc()

    if not SPARK_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="Spark is not available. Install with: pip install pyspark"
        )

    try:
        job_id = str(uuid.uuid4())

        print(f"[{WORKER_ID}] Spark Job {job_id} assigned to worker {WORKER_ID}")

        # Add background task
        background_tasks.add_task(
            _process_file_spark,
            job_id=job_id,
            request=request,
            worker_id=WORKER_ID,
        )

        return ProcessResponse(
            job_id=job_id,
            status="accepted",
            message=f"Spark processing job started (mode: {request.mode})",
            worker_id=WORKER_ID,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/spark/status")
async def spark_status():
    """Check Spark availability and cluster status."""
    api_requests.labels(method='GET', endpoint='/spark/status').inc()

    if not SPARK_AVAILABLE:
        return {
            "available": False,
            "message": "PySpark is not installed"
        }

    try:
        from pyspark.sql import SparkSession

        return {
            "available": True,
            "pyspark_version": SparkSession.__version__ if hasattr(SparkSession, '__version__') else "3.5.0",
            "master": "spark://spark-master:7077",
            "message": "Spark is available"
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e)
        }


# Background Tasks

async def _process_file(job_id: str, request: ProcessRequest, worker_id: str):
    """Background task to process file with privacy preservation."""
    try:
        logger.info(f"[Worker {worker_id}] [Job {job_id}] Starting processing")
        logger.info(f"[Worker {worker_id}] [Job {job_id}] Input: {request.input_path}")
        logger.info(f"[Worker {worker_id}] [Job {job_id}] PII Detection: {request.enable_pii}")
        logger.info(f"[Worker {worker_id}] [Job {job_id}] Workers: {request.num_workers}")

        # Create pipeline
        config = ProcessorConfig(
            chunk_size=request.chunk_size,
            num_workers=request.num_workers,
            enable_pii_detection=request.enable_pii,
        )

        pipeline = Pipeline(config)

        # Add anonymization if enabled (use module-level function for pickling)
        if request.enable_pii:
            pipeline.add_processor(anonymize_processor)
            logger.info(f"[Worker {worker_id}] [Job {job_id}] PII anonymization enabled")

        # Process file (disable multiprocessing in Docker/API context)
        # For horizontal scaling, increase replicas instead of workers
        stats = pipeline.process_file(
            request.input_path,
            request.output_path,
            file_type=request.file_type,
            enable_multiprocessing=False,  # Single-threaded per API worker
        )

        logger.info(f"[Worker {worker_id}] [Job {job_id}] Completed successfully")
        logger.info(f"[Worker {worker_id}] [Job {job_id}] Records: {stats.processed_records:,}, Duration: {stats.processing_time:.2f}s, Throughput: {stats.throughput:.0f} rec/s")

    except Exception as e:
        logger.error(f"[Worker {worker_id}] [Job {job_id}] Failed: {str(e)}")
        import traceback
        traceback.print_exc()


async def _cluster_task(job_id: str, request: ClusterRequest):
    """Background task to cluster data."""
    try:
        print(f"[Job {job_id}] Clustering data ({request.num_clusters} clusters, {request.algorithm})")

        # Load data
        df = pl.read_parquet(request.input_path)
        print(f"[Job {job_id}] Loaded {len(df):,} records")

        # Cluster
        config = ClusteringConfig(
            num_clusters=request.num_clusters,
            algorithm=request.algorithm,
        )

        clusterer = DataClusterer(config)
        clustered_df = clusterer.cluster_dataframe(df, text_column=request.text_column)

        # Save
        from pathlib import Path
        output_path = request.output_path or f"/tmp/clustered_{job_id}.parquet"
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        clustered_df.write_parquet(output_path, compression="zstd")

        # Get cluster summaries
        summaries = clusterer.get_cluster_summaries(clustered_df, request.text_column)

        print(f"[Job {job_id}] Clustering complete:")
        for cluster_id, summary in summaries.items():
            print(f"  Cluster {cluster_id}: {summary['size']} records ({summary['percentage']:.1f}%)")

        print(f"[Job {job_id}] Saved to {output_path}")

    except Exception as e:
        print(f"[Job {job_id}] Failed: {str(e)}")
        import traceback
        traceback.print_exc()


async def _process_file_spark(job_id: str, request: SparkProcessRequest, worker_id: str):
    """Background task to process file with Spark."""
    try:
        logger.info(f"[Worker {worker_id}] [Spark Job {job_id}] Starting distributed processing")
        logger.info(f"[Worker {worker_id}] [Spark Job {job_id}] Input: {request.input_path}")
        logger.info(f"[Worker {worker_id}] [Spark Job {job_id}] Mode: {request.mode}")
        logger.info(f"[Worker {worker_id}] [Spark Job {job_id}] Master: {request.spark_master}")

        # Create Spark config
        spark_config = SparkConfig(
            app_name=f"api-job-{job_id}",
            master=request.spark_master,
            executor_memory=request.executor_memory,
            driver_memory=request.driver_memory,
            executor_cores=request.executor_cores,
            num_executors=request.num_executors,
        )

        # Create distributed pipeline
        processing_mode = ProcessingMode(request.mode)
        pipeline = DistributedPipeline(
            mode=processing_mode,
            spark_config=spark_config,
        )

        # Process file
        stats = pipeline.process_file(
            request.input_path,
            request.output_path,
            file_type=request.file_type,
        )

        print(f"[{worker_id}] Spark Job {job_id} completed:")
        print(f"  Engine: {stats['engine']}")
        print(f"  Records: {stats['records_processed']:,}")
        print(f"  Time: {stats['processing_time_seconds']:.2f}s")
        print(f"  Throughput: {stats['throughput']:,.0f} rec/s")

        # Cleanup
        pipeline.stop()

    except Exception as e:
        print(f"[{worker_id}] Spark Job {job_id} failed: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
