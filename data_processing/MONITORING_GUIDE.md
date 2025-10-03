# Monitoring Guide: Prometheus & Grafana

Complete guide for monitoring your data processing infrastructure.

## Quick Start

```bash
# 1. Make sure monitoring services are running
docker-compose ps prometheus grafana

# 2. Access Prometheus
open http://localhost:9090

# 3. Access Grafana
open http://localhost:3000
```

## Grafana Setup

### First Time Login

1. Open http://localhost:3000
2. Login with:
   - **Username**: `admin`
   - **Password**: `admin`
3. Skip or set new password

### View Dashboard

1. Click **Dashboards** (☰ menu on left)
2. Select **Data Processing API Metrics**
3. Dashboard auto-refreshes every 5 seconds

The dashboard shows:
- **API Request Rate**: Requests per second by endpoint
- **Total API Requests**: Overall request counter
- **API Response Time**: p50 and p95 latency
- **Requests by Endpoint**: Distribution pie chart

### Create Custom Dashboard

1. Click **+** → **Dashboard** → **Add visualization**
2. Select **Prometheus** datasource
3. Enter PromQL query (examples below)
4. Save dashboard

## Prometheus Queries

### Available Metrics

The API exposes these custom metrics:

```promql
# Request counters
api_requests_total{method="GET", endpoint="/health"}
api_requests_total{method="POST", endpoint="/process"}

# Response time histogram
api_duration_seconds_bucket
api_duration_seconds_count
api_duration_seconds_sum
```

### Useful Queries

#### 1. Request Rate (per second)
```promql
# All endpoints
rate(api_requests_total[5m])

# Specific endpoint
rate(api_requests_total{endpoint="/process"}[5m])

# By method
sum by(method) (rate(api_requests_total[5m]))
```

#### 2. Response Time

```promql
# 95th percentile (p95)
histogram_quantile(0.95, rate(api_duration_seconds_bucket[5m]))

# 50th percentile (p50)
histogram_quantile(0.50, rate(api_duration_seconds_bucket[5m]))

# 99th percentile (p99)
histogram_quantile(0.99, rate(api_duration_seconds_bucket[5m]))

# Average response time
rate(api_duration_seconds_sum[5m]) / rate(api_duration_seconds_count[5m])
```

#### 3. Total Requests

```promql
# Total across all endpoints
sum(api_requests_total)

# By endpoint
sum by(endpoint) (api_requests_total)

# Growth rate (requests in last 5 minutes)
increase(api_requests_total[5m])
```

#### 4. Process Metrics

```promql
# Memory usage (MB)
process_resident_memory_bytes / 1024 / 1024

# CPU time
rate(process_cpu_seconds_total[1m])

# Python GC collections
rate(python_gc_collections_total[1m])
```

## Testing Metrics

### Generate Load

```bash
# Send 100 health check requests
for i in {1..100}; do
  curl -s http://localhost:8000/health > /dev/null
  echo "Request $i sent"
done

# Send processing requests
for i in {1..10}; do
  curl -X POST http://localhost:8000/process \
    -H "Content-Type: application/json" \
    -d '{
      "input_path": "/app/data/customers_small.parquet",
      "output_path": "/app/output/test'$i'",
      "file_type": "parquet",
      "enable_pii": false
    }'
  sleep 2
done
```

### View Metrics

```bash
# Check raw metrics
curl http://localhost:8000/metrics

# Query Prometheus API
curl -s 'http://localhost:9090/api/v1/query?query=api_requests_total' | python3 -m json.tool

# Check targets status
curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool
```

## Prometheus Web UI

### Explore Metrics

1. Open http://localhost:9090
2. Click **Graph** tab
3. Enter query in expression box
4. Click **Execute**
5. View as **Table** or **Graph**

### Check Targets

1. Go to **Status** → **Targets**
2. Verify `data-processing-api` is **UP**
3. Check last scrape time

### Alerts (Optional)

Create alert rules in `deployment/prometheus/alerts.yml`:

```yaml
groups:
  - name: api_alerts
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(api_requests_total{status="500"}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} req/s"
```

## Grafana Advanced Features

### Add Panels

