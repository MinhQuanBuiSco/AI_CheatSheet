# 📊 Monitoring Guide

**Anthropic-Level Observability Stack**

This guide covers the comprehensive monitoring infrastructure for the data processing system, designed for production-grade observability, privacy-first metrics, and research-focused insights.

---

## 🎯 Overview

The monitoring stack provides:

- **Metrics Collection**: Prometheus scraping 40+ metric types
- **Visualization**: Grafana dashboards for real-time insights
- **Alerting**: Production-ready alert rules for critical conditions
- **Privacy-First**: No PII leakage in metrics
- **Research-Focused**: Data quality, processing accuracy, audit tracking

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Grafana Dashboards                    │
│     [Overview] [Pipeline] [Privacy] [Resources]         │
└───────────────────────────┬─────────────────────────────┘
                            │ PromQL queries
┌───────────────────────────┴─────────────────────────────┐
│              Prometheus (Metrics Storage)                │
│  - 15s scrape interval                                   │
│  - 7 day retention                                      │
│  - Kubernetes service discovery                         │
└──┬─────┬─────┬─────┬─────┬─────────────────────────────┘
   │     │     │     │     │
   │     │     │     │     └─ Custom Exporters
   │     │     │     └─────── Kubernetes Metrics
   │     │     └──────────── MinIO Metrics
   │     └────────────────── Spark Cluster Metrics
   └──────────────────────── API /metrics Endpoint
```

---

## 🚀 Quick Start

### Access the Dashboards

After running `bash scripts/deploy.sh`:

```bash
# Open Grafana
open http://localhost:3000

# Login (default credentials)
Username: admin
Password: admin
```

**Default Dashboard**: Overview dashboard opens automatically

### Access Prometheus

```bash
# Open Prometheus UI
open http://localhost:9090

# Query examples
- records_processed_total
- rate(records_processed_total[5m])
- histogram_quantile(0.95, rate(processing_duration_seconds_bucket[5m]))
```

---

## 📊 Metrics Categories

### 1. Processing Metrics

**Purpose**: Track pipeline performance and throughput

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `records_processed_total` | Counter | `stage`, `status` | Total records processed (success/failed) |
| `processing_duration_seconds` | Histogram | `stage` | Time spent processing by stage |
| `batch_size_records` | Histogram | `stage` | Records per batch distribution |
| `pipeline_queue_depth` | Gauge | `stage` | Items waiting in pipeline queue |
| `throughput_records_per_second` | Gauge | `stage` | Processing throughput |

**Example Queries**:
```promql
# Processing rate (records/sec)
sum(rate(records_processed_total{status="success"}[5m])) by (stage)

# P95 latency
histogram_quantile(0.95, rate(processing_duration_seconds_bucket[5m]))

# Error rate
rate(records_processed_total{status="failed"}[5m])
/ rate(records_processed_total[5m])
```

---

### 2. Privacy & Audit Metrics ⭐ CRITICAL

**Purpose**: Track data privacy operations and compliance

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `pii_entities_detected_total` | Counter | `entity_type` | PII detected by type (email, phone, name, ssn) |
| `anonymization_operations_total` | Counter | `method`, `status` | Anonymization ops (hash/mask/redact/synthetic) |
| `audit_log_writes_total` | Counter | `operation`, `status` | Audit log entries (read/write/delete/export) |
| `privacy_policy_violations_total` | Counter | `violation_type` | Privacy violations detected |
| `encryption_operations_total` | Counter | `direction`, `status` | Encryption/decryption operations |

**Example Queries**:
```promql
# PII detection rate
sum(rate(pii_entities_detected_total[10m])) by (entity_type)

# Anonymization success rate
rate(anonymization_operations_total{status="success"}[5m])
/ rate(anonymization_operations_total[5m])

# Privacy violations (should be 0)
sum(privacy_policy_violations_total)
```

**⚠️ ALERTS**:
- `PrivacyPolicyViolation`: Any violation triggers immediate alert
- `AnonymizationFailures`: >1 failure/sec for 5m
- `AuditLogWriteFailures`: Any failure triggers alert

---

### 3. Data Quality Metrics

**Purpose**: Track research data quality and accuracy

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `data_quality_score` | Gauge | `dataset` | Overall quality score (0-1) |
| `schema_validation_failures_total` | Counter | `field`, `error_type` | Schema validation failures |
| `duplicate_records_total` | Counter | `dedup_method` | Duplicate records detected |
| `data_freshness_seconds` | Gauge | `source` | Age of most recent data |

**Example Queries**:
```promql
# Quality score (should be >0.7)
data_quality_score

# Validation failure rate
rate(schema_validation_failures_total[10m])

