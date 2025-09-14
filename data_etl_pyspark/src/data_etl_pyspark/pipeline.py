from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import lit, rand, col, current_date, monotonically_increasing_id
from datasets import load_dataset
import time
import logging
import os
from typing import Optional

from utils.cleaning import clean_text_udf
from utils.filtering import filter_language_udf, split_words_udf, heuristic_filter_udf, quality_filter_udf
from utils.dedup import hash_text_udf, deduplicate_df
from utils.monitoring import PerformanceMonitor, analyze_partition_skew, MetricsCollector
from utils.error_handling import safe_spark_operation, retry_with_exponential_backoff, ResourceMonitor

class DataPreprocessingPipeline:
    def __init__(self, spark: SparkSession, config: dict, logger: logging.Logger):
        self.spark = spark
        self.config = config
        self.logger = logger
        self.cache_intermediate = self.config['processing']['cache_intermediate']
        self.checkpoint_interval = self.config['processing']['checkpoint_interval']
        self.step_counter = 0
        
        # Determine optimal partitions - keep small for demo
        if self.config['processing']['num_partitions'] == "auto":
            self.num_partitions = max(self.spark.sparkContext.defaultParallelism, 4)  # Much smaller
        else:
            self.num_partitions = min(self.config['processing']['num_partitions'], 4)  # Cap at 4
        
        # Create checkpoint directory if needed
        if self.config['monitoring']['checkpoint_dir']:
            os.makedirs(self.config['monitoring']['checkpoint_dir'], exist_ok=True)
            
        # Initialize monitoring
        self.performance_monitor = PerformanceMonitor(
            pipeline_id=f"llm_preprocessing_{int(time.time())}",
            output_dir=self.config.get('monitoring', {}).get('metrics_dir', './metrics'),
            logger=self.logger
        )
        
        # Initialize resource monitor
        self.resource_monitor = ResourceMonitor(spark, logger)

    @safe_spark_operation("data_loading")
    @retry_with_exponential_backoff(max_retries=2, exceptions=(Exception,))
    def load_data(self) -> DataFrame:
        start_time = time.time()
        self.logger.info("Starting data loading...")
        
        kwargs = {'split': self.config['dataset']['split']}
        if 'config' in self.config['dataset'] and self.config['dataset']['config']:
            kwargs['name'] = self.config['dataset']['config']
        
        # Load in batches for memory efficiency
        ds = load_dataset(self.config['dataset']['name'], **kwargs)
        
        # Convert to pandas in smaller chunks to prevent OOM
        if hasattr(ds, '__len__') and len(ds) > 5000:
            # For large datasets, take a sample for demo
            ds = ds.select(range(min(1000, len(ds))))
            self.logger.info(f"Limited dataset to {len(ds)} samples for memory efficiency")
        
        pdf = ds.to_pandas()
        
        # Add metadata columns for better tracking
        df = self.spark.createDataFrame(pdf)
        
        # Use monotonically_increasing_id() instead of window function to avoid partition warnings
        df = df.withColumn("id", monotonically_increasing_id()) \
               .withColumn("processing_date", current_date())
        
        # Repartition to optimal number for small datasets
        if self.num_partitions == "auto":
            optimal_partitions = min(4, max(1, len(pdf) // 100))  # 1 partition per 100 rows, max 4
        else:
            optimal_partitions = min(self.num_partitions, 4)  # Cap at 4 for demo
            
        df = df.repartition(optimal_partitions)
        
        # Cache if configured and checkpoint
        df = self._optimize_dataframe(df, "data_loading")
        
        row_count = df.count()
        self.logger.info(f"Data loaded: {row_count:,} rows in {self.num_partitions} partitions. Time taken: {time.time() - start_time:.2f}s")
        self.logger.info(f"Average rows per partition: {row_count // self.num_partitions:,}")
        
        return df

    @safe_spark_operation("cleaning_and_filtering")
    def clean_and_filter(self, df: DataFrame) -> DataFrame:
        start_time = time.time()
        self.logger.info("Starting cleaning and filtering...")
        initial_count = df.count()
        
        lang = self.config['filters']['language']
        
        # Clean text - broadcast small config values for efficiency
        df = df.withColumn("cleaned_text", clean_text_udf(col("text")))
        df = self._optimize_dataframe(df, "text_cleaning")
        
        # Language filter with null safety
        df = df.filter(
            (col("cleaned_text").isNotNull()) & 
            (filter_language_udf(col("cleaned_text"), lit(lang)))
        )
        lang_filtered_count = df.count()
        self.logger.info(f"Language filter: {initial_count:,} → {lang_filtered_count:,} rows ({lang_filtered_count/initial_count*100:.1f}% retained)")
        
        # Split words
        df = df.withColumn("words", split_words_udf(col("cleaned_text")))
        
        # Heuristic filter with broadcast variables for efficiency
        min_words = self.spark.sparkContext.broadcast(self.config['filters']['min_word_count'])
        max_words = self.spark.sparkContext.broadcast(self.config['filters']['max_word_count'])
        rep_threshold = self.spark.sparkContext.broadcast(self.config['filters']['repetition_threshold'])
        
        df = df.filter(heuristic_filter_udf(
            col("words"), 
            col("cleaned_text"), 
            lit(min_words.value),
            lit(max_words.value),
            lit(rep_threshold.value)
        ))
        
        final_count = df.count()
        df = self._optimize_dataframe(df, "cleaning_and_filtering")
        
        self.logger.info(f"Heuristic filter: {lang_filtered_count:,} → {final_count:,} rows ({final_count/initial_count*100:.1f}% of original retained)")
        self.logger.info(f"Cleaning and filtering completed. Time taken: {time.time() - start_time:.2f}s")
        
        return df

    @safe_spark_operation("deduplication")
    def deduplicate(self, df: DataFrame) -> DataFrame:
        start_time = time.time()
        self.logger.info("Starting deduplication...")
        initial_count = df.count()
        
        # Add hash column
        df = df.withColumn("hash", hash_text_udf(col("cleaned_text")))
        df = self._optimize_dataframe(df, "hash_generation")
        
        # Deduplicate with optimized threshold
        df = deduplicate_df(df, self.config['filters']['dedup_threshold'], self.logger)
        df = self._optimize_dataframe(df, "deduplication")
        
        final_count = df.count()
        duplicates_removed = initial_count - final_count
        self.logger.info(f"Deduplication: {initial_count:,} → {final_count:,} rows ({duplicates_removed:,} duplicates removed, {duplicates_removed/initial_count*100:.1f}%)")
        self.logger.info(f"Deduplication completed. Time taken: {time.time() - start_time:.2f}s")
        
        return df

    @safe_spark_operation("quality_filtering")
    def quality_filter(self, df: DataFrame) -> DataFrame:
        start_time = time.time()
        self.logger.info("Starting quality filtering...")
        initial_count = df.count()
        
        quality_model = self.config['filters']['quality_model']
        quality_threshold = self.config['filters']['quality_threshold']
        batch_size = self.config['processing']['batch_size']
        
        # Apply simple quality filter (avoids serialization issues)
        quality_udf = quality_filter_udf(quality_model, quality_threshold, batch_size)
        df = df.filter(quality_udf(col("cleaned_text")))
        
        df = self._optimize_dataframe(df, "quality_filtering")
        
        final_count = df.count()
        filtered_out = initial_count - final_count
        self.logger.info(f"Quality filter: {initial_count:,} → {final_count:,} rows ({filtered_out:,} low-quality filtered out, {filtered_out/initial_count*100:.1f}%)")
        self.logger.info(f"Quality filtering completed. Time taken: {time.time() - start_time:.2f}s")
        
        return df

    def finalize(self, df: DataFrame) -> DataFrame:
        start_time = time.time()
        self.logger.info("Starting finalization...")
        
        # Select final columns and add metadata
        df = df.select(
            col("cleaned_text").alias("text"),
            col("id"),
            col("processing_date")
        )
        
        # Shuffle with optimized partitioning
        df = df.orderBy(rand(seed=42))
        df = df.repartition(self.num_partitions // 4)  # Reduce partitions for final output
        
        final_count = df.count()
        self.logger.info(f"Final dataset: {final_count:,} rows. Time taken: {time.time() - start_time:.2f}s")
        
        return df

    def _optimize_dataframe(self, df: DataFrame, stage_name: str) -> DataFrame:
        """Apply caching and checkpointing strategies."""
        self.step_counter += 1
        
        if self.cache_intermediate:
            df = df.cache()
            
        # Checkpoint every N steps to truncate lineage
        if self.step_counter % self.checkpoint_interval == 0:
            df = df.checkpoint()
            self.logger.info(f"Checkpointed DataFrame at stage: {stage_name}")
            
        return df
    
    def _save_output(self, df: DataFrame) -> str:
        """Save output with optimized format and partitioning."""
        output_config = self.config['output']
        output_path = output_config['dir']
        
        writer = df.write.mode("overwrite")
        
        # Configure compression
        if 'compression' in output_config:
            writer = writer.option("compression", output_config['compression'])
            
        # Configure partitioning
        if 'partition_by' in output_config and output_config['partition_by']:
            # Only partition if the column exists
            available_columns = df.columns
            partition_cols = [col for col in output_config['partition_by'] if col in available_columns]
            if partition_cols:
                writer = writer.partitionBy(*partition_cols)
        
        # Choose output format
        output_format = output_config.get('format', 'parquet')
        if output_format == 'delta':
            try:
                writer.format("delta").save(output_path)
                return f"{output_path} (Delta Lake format)"
            except Exception as e:
                self.logger.warning(f"Delta Lake not available, falling back to Parquet: {e}")
                writer.parquet(output_path)
                return f"{output_path}/processed_dataset.parquet"
        else:
            writer.parquet(f"{output_path}/processed_dataset.parquet")
            return f"{output_path}/processed_dataset.parquet"
    
    def run(self):
        overall_start = time.time()
        self.logger.info("=== Optimized Pipeline Run Started ===")
        self.logger.info(f"Target partitions: {self.num_partitions}")
        self.logger.info(f"Caching enabled: {self.cache_intermediate}")
        self.logger.info(f"Checkpoint interval: {self.checkpoint_interval}")
        
        try:
            # Execute pipeline stages with monitoring
            self.performance_monitor.start_stage("data_loading")
            df = self.load_data()
            input_rows = df.count()
            self.performance_monitor.finish_stage(output_rows=input_rows)
            self.resource_monitor.log_resource_usage("after data loading")
            
            self.performance_monitor.start_stage("cleaning_and_filtering", input_rows=input_rows)
            df = self.clean_and_filter(df)
            cleaned_rows = df.count()
            self.performance_monitor.finish_stage(output_rows=cleaned_rows)
            self.resource_monitor.log_resource_usage("after cleaning and filtering")
            
            self.performance_monitor.start_stage("deduplication", input_rows=cleaned_rows)
            df = self.deduplicate(df)
            dedup_rows = df.count()
            partition_count, skew_ratio = analyze_partition_skew(df, self.logger)
            self.performance_monitor.finish_stage(
                output_rows=dedup_rows, 
                partition_count=partition_count, 
                data_skew_ratio=skew_ratio
            )
            self.resource_monitor.log_resource_usage("after deduplication")
            
            self.performance_monitor.start_stage("quality_filtering", input_rows=dedup_rows)
            df = self.quality_filter(df)
            quality_rows = df.count()
            self.performance_monitor.finish_stage(output_rows=quality_rows)
            self.resource_monitor.log_resource_usage("after quality filtering")
            
            self.performance_monitor.start_stage("finalization", input_rows=quality_rows)
            df = self.finalize(df)
            final_rows = df.count()
            self.performance_monitor.finish_stage(output_rows=final_rows)
            
            # Save output with monitoring
            self.performance_monitor.start_stage("output_save", input_rows=final_rows)
            output_path = self._save_output(df)
            self.performance_monitor.finish_stage(output_rows=final_rows)
            
            # Collect final metrics
            spark_config = MetricsCollector.collect_spark_metrics(self.spark, self.logger)
            self.performance_monitor.finish_pipeline(
                total_output_rows=final_rows,
                spark_config=spark_config
            )
            
            total_time = time.time() - overall_start
            self.logger.info(f"=== Pipeline Completed Successfully ===")
            self.logger.info(f"Output saved to: {output_path}")
            self.logger.info(f"Total processing time: {total_time:.2f}s ({total_time/60:.1f} minutes)")
            self.logger.info(f"Data flow: {input_rows:,} → {final_rows:,} rows ({final_rows/input_rows*100:.1f}% retained)")
            
            # Final resource usage
            self.resource_monitor.log_resource_usage("final")
            
            # Cleanup cached DataFrames
            if self.cache_intermediate:
                self.spark.catalog.clearCache()
                self.logger.info("Cleared all cached DataFrames")
                
        except Exception as e:
            self.logger.error(f"Pipeline failed: {str(e)}")
            
            # Add error to current stage if monitoring is active
            if hasattr(self, 'performance_monitor'):
                self.performance_monitor.add_stage_error(str(e))
            
            # Cleanup on failure
            if self.cache_intermediate:
                try:
                    self.spark.catalog.clearCache()
                    self.logger.info("Cleared Spark cache after error")
                except:
                    pass
            
            raise