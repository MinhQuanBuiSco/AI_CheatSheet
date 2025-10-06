"""PySpark engine for distributed processing."""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

try:
    from pyspark.sql import SparkSession, DataFrame as SparkDataFrame
    from pyspark.sql import functions as F
    from pyspark.conf import SparkConf
    SPARK_AVAILABLE = True
except ImportError:
    SPARK_AVAILABLE = False
    SparkSession = Any
    SparkDataFrame = Any


logger = logging.getLogger(__name__)


@dataclass
class SparkConfig:
    """Configuration for Spark engine."""
    app_name: str = "anthropic-data-processing"
    master: str = "local[*]"  # local[*], spark://host:port, yarn, k8s://https://...
    executor_memory: str = "4g"
    driver_memory: str = "2g"
    executor_cores: int = 2
    num_executors: int = 4
    shuffle_partitions: int = 200
    dynamic_allocation: bool = True
    adaptive_query_execution: bool = True
    # S3 configuration
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    s3_endpoint: Optional[str] = None
    # Additional Spark configs
    extra_configs: Dict[str, str] = None

    def __post_init__(self):
        if self.extra_configs is None:
            self.extra_configs = {}


class SparkEngine:
    """Manages Spark session and distributed processing."""

    def __init__(self, config: SparkConfig):
        if not SPARK_AVAILABLE:
            raise ImportError(
                "PySpark is not installed. Install with: pip install pyspark"
            )

        self.config = config
        self._spark: Optional[SparkSession] = None

    def get_session(self) -> SparkSession:
        """Get or create Spark session.

        Returns:
            Active Spark session
        """
        if self._spark is None or self._spark.sparkContext._jsc is None:
            # Create new session if none exists or if existing one is stopped
            if self._spark is not None:
                try:
                    self._spark.stop()
                except:
                    pass
            self._spark = self._create_session()
        return self._spark

    def _create_session(self) -> SparkSession:
        """Create Spark session with configuration."""
        # Stop any existing global Spark session that might be stopped
        try:
            existing = SparkSession.getActiveSession()
            if existing:
                try:
                    # Test if it's actually alive
                    existing.sparkContext.defaultParallelism
                except:
                    # Session is stopped, clear it
                    existing.stop()
                    logger.info("Stopped existing inactive Spark session")
        except:
            pass

        import os
        import socket

        conf = SparkConf()

        # Basic configs
        conf.set("spark.app.name", self.config.app_name)
        conf.set("spark.executor.memory", self.config.executor_memory)
        conf.set("spark.driver.memory", self.config.driver_memory)
        conf.set("spark.executor.cores", str(self.config.executor_cores))
        conf.set("spark.sql.shuffle.partitions", str(self.config.shuffle_partitions))

        # Driver networking for Kubernetes - use pod IP so executors can reach driver
        # Get pod IP from environment (set by Kubernetes downward API) or hostname resolution
        driver_host = os.environ.get('POD_IP') or socket.gethostbyname(socket.gethostname())
        conf.set("spark.driver.host", driver_host)
        conf.set("spark.driver.bindAddress", "0.0.0.0")
        logger.info(f"Spark driver host: {driver_host}")

        # Performance optimizations
        if self.config.dynamic_allocation:
            conf.set("spark.dynamicAllocation.enabled", "true")
            conf.set("spark.dynamicAllocation.minExecutors", "1")
            conf.set("spark.dynamicAllocation.maxExecutors", str(self.config.num_executors))

        if self.config.adaptive_query_execution:
            conf.set("spark.sql.adaptive.enabled", "true")
            conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")

        # S3 configuration with local hadoop-aws JARs (pre-downloaded in Docker image)
        conf.set("spark.jars", "/app/jars/hadoop-aws-3.3.4.jar,/app/jars/aws-java-sdk-bundle-1.12.262.jar")

        if self.config.aws_access_key:
            conf.set("spark.hadoop.fs.s3a.access.key", self.config.aws_access_key)
            conf.set("spark.hadoop.fs.s3a.secret.key", self.config.aws_secret_key)
            conf.set("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
            conf.set("spark.hadoop.fs.s3a.path.style.access", "true")
            if self.config.s3_endpoint:
                conf.set("spark.hadoop.fs.s3a.endpoint", self.config.s3_endpoint)
                conf.set("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")

        # Kryo serialization for performance
        conf.set("spark.serializer", "org.apache.spark.serializer.KryoSerializer")

        # Additional configs
        for key, value in self.config.extra_configs.items():
            conf.set(key, value)

        # Create session
        builder = SparkSession.builder.config(conf=conf)

        if self.config.master:
            builder = builder.master(self.config.master)

        spark = builder.getOrCreate()

        logger.info(f"Created Spark session: {self.config.app_name}")
        logger.info(f"Master: {self.config.master}")
        logger.info(f"Executors: {self.config.num_executors}")

        return spark

    def read_parquet(self, path: str) -> SparkDataFrame:
        """Read Parquet file(s).

        Args:
            path: Path to parquet file or directory

        Returns:
            Spark DataFrame
        """
        spark = self.get_session()
        return spark.read.parquet(path)

    def read_csv(self, path: str, **options) -> SparkDataFrame:
        """Read CSV file(s).

        Args:
            path: Path to CSV file or directory
            **options: Additional read options

        Returns:
            Spark DataFrame
        """
        spark = self.get_session()
        return spark.read.csv(path, **options)

    def read_json(self, path: str) -> SparkDataFrame:
        """Read JSON file(s).

        Args:
            path: Path to JSON file or directory

        Returns:
            Spark DataFrame
        """
        spark = self.get_session()
        return spark.read.json(path)

    def write_parquet(
        self,
        df: SparkDataFrame,
        path: str,
        mode: str = "overwrite",
        partition_by: Optional[List[str]] = None,
        compression: str = "snappy",
    ) -> None:
        """Write DataFrame to Parquet.

        Args:
            df: Spark DataFrame
            path: Output path
            mode: Write mode (overwrite, append, ignore, error)
            partition_by: Columns to partition by
            compression: Compression codec
        """
        writer = df.write.mode(mode).option("compression", compression)

        if partition_by:
            writer = writer.partitionBy(*partition_by)

        writer.parquet(path)
        logger.info(f"Wrote DataFrame to {path}")

    def process_in_batches(
        self,
        df: SparkDataFrame,
        batch_size: int,
        process_func: callable,
    ) -> SparkDataFrame:
        """Process DataFrame in batches using UDF.

        Args:
            df: Input DataFrame
            batch_size: Records per batch
            process_func: Function to apply to each batch

        Returns:
            Processed DataFrame
        """
        # This is a placeholder - actual implementation would use
        # mapPartitions or pandas UDFs for efficiency
        return df.transform(process_func)

    def optimize_shuffle(self, df: SparkDataFrame, num_partitions: Optional[int] = None) -> SparkDataFrame:
        """Optimize DataFrame partitioning.

        Args:
            df: Input DataFrame
            num_partitions: Target number of partitions

        Returns:
            Repartitioned DataFrame
        """
        if num_partitions is None:
            num_partitions = self.config.shuffle_partitions

        current_partitions = df.rdd.getNumPartitions()

        if current_partitions < num_partitions:
            return df.repartition(num_partitions)
        else:
            return df.coalesce(num_partitions)

    def cache_dataframe(self, df: SparkDataFrame) -> SparkDataFrame:
        """Cache DataFrame in memory.

        Args:
            df: DataFrame to cache

        Returns:
            Cached DataFrame
        """
        return df.cache()

    def uncache_dataframe(self, df: SparkDataFrame) -> None:
        """Remove DataFrame from cache.

        Args:
            df: DataFrame to uncache
        """
        df.unpersist()

    def get_stats(self) -> Dict[str, Any]:
        """Get Spark session statistics.

        Returns:
            Dictionary of stats
        """
        spark = self.get_session()
        sc = spark.sparkContext

        # Get active jobs (API changed in PySpark 3.5)
        try:
            active_jobs = len(sc.statusTracker().getActiveJobIds())
        except AttributeError:
            # Fallback for different PySpark versions
            active_jobs = 0

        return {
            "app_id": sc.applicationId,
            "app_name": sc.appName,
            "master": sc.master,
            "default_parallelism": sc.defaultParallelism,
            "active_jobs": active_jobs,
        }

    def stop(self) -> None:
        """Stop Spark session."""
        if self._spark:
            self._spark.stop()
            self._spark = None
            logger.info("Stopped Spark session")