# Data staleness
data_freshness_seconds / 3600  # Convert to hours
```

---

### 4. Storage Metrics (MinIO/S3)

**Purpose**: Track object storage operations

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `storage_operations_total` | Counter | `operation`, `status` | Storage ops (upload/download/delete/list) |
| `storage_bytes_transferred_total` | Counter | `direction` | Bytes transferred (upload/download) |
| `storage_latency_seconds` | Histogram | `operation` | Storage operation latency |
| `storage_objects_total` | Gauge | `bucket` | Total objects in storage |

**Example Queries**:
```promql
# Upload rate (bytes/sec)
rate(storage_bytes_transferred_total{direction="upload"}[5m])

# P95 storage latency
histogram_quantile(0.95, rate(storage_latency_seconds_bucket[5m]))

# Storage error rate
rate(storage_operations_total{status="failed"}[5m])
```

---

### 5. Resource Metrics

**Purpose**: Monitor system resource utilization

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `cpu_usage_percent` | Gauge | - | CPU usage percentage |
| `memory_usage_bytes` | Gauge | `type` | Memory usage (RSS, VMS) |
| `open_file_descriptors` | Gauge | - | Open file descriptors |
| `disk_io_bytes_total` | Counter | `direction` | Disk I/O (read/write) |

**Example Queries**:
```promql
# CPU usage
cpu_usage_percent

# Memory usage (GB)
memory_usage_bytes{type="rss"} / 1024 / 1024 / 1024

# Open files
open_file_descriptors
```

---

### 6. API Metrics

**Purpose**: Track HTTP API performance

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `http_requests_total` | Counter | `method`, `endpoint`, `status_code` | Total HTTP requests |
| `http_request_duration_seconds` | Histogram | `method`, `endpoint` | Request latency |
| `http_requests_in_flight` | Gauge | - | Concurrent requests |

**Example Queries**:
```promql
# Request rate
rate(http_requests_total[5m])

# P95 API latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate
rate(http_requests_total{status_code=~"5.."}[5m])
/ rate(http_requests_total[5m])
```

---

## 📈 Grafana Dashboards

### Overview Dashboard

**URL**: http://localhost:3000/d/overview

**Panels**:
1. **System Overview** (Row)
   - Processing Rate (records/sec)
   - Total Records Processed
   - Error Rate (%)
   - PII Entities Detected

2. **Processing Performance** (Row)
   - Throughput by Stage (graph)
   - Processing Latency Percentiles (graph)

3. **Privacy & Data Quality** (Row)
   - PII Detection Rate by Type (graph)
   - Data Quality Score (graph)

4. **Resource Utilization** (Row)
   - CPU Usage (graph)
   - Memory Usage (graph)
   - Storage Operations (graph)

**Use Cases**:
- Quick health check
- System performance at a glance
- Identify anomalies

---

### Privacy Dashboard

**URL**: http://localhost:3000/d/privacy

**Panels**:
1. **PII Detection & Anonymization** (Row)
   - PII Entities Detected (pie chart)
   - Anonymization Operations by Method (graph)

2. **Audit & Compliance** (Row)
   - Audit Log Writes (graph)
   - Privacy Policy Violations (stat - should be 0)

3. **Privacy Operations Health** (Row)
   - Anonymization Failure Rate (stat)
   - Encryption Operations (stat)
   - Audit Log Write Failures (stat - should be 0)

**Use Cases**:
- Privacy compliance monitoring
- Audit trail verification
- PII detection analysis

---

## 🔔 Alert Rules

### Critical Alerts (Immediate Action Required)

| Alert | Condition | Duration | Description |
|-------|-----------|----------|-------------|
| `PrivacyPolicyViolation` | >0 violations | 1m | Privacy policy violated |
| `AnonymizationFailures` | >1 failure/sec | 5m | Anonymization operations failing |
| `AuditLogWriteFailures` | >0 failures | 1m | Audit logs not being written |
| `HighAPIErrorRate` | >5% errors | 5m | API error rate too high |

### Warning Alerts (Investigation Needed)

| Alert | Condition | Duration | Description |
|-------|-----------|----------|-------------|
| `HighProcessingLatency` | P95 >60s | 5m | Processing taking too long |
| `LowThroughput` | <1000 records/sec | 10m | Processing throughput low |
| `HighFailureRate` | >5% failures | 5m | Too many record failures |
| `LowDataQualityScore` | <0.7 | 15m | Data quality degraded |
| `HighCPUUsage` | >90% | 10m | CPU saturation |
| `HighMemoryUsage` | >8GB | 5m | Memory pressure |

### Info Alerts (Monitoring)

| Alert | Condition | Duration | Description |
|-------|-----------|----------|-------------|
| `HighPIIDetectionRate` | >50% of records | 15m | Unusually high PII rate |
| `StaleData` | >24h old | 1h | Data freshness issue |

---

## 🛠 Common Operations

### Check Metric Value

```bash
# Via curl
curl http://localhost:8000/metrics | grep records_processed_total

