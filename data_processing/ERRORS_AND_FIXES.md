# 🐛 Errors Encountered and Fixes Applied

This document details all errors encountered during Spark cluster setup and their solutions.

---

## ❌ Error 1: No FileSystem for scheme "s3"

### Error Message
```
org.apache.hadoop.fs.UnsupportedFileSystemException: No FileSystem for scheme "s3"
at org.apache.hadoop.fs.FileSystem.getFileSystemClass(FileSystem.java:3443)
```

### Root Cause
Spark doesn't include Hadoop AWS libraries by default. When trying to read/write S3 paths (or MinIO using S3 protocol), Spark cannot find the required filesystem implementation.

### Impact
- ❌ Cannot read from `s3://data-processing/input/`
- ❌ Cannot write to `s3://data-processing/output/`
- ❌ Jobs fail immediately on S3 path access

### Solution
**Added Hadoop AWS dependencies**

**File**: `src/data_processing/distributed/spark_engine.py`
```python
# S3 configuration with local hadoop-aws JARs (pre-downloaded in Docker image)
conf.set("spark.jars", "/app/jars/hadoop-aws-3.3.4.jar,/app/jars/aws-java-sdk-bundle-1.12.262.jar")
```

**File**: `Dockerfile` (lines 104-109)
```dockerfile
# Download Hadoop AWS JARs for Spark S3 support
RUN curl -L -o /app/jars/hadoop-aws-3.3.4.jar \
    https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar && \
    curl -L -o /app/jars/aws-java-sdk-bundle-1.12.262.jar \
    https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar
```

**File**: `src/data_processing/distributed/distributed_pipeline.py` (lines 232-234)
```python
# Convert s3:// to s3a:// for Spark
input_path_str = str(input_path).replace("s3://", "s3a://")
output_path_str = str(output_path).replace("s3://", "s3a://")
```

---

## ❌ Error 2: Java Gateway Process Exited - Ivy Cache Permissions

### Error Message
```
Exception in thread "main" java.lang.reflect.UndeclaredThrowableException
...
Caused by: java.io.FileNotFoundException: /home/appuser/.ivy2/cache/resolved-...xml
(No such file or directory)
```

### Root Cause
When using `spark.jars.packages`, Spark tries to download JARs at runtime using Apache Ivy. The download cache is stored in `~/.ivy2/`, but:
1. The directory doesn't exist
2. The container runs as non-root user `appuser` who may not have write permissions
3. Runtime downloads add latency and can fail in restricted networks

### Impact
- ❌ Spark session creation fails
- ❌ No executors can start
- ❌ Job submission fails immediately

### First Attempt (Failed)
```dockerfile
# Created .ivy2 directory with permissions - DIDN'T WORK
RUN mkdir -p /home/appuser/.ivy2 && chown -R appuser:appuser /home/appuser/.ivy2
```
**Why it failed**: Ivy still had issues with concurrent access and cache locking.

### Second Attempt (Failed)
```dockerfile
# Pre-downloaded JARs with PySpark - DIDN'T WORK
RUN python3 -c "from pyspark.sql import SparkSession; ..."
```
**Why it failed**: PySpark downloaded to different cache location, still had runtime issues.

### Final Solution ✅
**Pre-download JARs with `curl` and use local file paths**

**File**: `Dockerfile`
```dockerfile
RUN curl -L -o /app/jars/hadoop-aws-3.3.4.jar \
    https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar && \
    curl -L -o /app/jars/aws-java-sdk-bundle-1.12.262.jar \
    https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar
```

**File**: `spark_engine.py`
```python
# Use local JARs instead of packages
conf.set("spark.jars", "/app/jars/hadoop-aws-3.3.4.jar,/app/jars/aws-java-sdk-bundle-1.12.262.jar")
# NOT: conf.set("spark.jars.packages", "org.apache.hadoop:hadoop-aws:3.3.4,...")
```

---

## ❌ Error 3: 403 Forbidden - Invalid Access Key

### Error Message
```
com.amazonaws.services.s3.model.AmazonS3Exception: The AWS Access Key Id you provided
does not exist in our records.
(Service: Amazon S3; Status Code: 403; Error Code: InvalidAccessKeyId)
```

### Root Cause
**Environment variables don't propagate to Spark executors!**

The API pod has environment variables:
- `AWS_ACCESS_KEY_ID=minioadmin`
- `AWS_SECRET_ACCESS_KEY=minioadmin`
- `AWS_ENDPOINT_URL=http://minio:9000`

But Spark executors run on **worker nodes** in separate pods, which don't have these environment variables. The executors inherit Spark configuration from the driver, not the environment.

### Impact
- ✅ Spark session creates successfully (driver has credentials)
- ✅ Driver can read input file metadata
- ❌ Executors fail when trying to read actual data
- ❌ All tasks fail with 403 errors

### Solution
**Pass credentials through Spark configuration**

**File**: `src/data_processing/api/main.py` (lines 478-496)
```python
import os

# Create Spark config with S3 credentials from environment
spark_config = SparkConfig(
    app_name=f"api-job-{job_id}",
    master=request.spark_master,
    executor_memory=request.executor_memory,
    driver_memory=request.driver_memory,
    executor_cores=request.executor_cores,
    num_executors=request.num_executors,
    # ✅ Pass credentials from environment to Spark config
    aws_access_key=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    s3_endpoint=os.environ.get('AWS_ENDPOINT_URL'),
)
```

