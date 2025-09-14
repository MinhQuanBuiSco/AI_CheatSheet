import argparse
import logging
import yaml
from pyspark.sql import SparkSession
from pipeline import DataPreprocessingPipeline

def setup_logging(config):
    log_level = config.get('logging', {}).get('level', 'INFO')
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description="LLM Data Preprocessing Pipeline")
    parser.add_argument('--config', type=str, default='config/config.yaml', help='Path to config file')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize optimized Spark session
    spark_builder = SparkSession.builder.appName("LLM Data Preprocessing Pipeline")
    
    # Core performance configs - disabled Arrow for demo to prevent OOM
    spark_builder = spark_builder \
        .config("spark.sql.execution.arrow.pyspark.enabled", "false") \
        .config("spark.sql.adaptive.enabled", config['spark']['sql']['adaptive']['enabled']) \
        .config("spark.sql.adaptive.coalescePartitions.enabled", config['spark']['sql']['adaptive']['coalesce_partitions']) \
        .config("spark.sql.adaptive.skewJoin.enabled", config['spark']['sql']['adaptive']['skew_join']) \
        .config("spark.serializer", config['spark']['serializer'])
    
    # Memory configuration
    memory_config = config['spark']['memory']
    spark_builder = spark_builder \
        .config("spark.executor.memory", memory_config['executor']) \
        .config("spark.driver.memory", memory_config['driver']) \
        .config("spark.executor.memoryFraction", memory_config['executor_memory_fraction']) \
        .config("spark.storage.memoryFraction", memory_config['executor_memory_storage_fraction'])
    
    # Dynamic allocation
    if config['spark']['dynamic_allocation']['enabled']:
        dynamic_config = config['spark']['dynamic_allocation']
        spark_builder = spark_builder \
            .config("spark.dynamicAllocation.enabled", "true") \
            .config("spark.dynamicAllocation.minExecutors", dynamic_config['min_executors']) \
            .config("spark.dynamicAllocation.maxExecutors", dynamic_config['max_executors']) \
            .config("spark.dynamicAllocation.initialExecutors", dynamic_config['initial_executors'])
    
    # Shuffle optimization
    shuffle_config = config['spark']['shuffle']
    spark_builder = spark_builder \
        .config("spark.shuffle.service.enabled", shuffle_config['service']) \
        .config("spark.shuffle.compress", shuffle_config['compress']) \
        .config("spark.shuffle.spill.compress", shuffle_config['spill_compress'])
    
    # Network optimization
    spark_builder = spark_builder \
        .config("spark.network.timeout", config['spark']['network_timeout']) \
        .config("spark.executor.heartbeatInterval", config['spark']['executor_heartbeat_interval'])
    
    # Checkpointing
    if config['monitoring']['checkpoint_dir']:
        spark_builder = spark_builder \
            .config("spark.sql.streaming.checkpointLocation", config['monitoring']['checkpoint_dir'])
    
    spark = spark_builder.getOrCreate()
    
    # Set checkpoint directory
    if config['monitoring']['checkpoint_dir']:
        spark.sparkContext.setCheckpointDir(config['monitoring']['checkpoint_dir'])
    
    try:
        logger = setup_logging(config)

        
        pipeline = DataPreprocessingPipeline(spark, config, logger)
        pipeline.run()
        logger.info("Pipeline completed successfully.")
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        raise
    finally:
        spark.stop()