# Via Prometheus API
curl 'http://localhost:9090/api/v1/query?query=records_processed_total'
```

### View Active Alerts

```bash
# In Prometheus UI
open http://localhost:9090/alerts

# Via API
curl http://localhost:9090/api/v1/alerts
```

### Hot-Reload Prometheus Config

```bash
# After editing prometheus-config.yaml
kubectl apply -f deployment/monitoring/prometheus/prometheus-config.yaml

# Trigger reload
curl -X POST http://localhost:9090/-/reload
```

### Add Custom Dashboard

1. Create dashboard JSON in `deployment/monitoring/grafana/dashboards/custom.json`
2. Update `dashboards-configmap.yaml` to include it
3. Apply: `kubectl apply -f deployment/monitoring/grafana/dashboards-configmap.yaml`
4. Restart Grafana: `kubectl rollout restart deployment/grafana -n data-processing`

---

## 🔍 Troubleshooting

### No Metrics in Grafana

**Check Prometheus targets**:
```bash
# View targets
open http://localhost:9090/targets

# Should see:
# - data-processing-api (UP)
# - spark-master (UP)
# - prometheus (UP)
```

**If target is DOWN**:
```bash
# Check pod logs
kubectl logs -n data-processing -l component=api --tail=50

# Check service
kubectl get svc -n data-processing data-processing-api
```

### Missing Labels in Metrics

**Ensure metric labels are set** when recording metrics in code:

```python
# ❌ Wrong
metrics.records_processed.inc(10)

# ✅ Correct
metrics.records_processed.labels(stage="processing", status="success").inc(10)
```

### High Memory Usage in Prometheus

**Reduce retention** in `prometheus-deployment.yaml`:
```yaml
args:
  - '--storage.tsdb.retention.time=3d'  # Reduce from 7d to 3d
```

### Dashboards Not Loading

```bash
# Check Grafana logs
kubectl logs -n data-processing -l app=grafana --tail=50

# Verify dashboard ConfigMap
kubectl get configmap grafana-dashboards -n data-processing -o yaml
```

---

## 📊 Best Practices

### 1. Privacy-First Metrics

**✅ DO**:
- Use aggregated counts, not individual records
- Track PII detection rates, not actual PII values
- Log hashed user IDs, not plain text IDs

**❌ DON'T**:
- Include any PII in metric labels
- Log sensitive data in metric values
- Export audit logs containing user data

### 2. Cardinality Management

**✅ DO**:
- Use low-cardinality labels (stage, status, method)
- Limit unique label values (<100 per label)
- Use histograms for latency tracking

**❌ DON'T**:
- Use high-cardinality labels (user_id, job_id, timestamp)
- Create unbounded label values
- Use gauges for constantly increasing values

### 3. Alert Tuning

**✅ DO**:
- Set appropriate thresholds based on baselines
- Use `for` duration to avoid flapping
- Include actionable context in annotations

**❌ DON'T**:
- Alert on every minor issue
- Set unrealistic SLOs
- Ignore repeated alerts

---

## 🎯 For CLIO Demo

**Highlight These Features**:

1. **Privacy-First**: Show PII detection metrics without exposing actual PII
2. **Production-Grade**: 40+ metrics, comprehensive dashboards, alert rules
3. **Research-Focused**: Data quality scores, validation failures, freshness
4. **Distributed Systems**: Spark cluster monitoring, storage metrics
5. **Full Observability**: Metrics + Logs + Distributed Tracing (via labels)

**Demo Flow**:
```bash
# 1. Deploy with monitoring
bash scripts/deploy.sh

# 2. Open Grafana
open http://localhost:3000

# 3. Run test to generate metrics
bash scripts/test.sh

# 4. Show live metrics updating in dashboard

# 5. Check specific metric
curl http://localhost:8000/metrics | grep pii_entities_detected

# 6. View alerts (should all be green)
open http://localhost:9090/alerts
```

---

## 📚 Additional Resources

- **Prometheus Documentation**: https://prometheus.io/docs/
- **Grafana Documentation**: https://grafana.com/docs/
- **PromQL Tutorial**: https://prometheus.io/docs/prometheus/latest/querying/basics/
- **Dashboard Best Practices**: https://grafana.com/docs/grafana/latest/best-practices/

---

## 🆘 Support

For issues or questions:

1. Check this guide's Troubleshooting section
2. Review Prometheus targets: http://localhost:9090/targets
3. Check pod logs: `kubectl logs -n data-processing -l app=prometheus`
4. Verify metrics endpoint: `curl http://localhost:8000/metrics`
