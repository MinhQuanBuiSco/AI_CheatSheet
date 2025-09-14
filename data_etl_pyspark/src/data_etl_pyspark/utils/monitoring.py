"""Performance monitoring and metrics collection for the data pipeline."""

import time
import json
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import logging


@dataclass
class StageMetrics:
    """Metrics for a single pipeline stage."""
    stage_name: str
    start_time: float
    end_time: Optional[float] = None
    duration_seconds: Optional[float] = None
    input_rows: Optional[int] = None
    output_rows: Optional[int] = None
    rows_processed_per_second: Optional[float] = None
    memory_usage_mb: Optional[int] = None
    partition_count: Optional[int] = None
    data_skew_ratio: Optional[float] = None
    errors: list = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
            
    def finish(self, output_rows: int = None, memory_usage_mb: int = None, 
               partition_count: int = None, data_skew_ratio: float = None):
        """Mark stage as finished and calculate metrics."""
        self.end_time = time.time()
        self.duration_seconds = self.end_time - self.start_time
        
        if output_rows is not None:
            self.output_rows = output_rows
            if self.duration_seconds > 0:
                self.rows_processed_per_second = output_rows / self.duration_seconds
                
        if memory_usage_mb is not None:
            self.memory_usage_mb = memory_usage_mb
            
        if partition_count is not None:
            self.partition_count = partition_count
            
        if data_skew_ratio is not None:
            self.data_skew_ratio = data_skew_ratio


@dataclass 
class PipelineMetrics:
    """Overall pipeline performance metrics."""
    pipeline_id: str
    start_time: float
    end_time: Optional[float] = None
    total_duration_seconds: Optional[float] = None
    total_input_rows: Optional[int] = None
    total_output_rows: Optional[int] = None
    retention_rate: Optional[float] = None
    average_throughput_rows_per_second: Optional[float] = None
    stages: Dict[str, StageMetrics] = None
    spark_config: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.stages is None:
            self.stages = {}
    
    def finish(self, total_output_rows: int = None):
        """Mark pipeline as finished and calculate final metrics."""
        self.end_time = time.time()
        self.total_duration_seconds = self.end_time - self.start_time
        
        if total_output_rows is not None:
            self.total_output_rows = total_output_rows
            if self.total_input_rows and self.total_input_rows > 0:
                self.retention_rate = total_output_rows / self.total_input_rows
            
            if self.total_duration_seconds and self.total_duration_seconds > 0:
                self.average_throughput_rows_per_second = total_output_rows / self.total_duration_seconds


class PerformanceMonitor:
    """Monitor and collect performance metrics for the pipeline."""
    
    def __init__(self, pipeline_id: str, output_dir: str = "./metrics", logger: Optional[logging.Logger] = None):
        self.pipeline_id = pipeline_id
        self.output_dir = output_dir
        self.logger = logger or logging.getLogger(__name__)
        self.metrics = PipelineMetrics(pipeline_id=pipeline_id, start_time=time.time())
        self.current_stage: Optional[StageMetrics] = None
        
        # Create metrics output directory
        os.makedirs(output_dir, exist_ok=True)
        
    def start_stage(self, stage_name: str, input_rows: int = None) -> StageMetrics:
        """Start monitoring a new pipeline stage."""
        # Finish previous stage if exists
        if self.current_stage and self.current_stage.end_time is None:
            self.logger.warning(f"Stage {self.current_stage.stage_name} was not properly finished")
            self.finish_stage()
        
        stage_metrics = StageMetrics(
            stage_name=stage_name,
            start_time=time.time(),
            input_rows=input_rows
        )
        
        self.current_stage = stage_metrics
        self.metrics.stages[stage_name] = stage_metrics
        
        self.logger.info(f"Started monitoring stage: {stage_name}")
        if input_rows:
            self.logger.info(f"Input rows for {stage_name}: {input_rows:,}")
            
        return stage_metrics
    
    def finish_stage(self, output_rows: int = None, **kwargs) -> Optional[StageMetrics]:
        """Finish monitoring the current stage."""
        if not self.current_stage:
            self.logger.warning("No active stage to finish")
            return None
        
        self.current_stage.finish(output_rows=output_rows, **kwargs)
        
        # Log stage completion
        stage = self.current_stage
        self.logger.info(f"Completed stage: {stage.stage_name}")
        self.logger.info(f"Duration: {stage.duration_seconds:.2f}s")
        
        if stage.input_rows and stage.output_rows:
            retention = stage.output_rows / stage.input_rows
            self.logger.info(f"Rows: {stage.input_rows:,} → {stage.output_rows:,} ({retention*100:.1f}% retained)")
            
        if stage.rows_processed_per_second:
            self.logger.info(f"Throughput: {stage.rows_processed_per_second:,.0f} rows/second")
            
        finished_stage = self.current_stage
        self.current_stage = None
        
        return finished_stage
    
    def add_stage_error(self, error: str):
        """Add error to current stage."""
        if self.current_stage:
            self.current_stage.errors.append({
                'timestamp': datetime.now().isoformat(),
                'error': error
            })
    
    def finish_pipeline(self, total_output_rows: int = None, spark_config: Dict[str, Any] = None):
        """Finish monitoring the entire pipeline."""
        # Finish any active stage
        if self.current_stage:
            self.finish_stage()
        
        # Set total input rows from first stage if not set
        if not self.metrics.total_input_rows and self.metrics.stages:
            first_stage = next(iter(self.metrics.stages.values()))
            self.metrics.total_input_rows = first_stage.input_rows
        
        self.metrics.finish(total_output_rows=total_output_rows)
        
        if spark_config:
            self.metrics.spark_config = spark_config
        
        # Log final metrics
        self._log_final_metrics()
        
        # Save metrics to file
        self._save_metrics()
    
    def _log_final_metrics(self):
        """Log comprehensive pipeline metrics."""
        m = self.metrics
        self.logger.info("=" * 60)
        self.logger.info("PIPELINE PERFORMANCE SUMMARY")
        self.logger.info("=" * 60)
        
        if m.total_duration_seconds:
            self.logger.info(f"Total Duration: {m.total_duration_seconds:.2f}s ({m.total_duration_seconds/60:.1f} min)")
        
        if m.total_input_rows and m.total_output_rows:
            self.logger.info(f"Data Processed: {m.total_input_rows:,} → {m.total_output_rows:,}")
            self.logger.info(f"Retention Rate: {m.retention_rate*100:.1f}%")
        
        if m.average_throughput_rows_per_second:
            self.logger.info(f"Average Throughput: {m.average_throughput_rows_per_second:,.0f} rows/second")
        
        self.logger.info("\nSTAGE BREAKDOWN:")
        for stage_name, stage in m.stages.items():
            if stage.duration_seconds:
                pct_of_total = (stage.duration_seconds / m.total_duration_seconds * 100) if m.total_duration_seconds else 0
                self.logger.info(f"  {stage_name}: {stage.duration_seconds:.2f}s ({pct_of_total:.1f}%)")
                
                if stage.errors:
                    self.logger.info(f"    Errors: {len(stage.errors)}")
        
        self.logger.info("=" * 60)
    
    def _save_metrics(self):
        """Save metrics to JSON file."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pipeline_metrics_{self.pipeline_id}_{timestamp}.json"
            filepath = os.path.join(self.output_dir, filename)
            
            # Convert to dict and handle non-serializable types
            metrics_dict = asdict(self.metrics)
            
            with open(filepath, 'w') as f:
                json.dump(metrics_dict, f, indent=2, default=str)
            
            self.logger.info(f"Metrics saved to: {filepath}")
            
        except Exception as e:
            self.logger.error(f"Failed to save metrics: {e}")
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics as dictionary."""
        return asdict(self.metrics)


