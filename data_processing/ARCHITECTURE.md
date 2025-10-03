# System Architecture

Production-grade data processing infrastructure inspired by Anthropic's CLIO team.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ANTHROPIC CLIO-LEVEL                            │
│                         DATA PROCESSING INFRASTRUCTURE                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────┐
│                           API LAYER (FastAPI)                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  ┌─────────────┐     │
│  │  REST API   │  │   GraphQL    │  │  WebSocket │  │   gRPC      │     │
│  │  Endpoints  │  │  (Optional)  │  │  (Stream)  │  │  (Optional) │     │
│  └─────────────┘  └──────────────┘  └────────────┘  └─────────────┘     │
└───────────────────────────────────────────────────────────────────────────┘
                                     │
┌──────────────────────────────────────┴────────────────────────────────────┐
│                         PROCESSING ENGINE                                  │
│                                                                            │
│  ┌──────────────────────┐          ┌──────────────────────┐             │
│  │   LOCAL PROCESSING   │          │ DISTRIBUTED PROCESSING│             │
│  │   (Polars)           │          │   (PySpark)           │             │
│  │                      │          │                       │             │
│  │ • Single Machine     │◄────────►│ • Multi-Node Cluster  │             │
│  │ • Up to 100GB        │   Auto   │ • Unlimited Scale     │             │
│  │ • Mac M4 Optimized   │  Select  │ • Kubernetes/YARN     │             │
│  └──────────────────────┘          └──────────────────────┘             │
│                                                                            │
│  ┌────────────────────────────────────────────────────────────┐          │
│  │                    PIPELINE COMPONENTS                       │          │
│  │  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌──────────────┐│          │
│  │  │ Chunking │→│ Transform │→│ Validate │→│ Anonymize    ││          │
│  │  └──────────┘ └───────────┘ └──────────┘ └──────────────┘│          │
│  └────────────────────────────────────────────────────────────┘          │
└───────────────────────────────────────────────────────────────────────────┘
                                     │
┌──────────────────────────────────────┴────────────────────────────────────┐
│                          PRIVACY LAYER                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐  │
│  │PII Detection│  │ Anonymization│  │  Encryption │  │ Audit Logging│  │
│  │             │  │              │  │             │  │              │  │
│  │• Email      │  │• Hash        │  │• At Rest    │  │• All Access  │  │
│  │• Phone      │  │• Mask        │  │• In Transit │  │• Compliance  │  │
│  │• SSN        │  │• Redact      │  │• Keys Mgmt  │  │• Retention   │  │
│  │• Credit Card│  │• Synthetic   │  │             │  │              │  │
│  └─────────────┘  └──────────────┘  └─────────────┘  └──────────────┘  │
└───────────────────────────────────────────────────────────────────────────┘
                                     │
┌──────────────────────────────────────┴────────────────────────────────────┐
│                         ANALYTICS LAYER                                    │
│  ┌─────────────────┐  ┌────────────────┐  ┌───────────────────┐         │
│  │   Clustering    │  │    Quality     │  │    Hierarchy      │         │
│  │   (Embeddings)  │  │    Checks      │  │    Building       │         │
│  │                 │  │                │  │                   │         │
│  │• BERT/SentTrans │  │• Completeness  │  │• Tree Structures  │         │
│  │• K-Means        │  │• Accuracy      │  │• Graph Analysis   │         │
│  │• DBSCAN         │  │• Consistency   │  │• Relationships    │         │
│  │• Hierarchical   │  │• Timeliness    │  │                   │         │
│  └─────────────────┘  └────────────────┘  └───────────────────┘         │
└───────────────────────────────────────────────────────────────────────────┘
                                     │
┌──────────────────────────────────────┴────────────────────────────────────┐
│                        MONITORING & OBSERVABILITY                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │  Prometheus  │  │   Grafana    │  │ OpenTelemetry│  │   Logging   │ │
│  │   Metrics    │  │  Dashboards  │  │    Tracing   │  │  (JSON)     │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘ │
└───────────────────────────────────────────────────────────────────────────┘
                                     │
