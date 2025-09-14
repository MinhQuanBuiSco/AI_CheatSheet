from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import row_number, lit, rand, col  # Added col import
from pyspark.sql.window import Window
from datasets import load_dataset
import pandas as pd
import time
import logging  # Import for type hinting

from utils.cleaning import clean_text_udf
from utils.filtering import filter_language_udf, split_words_udf, heuristic_filter_udf, quality_filter_udf
from utils.dedup import hash_text_udf, deduplicate_df

class DataPreprocessingPipeline:
    def __init__(self, spark: SparkSession, config: dict, logger: logging.Logger):
        self.spark = spark
        self.config = config
        self.logger = logger
        self.num_partitions = self.config['processing']['num_partitions']

    def load_data(self) -> DataFrame:
        start_time = time.time()
        self.logger.info("Starting data loading...")
        
        kwargs = {'split': self.config['dataset']['split']}
        if 'config' in self.config['dataset'] and self.config['dataset']['config']:
            kwargs['name'] = self.config['dataset']['config']
        
        ds = load_dataset(self.config['dataset']['name'], **kwargs)
        pdf = ds.to_pandas()
        df = self.spark.createDataFrame(pdf).repartition(self.num_partitions)
        df = df.withColumn("id", row_number().over(Window.orderBy(lit(1))))
        
        self.logger.info(f"Data loaded: {df.count()} rows. Time taken: {time.time() - start_time:.2f}s")
        self.logger.debug(f"Sample row: {df.take(1)}")  # Debug: show one row
        return df

    def clean_and_filter(self, df: DataFrame) -> DataFrame:
        start_time = time.time()
        self.logger.info("Starting cleaning and filtering...")
        
        lang = self.config['filters']['language']
        
        # Clean
        df = df.withColumn("cleaned_text", clean_text_udf(col("text")))  # Assuming 'text' column
        self.logger.debug(f"After cleaning: {df.count()} rows")
        
        # Language filter
        df = df.filter(filter_language_udf(col("cleaned_text"), lit(lang)))
        self.logger.info(f"After language filter: {df.count()} rows")
        
        # Split words
        df = df.withColumn("words", split_words_udf(col("cleaned_text")))
        
        # Heuristic filter
        df = df.filter(heuristic_filter_udf(
            col("words"), 
            col("cleaned_text"), 
            lit(self.config['filters']['min_word_count']),
            lit(self.config['filters']['max_word_count']),
            lit(self.config['filters']['repetition_threshold'])
        ))
        self.logger.info(f"After heuristic filter: {df.count()} rows. Time taken: {time.time() - start_time:.2f}s")
        
        return df

    def deduplicate(self, df: DataFrame) -> DataFrame:
        start_time = time.time()
        self.logger.info("Starting deduplication...")
        
        df = df.withColumn("hash", hash_text_udf(col("cleaned_text")))
        df = deduplicate_df(df, self.config['filters']['dedup_threshold'])
        
        self.logger.info(f"After deduplication: {df.count()} rows. Time taken: {time.time() - start_time:.2f}s")
        return df

    def quality_filter(self, df: DataFrame) -> DataFrame:
        start_time = time.time()
        self.logger.info("Starting quality filtering...")
        
        quality_model = self.config['filters']['quality_model']
        quality_threshold = self.config['filters']['quality_threshold']
        batch_size = self.config['processing']['batch_size']
        
        df = df.withColumn("dummy_key", lit(0))
        df = df.groupBy("dummy_key").apply(quality_filter_udf(
            lit(quality_model), 
            lit(quality_threshold), 
            lit(batch_size)
        ))
        df = df.filter(col("quality_pass"))
        
        self.logger.info(f"After quality filter: {df.count()} rows. Time taken: {time.time() - start_time:.2f}s")
        return df

    def finalize(self, df: DataFrame) -> DataFrame:
        start_time = time.time()
        self.logger.info("Starting finalization...")
        
        df = df.select("cleaned_text").withColumnRenamed("cleaned_text", "text")
        df = df.orderBy(rand(seed=42))  # Shuffle
        
        self.logger.info(f"Final dataset: {df.count()} rows. Time taken: {time.time() - start_time:.2f}s")
        return df

    def run(self):
        overall_start = time.time()
        self.logger.info("Pipeline run started.")
        
        df = self.load_data()
        df = self.clean_and_filter(df)
        df = self.deduplicate(df)
        df = self.quality_filter(df)
        df = self.finalize(df)
        
        output_path = self.config['output']['dir'] + "/processed_dataset.parquet"
        df.write.mode("overwrite").parquet(output_path)
        
        self.logger.info(f"Pipeline completed. Total time: {time.time() - overall_start:.2f}s")