def analyze_partition_skew(df, logger: logging.Logger) -> tuple:
    """Analyze data skew across partitions."""
    try:
        # For small datasets or local mode, partition analysis might not be meaningful
        partition_sizes = df.rdd.glom().map(len).collect()
        if not partition_sizes:
            logger.debug("No partition information available")
            return 0, 1.0
        
        max_size = max(partition_sizes)
        min_size = min(partition_sizes)
        avg_size = sum(partition_sizes) / len(partition_sizes)
        
        # Avoid division by zero
        skew_ratio = max_size / max(min_size, 1) if min_size > 0 else 1.0
        
        # Only warn about skew if we have meaningful data
        if len(partition_sizes) > 1 and max_size > 10 and skew_ratio > 5:
            logger.warning(f"Data skew detected - Max: {max_size}, Min: {min_size}, Avg: {avg_size:.0f}, Skew ratio: {skew_ratio:.1f}")
        elif len(partition_sizes) > 1:
            logger.debug(f"Partition distribution - Max: {max_size}, Min: {min_size}, Avg: {avg_size:.0f}")
        
        return len(partition_sizes), skew_ratio
        
    except Exception as e:
        logger.warning(f"Could not analyze partition skew: {e}")
        return 0, 1.0


class MetricsCollector:
    """Utility class for collecting various performance metrics."""
    
    @staticmethod
    def collect_spark_metrics(spark_session, logger: logging.Logger) -> Dict[str, Any]:
        """Collect Spark-specific metrics."""
        try:
            sc = spark_session.sparkContext
            status = sc.statusTracker()
            
            basic_metrics = {
                'application_id': getattr(sc, 'applicationId', 'unknown'),
                'application_name': sc.appName,
                'master': sc.master,
                'default_parallelism': sc.defaultParallelism
            }
            
            # Try to get executor info with fallback
            try:
                executor_infos = status.getExecutorInfos()
                basic_metrics['executors'] = {
                    'total': len(executor_infos),
                    'active': len([e for e in executor_infos if getattr(e, 'isActive', True)])
                }
            except (AttributeError, Exception):
                basic_metrics['executors'] = {'total': 'unknown', 'active': 'unknown'}
            
            # Try to get stage info with fallback
            try:
                stage_infos = status.getStageInfos()
                basic_metrics['stages_completed'] = len([s for s in stage_infos if getattr(s, 'submissionTime', None) is not None])
            except (AttributeError, Exception):
                basic_metrics['stages_completed'] = 'unknown'
            
            return basic_metrics
            
        except Exception as e:
            logger.warning(f"Could not collect Spark metrics: {e}")
            return {
                'application_name': 'unknown',
                'master': 'unknown',
                'error': str(e)
            }