┌──────────────────────────────────────┴────────────────────────────────────┐
│                          DATA LAYER                                        │
│  ┌───────────┐  ┌──────────┐  ┌────────┐  ┌─────────┐  ┌──────────┐    │
│  │ PostgreSQL│  │  Redis   │  │ Kafka  │  │   S3    │  │ BigQuery │    │
│  │ (Metadata)│  │ (Cache)  │  │(Queue) │  │ (Files) │  │  (DWH)   │    │
│  └───────────┘  └──────────┘  └────────┘  └─────────┘  └──────────┘    │
└───────────────────────────────────────────────────────────────────────────┘
```

## Technology Stack

### Core Processing
- **Polars**: High-performance local processing (10-100x faster than Pandas)
- **PyArrow**: Columnar data format, zero-copy interop
- **PySpark**: Distributed processing for unlimited scale

### Privacy & Security
- **Presidio**: Microsoft's PII detection framework
- **Cryptography**: Industry-standard encryption (Fernet, AES-256)
- **BLAKE3**: Fast cryptographic hashing

### Analytics
- **Sentence Transformers**: BERT-based embeddings for clustering
- **scikit-learn**: ML algorithms (K-Means, DBSCAN, Hierarchical)
- **Great Expectations**: Data validation and quality

### Infrastructure
- **FastAPI**: Modern async web framework
- **Kubernetes**: Container orchestration
- **Docker**: Containerization with multi-stage builds
- **Terraform**: Infrastructure as Code

### Monitoring
- **Prometheus**: Metrics collection
- **Grafana**: Visualization and dashboards
- **OpenTelemetry**: Distributed tracing
- **Structured Logging**: JSON logs for analysis

### Message Queue
- **Apache Kafka**: Event streaming platform
- **Redis**: In-memory cache and pub/sub

## Deployment Modes

### 1. Local Development
```
Mac M4 ─► Polars ─► Local Storage
         (10 workers)
```

### 2. Single Server Production
```
AWS/GCP VM ─► Polars + Docker ─► Cloud Storage
            (Multi-core optimized)
```

### 3. Kubernetes Cluster
```
K8s Cluster ─► FastAPI Pods ─► Polars Workers ─► Cloud Storage
              (Auto-scaling)
```

### 4. Distributed Spark
```
K8s/YARN ─► Spark Master ─► Spark Workers ─► HDFS/S3
          (100+ nodes)
```

## Data Flow

```
INPUT DATA
    │
    ▼
┌──────────────┐
│   Ingestion  │  ◄── Validation, Schema Check
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Privacy    │  ◄── PII Detection, Anonymization
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Transformation│ ◄── Map, Filter, Aggregate
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Analytics  │  ◄── Clustering, Quality Check
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Storage    │  ◄── Parquet, Compression
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Audit Log   │  ◄── Complete Trail
└──────────────┘
```

## Scalability

| Data Size | Mode | Workers | Memory | Time (est) |
|-----------|------|---------|--------|------------|
| < 1 GB    | Local Polars | 10 | 4 GB | seconds |
| 1-10 GB   | Local Polars | 10 | 16 GB | minutes |
| 10-100 GB | K8s Polars | 50 | 200 GB | 10-30 min |
| 100+ GB   | PySpark | 100+ | 1+ TB | hours |
| 1+ PB     | PySpark | 1000+ | 10+ TB | hours |

## Security Features

1. **Authentication**: OAuth2, API Keys, mTLS
2. **Authorization**: RBAC, Policy-based access control
3. **Encryption**: At-rest (AES-256), In-transit (TLS 1.3)
4. **PII Protection**: Automatic detection and anonymization
5. **Audit Logging**: Complete trail of all data access
6. **Secrets Management**: Vault, AWS Secrets Manager, K8s Secrets
7. **Network Security**: Network policies, service mesh
8. **Vulnerability Scanning**: Trivy, Snyk, Dependabot

## Compliance

- **GDPR**: Right to be forgotten, data portability, consent management
- **CCPA**: Data access, deletion, opt-out
- **HIPAA**: PHI protection, audit trails, encryption
- **SOC 2**: Access control, logging, monitoring
- **ISO 27001**: Information security management

## Performance Optimizations

### Mac M4 Specific
1. **Optimal Workers**: 10 (12 cores - 2 for system)
2. **Fork Context**: Faster multiprocessing on macOS
3. **Accelerate Framework**: Apple's optimized BLAS/LAPACK
4. **Native ARM64**: All dependencies support Apple Silicon

### General
1. **Chunk Processing**: Memory-efficient streaming
2. **Compression**: ZSTD for 2-3x space savings
3. **Caching**: Redis for frequently accessed data
4. **Connection Pooling**: Database connection reuse
5. **Async I/O**: Non-blocking operations

## Disaster Recovery

1. **Automated Backups**: Daily database and data backups
2. **Point-in-Time Recovery**: PostgreSQL WAL archiving
3. **Multi-Region**: Active-passive or active-active
4. **Checkpointing**: Resume failed jobs from last checkpoint
5. **Health Checks**: Automatic pod restart on failure

## Cost Optimization

1. **Spot Instances**: 70% cost savings for batch workloads
2. **Autoscaling**: Scale to zero when idle
3. **Compression**: Reduce storage costs by 3x
4. **Tiered Storage**: Hot/warm/cold data separation
5. **Right-Sizing**: VPA for optimal resource allocation
