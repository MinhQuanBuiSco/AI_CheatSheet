"""FastAPI application for data processing infrastructure."""
import os
import uuid
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import polars as pl
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from ..core import Pipeline, ProcessorConfig
from ..privacy import Anonymizer, AnonymizationConfig
from ..analytics import DataQualityChecker
from ..monitoring import MetricsCollector

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
    print("Starting data processing API...")
    yield
    # Shutdown
    print("Shutting down data processing API...")


app = FastAPI(
    title="Data Processing API",
    description="Production-grade data processing infrastructure API",
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


# Request/Response Models
class ProcessRequest(BaseModel):
    """Request model for data processing."""
    input_path: str
    output_path: str
    file_type: str = "parquet"
    enable_pii: bool = False
    num_workers: int = 10
    chunk_size: int = 10000


class ProcessResponse(BaseModel):
    """Response model for data processing."""
    job_id: str
    status: str
    message: str


class QualityCheckRequest(BaseModel):
    """Request model for quality check."""
    file_path: str


class QualityCheckResponse(BaseModel):
    """Response model for quality check."""
    total_records: int
    total_columns: int
    quality_score: float
    issues_count: int
    issues: List[str]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str


# Routes
@app.get("/", response_model=dict)
async def root():
    """Root endpoint."""
    api_requests.labels(method='GET', endpoint='/').inc()
    return {
        "message": "Data Processing API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    api_requests.labels(method='GET', endpoint='/health').inc()
    return HealthResponse(status="healthy", version="0.1.0")


@app.get("/ready", response_model=dict)
async def ready():
    """Readiness check endpoint."""
    api_requests.labels(method='GET', endpoint='/ready').inc()
    return {"status": "ready"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/process", response_model=ProcessResponse)
async def process_data(request: ProcessRequest, background_tasks: BackgroundTasks, req: Request):
    """Process data file."""
    api_requests.labels(method='POST', endpoint='/process').inc()

    try:
        # Create job ID
        job_id = str(uuid.uuid4())

        # Log which worker is handling this
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
            message=f"Processing job {job_id} started on worker {WORKER_ID}",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/quality-check", response_model=QualityCheckResponse)
async def quality_check(request: QualityCheckRequest):
    """Run data quality check."""
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


async def _process_file(job_id: str, request: ProcessRequest, worker_id: str):
    """Background task to process file."""
    try:
        print(f"[{worker_id}] Job {job_id} - Starting processing on worker {worker_id}")
        print(f"[{worker_id}] Job {job_id} - Input: {request.input_path}")
        print(f"[{worker_id}] Job {job_id} - Workers: {request.num_workers}")

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

        # Process file (disable multiprocessing in Docker/API context)
        # For horizontal scaling, increase replicas instead of workers
        stats = pipeline.process_file(
            request.input_path,
            request.output_path,
            file_type=request.file_type,
            enable_multiprocessing=False,  # Single-threaded per API worker
        )

        print(f"[{worker_id}] Job {job_id} completed: {stats.processed_records} records processed")

    except Exception as e:
        print(f"[{worker_id}] Job {job_id} failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
