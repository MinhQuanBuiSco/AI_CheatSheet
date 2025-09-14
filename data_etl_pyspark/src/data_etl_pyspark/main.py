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
    
    # Initialize Spark
    spark = SparkSession.builder \
        .appName("LLM Data Preprocessing Pipeline") \
        .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
        .config("spark.executor.memory", "16g") \
        .config("spark.driver.memory", "16g") \
        .getOrCreate()
    
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