**Memory Usage Panel**:
```promql
process_resident_memory_bytes{job="data-processing-api"} / 1024 / 1024
```

**Request Success Rate**:
```promql
sum(rate(api_requests_total{status!~"5.."}[5m])) /
sum(rate(api_requests_total[5m])) * 100
```

**Active Workers** (shows scaled API instances):
```promql
count(up{job="data-processing-api"})
```

### Variables

Create dashboard variables for filtering:

1. Dashboard settings → Variables → Add variable
2. Name: `endpoint`
3. Query: `label_values(api_requests_total, endpoint)`
4. Use in queries: `api_requests_total{endpoint="$endpoint"}`

### Alerts in Grafana

1. Edit panel → Alert tab
2. Create alert rule
3. Set condition (e.g., "avg() of query(A) > 1000")
4. Configure notification channel (email, Slack, etc.)

## Horizontal Scaling Monitoring

Track load distribution across workers:

```bash
# Scale to 3 instances
docker-compose up -d --scale api=3

# Send requests and check which worker handles them
for i in {1..30}; do
  curl -s http://localhost:8000/ | python3 -c "import sys, json; print(json.load(sys.stdin))"
done

# View distribution in logs
docker-compose logs -f api | grep "assigned to worker"
```

**Grafana query for worker distribution**:
```promql
sum by(instance) (rate(api_requests_total[5m]))
```

## Performance Metrics

### Key Metrics to Monitor

1. **Throughput**: `rate(api_requests_total[1m])`
2. **Latency p95**: `histogram_quantile(0.95, rate(api_duration_seconds_bucket[5m]))`
3. **Error rate**: `rate(api_requests_total{status=~"5.."}[5m])`
4. **Memory**: `process_resident_memory_bytes`
5. **Active connections**: Check nginx logs

### SLOs (Service Level Objectives)

Example targets:
- **Availability**: 99.9% uptime
- **Latency**: p95 < 500ms
- **Throughput**: > 100 req/s
- **Error rate**: < 0.1%

Track in Grafana:
```promql
# Availability (last 24h)
avg_over_time(up{job="data-processing-api"}[24h]) * 100

# Error rate
sum(rate(api_requests_total{status=~"5.."}[5m])) /
sum(rate(api_requests_total[5m]))
```

## Troubleshooting

### Prometheus Not Scraping

```bash
# Check targets
curl http://localhost:9090/api/v1/targets

# Check Prometheus logs
docker-compose logs prometheus

# Verify metrics endpoint works
curl http://localhost:8000/metrics
```

### Grafana No Data

1. Check datasource: Configuration → Data Sources
2. Test connection (should be green)
3. Verify query syntax in Query Inspector
4. Check time range (top right)

### Missing Metrics

```bash
# Restart services
docker-compose restart api prometheus grafana

# Check API is exposing metrics
curl http://localhost:8000/metrics | grep api_requests

# Verify Prometheus config
docker exec data-processing-prometheus cat /etc/prometheus/prometheus.yml
```

## Production Setup

### Long-term Storage

For production, configure remote storage:

```yaml
# prometheus.yml
remote_write:
  - url: https://your-remote-storage/api/v1/write
```

### Alertmanager

Add Alertmanager for notifications:

```yaml
# docker-compose.yml
alertmanager:
  image: prom/alertmanager:latest
  ports:
    - "9093:9093"
  volumes:
    - ./deployment/prometheus/alertmanager.yml:/etc/alertmanager/alertmanager.yml
```

### Grafana Plugins

Install useful plugins:

```bash
docker exec -it data-processing-grafana grafana-cli plugins install grafana-piechart-panel
docker-compose restart grafana
```

## Next Steps

1. ✅ Open Grafana at http://localhost:3000
2. ✅ View pre-configured dashboard
3. ✅ Generate some load (process data via API)
4. ✅ Watch metrics update in real-time
5. ✅ Create custom panels for your needs
6. ✅ Set up alerts for critical metrics

## Useful Links

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- API Metrics: http://localhost:8000/metrics
- PromQL Docs: https://prometheus.io/docs/prometheus/latest/querying/basics/
- Grafana Docs: https://grafana.com/docs/