**File**: `spark_engine.py` (lines 111-118)
```python
if self.config.aws_access_key:
    # These configs are sent to all executors
    conf.set("spark.hadoop.fs.s3a.access.key", self.config.aws_access_key)
    conf.set("spark.hadoop.fs.s3a.secret.key", self.config.aws_secret_key)
    conf.set("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    conf.set("spark.hadoop.fs.s3a.path.style.access", "true")
    if self.config.s3_endpoint:
        conf.set("spark.hadoop.fs.s3a.endpoint", self.config.s3_endpoint)
```

---

## ❌ Error 4: UnknownHostException - Driver Hostname Not Resolvable

### Error Message
```
java.net.UnknownHostException: data-processing-api-5cc9b9db75-nn4bc
...
Caused by: Failed to connect to data-processing-api-5cc9b9db75-nn4bc:33105
```

### Root Cause
**Kubernetes pod hostnames are not resolvable across namespaces!**

Spark driver (in API pod) uses its pod hostname by default:
- Pod hostname: `data-processing-api-5cc9b9db75-nn4bc`
- Driver tells executors: "Connect to me at `data-processing-api-5cc9b9db75-nn4bc:33105`"
- Executors (on worker nodes): "Who is `data-processing-api-5cc9b9db75-nn4bc`?? DNS lookup failed!"

In Kubernetes:
- ✅ Service names are resolvable: `spark-master.data-processing.svc.cluster.local`
- ✅ Pod IPs are routable: `10.244.0.54`
- ❌ Pod hostnames are NOT resolvable across pods: `data-processing-api-5cc9b9db75-nn4bc`

### Impact
- ✅ Spark master registers application
- ✅ Master assigns executors to workers
- ✅ Workers launch executor processes
- ❌ Executors cannot connect back to driver
- ❌ Executors exit immediately with code 1
- ❌ Master keeps retrying (100+ failed executor attempts)

### Solution
**Use pod IP instead of hostname for driver**

**Step 1**: Add POD_IP environment variable using Kubernetes Downward API

**File**: `deployment/k8s/base/deployment.yaml` (lines 78-82)
```yaml
env:
  # ... other env vars ...
  # Pod IP for Spark driver networking (Kubernetes Downward API)
  - name: POD_IP
    valueFrom:
      fieldRef:
        fieldPath: status.podIP
```

**Step 2**: Configure Spark driver to use pod IP

**File**: `spark_engine.py` (lines 89-106)
```python
import os
import socket

# Driver networking for Kubernetes - use pod IP so executors can reach driver
# Get pod IP from environment (set by Kubernetes downward API) or hostname resolution
driver_host = os.environ.get('POD_IP') or socket.gethostbyname(socket.gethostname())
conf.set("spark.driver.host", driver_host)
conf.set("spark.driver.bindAddress", "0.0.0.0")
logger.info(f"Spark driver host: {driver_host}")
```

**Result**:
```
2025-10-06 14:30:32 [INFO] Spark driver host: 10.244.0.54
```

Executors now connect to: `10.244.0.54:40835` ✅

---

## 📊 Summary of All Fixes

| Error | File(s) Changed | Key Fix |
|-------|----------------|---------|
| **No S3 FileSystem** | `Dockerfile`, `spark_engine.py`, `distributed_pipeline.py` | Pre-download Hadoop AWS JARs, use `s3a://` protocol |
| **Ivy Cache Permissions** | `Dockerfile`, `spark_engine.py` | Download JARs with `curl`, use `spark.jars` not `spark.jars.packages` |
| **403 S3 Credentials** | `main.py`, `spark_engine.py` | Pass env vars to `SparkConfig`, set Hadoop S3 configs |
| **Driver Hostname** | `deployment.yaml`, `spark_engine.py` | Add `POD_IP` env, configure `spark.driver.host` |

---

## ✅ Verification

After all fixes, check:

```bash
# 1. Check Spark session created with correct config
kubectl logs -n data-processing -l component=api | grep "Spark driver host"
# Should show: Spark driver host: 10.244.0.X

# 2. Check executors connected successfully
kubectl logs -n data-processing -l component=spark-worker | grep "registered"
# Should NOT show repeated "EXITED" messages

# 3. Check S3 access works
# Submit a job and check no 403 errors in logs

# 4. Verify output in MinIO
# Job should complete and write files to s3://data-processing/output/
```

---

## 🎓 Lessons Learned

1. **Always pre-download dependencies in Docker images** - Don't rely on runtime downloads
2. **Environment variables don't propagate to Spark executors** - Use Spark configuration
3. **Pod hostnames aren't resolvable in Kubernetes** - Use pod IPs or service names
4. **Test networking thoroughly** - Driver-executor communication is critical
5. **Use `s3a://` protocol** - Not `s3://` when using Hadoop S3A filesystem
6. **Check logs at every layer** - Driver, master, worker, executor all have different views

---

## 🔗 Related Files

- **Full deployment guide**: `DEPLOYMENT_GUIDE.md`
- **Cleanup script**: `scripts/cleanup.sh`
- **Deploy script**: `scripts/deploy.sh`
- **Test script**: `scripts/test.sh`
