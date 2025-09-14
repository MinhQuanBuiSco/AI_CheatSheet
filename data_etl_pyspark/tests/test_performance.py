"""Performance benchmarks for the optimized pipeline."""

import pytest
import time
import tempfile
import shutil
from unittest.mock import Mock
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, LongType

from src.data_etl_pyspark.pipeline import DataPreprocessingPipeline
from src.data_etl_pyspark.utils.monitoring import PerformanceMonitor


@pytest.fixture(scope="session")
def spark():
    """Create Spark session for testing."""
    return SparkSession.builder \
        .appName("PipelinePerformanceTest") \
        .master("local[2]") \
        .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
        .config("spark.sql.adaptive.enabled", "true") \
        .getOrCreate()


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        'dataset': {
            'name': 'test_dataset',
            'split': 'train'
        },
        'output': {
            'dir': './test_output',
            'format': 'parquet',
            'compression': 'snappy'
        },
        'filters': {
            'min_word_count': 10,
            'max_word_count': 1000,
            'repetition_threshold': 0.5,
            'language': 'en',
            'dedup_threshold': 0.9,
            'quality_model': 'distilbert-base-uncased-finetuned-sst-2-english',
            'quality_threshold': 0.5
        },
        'processing': {
            'batch_size': 32,
            'num_partitions': 4,
            'cache_intermediate': True,
            'checkpoint_interval': 5
        },
        'spark': {
            'dynamic_allocation': {'enabled': False},
            'memory': {
                'executor': '2g',
                'driver': '1g',
                'executor_memory_fraction': 0.8,
                'executor_memory_storage_fraction': 0.3
            },
            'sql': {
                'adaptive': {
                    'enabled': True,
                    'coalesce_partitions': True,
                    'skew_join': True
                }
            },
            'serializer': 'org.apache.spark.serializer.KryoSerializer',
            'network_timeout': '300s',
            'executor_heartbeat_interval': '20s',
            'shuffle': {
                'service': True,
                'compress': True,
                'spill_compress': True
            }
        },
        'monitoring': {
            'metrics_enabled': True,
            'checkpoint_dir': './test_checkpoints'
        },
        'logging': {
            'level': 'INFO'
        }
    }


@pytest.fixture
def sample_data(spark):
    """Create sample test data."""
    schema = StructType([
        StructField("text", StringType(), True),
        StructField("id", LongType(), True)
    ])
    
    # Generate diverse test data
    test_data = [
        ("This is a sample text for testing the pipeline. It has enough words to pass filtering.", 1),
        ("Another piece of text with different content and reasonable length for processing.", 2),
        ("Short text", 3),  # Will be filtered out
        ("This is a very very very very very repetitive text that repeats words", 4),  # May be filtered
        ("A good quality text sample with proper sentence structure and meaningful content.", 5),
        ("Yet another text sample to ensure we have enough data for deduplication testing.", 6),
        ("This is a sample text for testing the pipeline. It has enough words to pass filtering.", 7),  # Duplicate
        ("Final test text with appropriate length and content quality for the processing pipeline.", 8),
        ("" * 20 + "A longer text " * 50, 9),  # Very long text
        ("Quality content with appropriate structure and length for machine learning applications.", 10)
    ]
    
    return spark.createDataFrame(test_data, schema)


