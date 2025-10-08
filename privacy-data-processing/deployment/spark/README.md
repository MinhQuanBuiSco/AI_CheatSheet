# Spark Logging Configuration

## 📝 Log Locations

### **Master Logs:**
```bash
# File logs (persistent)
logs/spark-master/spark.log

# Container logs (stdout/stderr)
docker logs spark-master

# Real-time tail
docker logs -f spark-master
```

### **Worker Logs:**
```bash
# File logs (persistent)
logs/spark-workers/spark.log

# Container logs (all workers)
docker-compose logs -f spark-worker

# Specific worker
docker logs <worker-container-id>
```

---

## 🔍 How to View Logs

### **1. View Master Logs**
```bash
# Recent logs
tail -f logs/spark-master/spark.log

# Search for errors
grep ERROR logs/spark-master/spark.log

# Filter by job ID
grep "job-12345" logs/spark-master/spark.log
```

### **2. View Worker Logs**
```bash
# All worker logs
tail -f logs/spark-workers/spark.log

# Only errors
grep ERROR logs/spark-workers/spark.log
```

### **3. View Application Logs (PySpark Jobs)**
```bash
# From Spark UI
open http://localhost:8080

# Click on running application > Executors > Logs
# Shows stdout/stderr for each executor
```

---

## 📊 Log Levels

Current configuration (`log4j.properties`):

| Component | Level | Description |
|-----------|-------|-------------|
| **Root** | INFO | General Spark logs |
| **Master** | INFO | Master node operations |
| **Worker** | INFO | Worker node operations |
| **Executor** | INFO | Task execution |
| **Scheduler** | INFO | Job scheduling |
| **Hadoop** | WARN | Reduce Hadoop verbosity |
| **Parquet** | WARN | Reduce Parquet verbosity |

### **Change Log Level:**

Edit `deployment/spark/log4j.properties`:
```properties
# For debugging
log4j.logger.org.apache.spark=DEBUG

# For production
log4j.logger.org.apache.spark=WARN
```

Then restart:
```bash
docker-compose restart spark-master spark-worker
```

---

## 🐛 Common Debug Scenarios

### **1. Job Failed - Find the Error**
```bash
# Search for exceptions in master logs
grep -A 10 "Exception" logs/spark-master/spark.log

# Check worker logs for task failures
grep -A 10 "ERROR" logs/spark-workers/spark.log
```

### **2. Slow Performance - Find Bottleneck**
```bash
# Check executor allocation
grep "Registering executor" logs/spark-master/spark.log

# Check task completion times
grep "Finished task" logs/spark-workers/spark.log
```

### **3. Connection Issues**
```bash
# Check if workers connected to master
grep "Registering worker" logs/spark-master/spark.log

# Check worker registration attempts
grep "Connecting to master" logs/spark-workers/spark.log
```

---

## 🎯 CLIO Demo Tips

### **Monitor a Processing Job:**
```bash
# Terminal 1: Watch master logs
tail -f logs/spark-master/spark.log | grep "job-"

# Terminal 2: Watch worker logs
tail -f logs/spark-workers/spark.log | grep "task"

# Terminal 3: Spark UI
open http://localhost:8080
```

### **Show Job Progress:**
```bash
# Count completed tasks
grep "Finished task" logs/spark-workers/spark.log | wc -l

# Show stages
grep "Submitting.*stage" logs/spark-master/spark.log
```

---

## 🔧 Troubleshooting

### **No Logs Appearing:**
```bash
# Check log directories exist
ls -la logs/spark-master/
ls -la logs/spark-workers/

# Check permissions
chmod -R 777 logs/  # Dev only!

# Restart Spark
docker-compose restart spark-master spark-worker
```

### **Log Files Too Large:**
```bash
# Logs auto-rotate at 100MB (10 backups)
# Manual cleanup:
rm logs/spark-master/spark.log.*
rm logs/spark-workers/spark.log.*
```

---

## 📈 Production Best Practices

1. **Enable structured logging** - Use JSON format for parsing
2. **Centralized logging** - Ship to ELK/Splunk/Datadog
3. **Log retention** - Keep 7-30 days depending on compliance
4. **Alerting** - Monitor ERROR logs with Prometheus alerts
5. **Trace IDs** - Add correlation IDs for distributed tracing

---

## 🚀 Quick Commands

```bash
# Start Spark with logging
docker-compose up -d spark-master spark-worker

# View all Spark logs
docker-compose logs -f spark-master spark-worker

# View just errors
docker-compose logs spark-master spark-worker | grep ERROR

# Clear all logs
rm -rf logs/spark-*/*

# Restart with fresh logs
docker-compose restart spark-master spark-worker
```