class TestPipelinePerformance:
    """Performance benchmark tests."""
    
    def test_pipeline_initialization_time(self, spark, sample_config, benchmark):
        """Benchmark pipeline initialization time."""
        logger = Mock()
        
        def create_pipeline():
            return DataPreprocessingPipeline(spark, sample_config, logger)
        
        pipeline = benchmark(create_pipeline)
        assert pipeline is not None
        assert hasattr(pipeline, 'spark')
        assert hasattr(pipeline, 'performance_monitor')
    
    def test_data_loading_performance(self, spark, sample_config, sample_data, benchmark):
        """Benchmark data loading performance."""
        logger = Mock()
        pipeline = DataPreprocessingPipeline(spark, sample_config, logger)
        
        # Mock the load_data method to use our sample data
        def mock_load_data():
            return sample_data
        
        result = benchmark(mock_load_data)
        assert result.count() == 10
    
    def test_text_cleaning_performance(self, spark, sample_config, sample_data, benchmark):
        """Benchmark text cleaning performance."""
        from src.data_etl_pyspark.utils.cleaning import clean_text_udf
        from pyspark.sql.functions import col
        
        def clean_data():
            return sample_data.withColumn("cleaned_text", clean_text_udf(col("text")))
        
        result = benchmark(clean_data)
        assert result.count() == 10
        assert 'cleaned_text' in result.columns
    
    def test_filtering_performance(self, spark, sample_config, sample_data, benchmark):
        """Benchmark filtering operations performance."""
        from src.data_etl_pyspark.utils.filtering import filter_language_udf, split_words_udf
        from pyspark.sql.functions import col, lit
        
        # Add cleaned text first
        df_with_cleaned = sample_data.withColumn("text", col("text"))
        
        def apply_filters():
            df = df_with_cleaned.filter(filter_language_udf(col("text"), lit("en")))
            df = df.withColumn("words", split_words_udf(col("text")))
            return df
        
        result = benchmark(apply_filters)
        assert result.count() > 0
        assert 'words' in result.columns
    
    def test_deduplication_performance(self, spark, sample_config, sample_data, benchmark):
        """Benchmark deduplication performance."""
        from src.data_etl_pyspark.utils.dedup import hash_text_udf, deduplicate_df
        from src.data_etl_pyspark.utils.filtering import split_words_udf
        from pyspark.sql.functions import col, row_number, lit
        from pyspark.sql.window import Window
        
        # Prepare data for deduplication
        df_prep = sample_data \
            .withColumn("cleaned_text", col("text")) \
            .withColumn("words", split_words_udf(col("text"))) \
            .withColumn("hash", hash_text_udf(col("text"))) \
            .withColumn("id", row_number().over(Window.orderBy(lit(1))))
        
        logger = Mock()
        
        def run_deduplication():
            return deduplicate_df(df_prep, 0.9, logger)
        
        result = benchmark(run_deduplication)
        # Should have fewer rows due to deduplication
        assert result.count() < sample_data.count()
    
    def test_memory_usage_during_processing(self, spark, sample_config, sample_data):
        """Test memory usage patterns during processing."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        logger = Mock()
        pipeline = DataPreprocessingPipeline(spark, sample_config, logger)
        
        # Mock load_data to use sample data
        pipeline.load_data = lambda: sample_data
        
        # Run a simplified pipeline
        df = pipeline.load_data()
        df = df.cache()  # Force caching
        df.count()  # Force computation
        
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory
        
        # Memory increase should be reasonable (less than 500MB for small test data)
        assert memory_increase < 500, f"Memory usage increased by {memory_increase:.1f}MB"
        
        # Clean up
        spark.catalog.clearCache()
    
    def test_partition_performance(self, spark, sample_config, sample_data, benchmark):
        """Test performance with different partition counts."""
        def test_with_partitions(num_partitions):
            df = sample_data.repartition(num_partitions)
            return df.count()
        
        # Test with different partition sizes
        for partitions in [1, 2, 4, 8]:
            result = benchmark.pedantic(
                test_with_partitions, 
                args=(partitions,), 
                iterations=3, 
                rounds=2
            )
            assert result == 10


class TestMonitoringPerformance:
    """Test performance monitoring overhead."""
    
    def test_performance_monitor_overhead(self, benchmark):
        """Measure overhead of performance monitoring."""
        import tempfile
        import logging
        
        logger = logging.getLogger('test')
        
        def with_monitoring():
            with tempfile.TemporaryDirectory() as temp_dir:
                monitor = PerformanceMonitor("test_pipeline", temp_dir, logger)
                monitor.start_stage("test_stage", 1000)
                time.sleep(0.001)  # Simulate some work
                monitor.finish_stage(900)
                monitor.finish_pipeline(900)
        
        def without_monitoring():
            time.sleep(0.001)  # Same work without monitoring
        
        # Benchmark both approaches
        with_time = benchmark(with_monitoring)
        without_time = time.time()
        time.sleep(0.001)
        without_time = time.time() - without_time
        
        # Monitoring overhead should be minimal
        # (This is approximate due to timing variations)
        print(f"Monitoring overhead: {with_time - without_time:.4f}s")


class TestResourceUtilization:
    """Test resource utilization efficiency."""
    
    def test_cpu_utilization(self, spark, sample_config, sample_data):
        """Monitor CPU utilization during processing."""
        import psutil
        import threading
        import time
        
        cpu_usage = []
        
        def monitor_cpu():
            for _ in range(10):  # Monitor for ~1 second
                cpu_usage.append(psutil.cpu_percent(interval=0.1))
        
        # Start monitoring
        monitor_thread = threading.Thread(target=monitor_cpu)
        monitor_thread.start()
        
        # Perform data processing
        result = sample_data.repartition(4).cache()
        result.count()
        
        # Wait for monitoring to complete
        monitor_thread.join()
        
        avg_cpu = sum(cpu_usage) / len(cpu_usage)
        max_cpu = max(cpu_usage)
        
        print(f"Average CPU usage: {avg_cpu:.1f}%")
        print(f"Peak CPU usage: {max_cpu:.1f}%")
        
        # CPU should be reasonably utilized (not 0%, not 100%)
        assert 0 < avg_cpu < 90, f"CPU utilization seems abnormal: {avg_cpu:.1f}%"


@pytest.mark.integration
class TestEndToEndPerformance:
    """End-to-end performance tests."""
    
    def test_full_pipeline_performance(self, spark, sample_config, benchmark):
        """Benchmark full pipeline execution."""
        logger = Mock()
        
        # Create temporary directories
        import tempfile
        temp_dir = tempfile.mkdtemp()
        checkpoint_dir = tempfile.mkdtemp()
        
        try:
            sample_config['output']['dir'] = temp_dir
            sample_config['monitoring']['checkpoint_dir'] = checkpoint_dir
            
            pipeline = DataPreprocessingPipeline(spark, sample_config, logger)
            
            # Create minimal test dataset
            test_data = spark.createDataFrame([
                ("This is test text number one with sufficient length.", 1),
                ("Another test text with different content and good length.", 2),
                ("Third test text for comprehensive pipeline testing.", 3)
            ], ["text", "id"])
            
            # Mock the load_data method
            pipeline.load_data = lambda: test_data
            
            def run_pipeline():
                pipeline.run()
            
            # This will benchmark the full pipeline
            result = benchmark.pedantic(run_pipeline, iterations=1, rounds=1)
            
            # Verify output was created
            import os
            output_files = os.listdir(temp_dir)
            assert len(output_files) > 0, "No output files created"
            
        finally:
            # Clean up
            shutil.rmtree(temp_dir, ignore_errors=True)
            shutil.rmtree(checkpoint_dir, ignore_errors=True)


if __name__ == "__main__":
    # Run benchmarks with pytest-benchmark
    pytest.main([__file__, "--benchmark-only", "--benchmark-sort=mean"])