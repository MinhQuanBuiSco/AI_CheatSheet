"""Error handling and retry utilities for the data pipeline."""

import time
import logging
from typing import Callable, Any, Optional, Type
from functools import wraps


class PipelineException(Exception):
    """Base exception for pipeline errors."""
    pass


class DataLoadException(PipelineException):
    """Exception raised during data loading."""
    pass


class ProcessingException(PipelineException):
    """Exception raised during data processing."""
    pass


def retry_with_exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Decorator to retry function calls with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_factor: Factor to multiply delay by after each retry
        exceptions: Tuple of exception types to catch and retry
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = logging.getLogger(__name__)
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries: {str(e)}")
                        raise
                    
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                    logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {str(e)}. Retrying in {delay:.1f}s")
                    time.sleep(delay)
            
        return wrapper
    return decorator


def safe_spark_operation(operation_name: str):
    """Decorator for safe Spark operations with proper error handling."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            logger = self.logger if hasattr(self, 'logger') else logging.getLogger(__name__)
            
            try:
                logger.info(f"Starting {operation_name}...")
                result = func(self, *args, **kwargs)
                logger.info(f"Completed {operation_name} successfully")
                return result
                
            except Exception as e:
                logger.error(f"Failed during {operation_name}: {str(e)}")
                # Cleanup cached DataFrames on error
                if hasattr(self, 'spark') and hasattr(self.spark, 'catalog'):
                    try:
                        self.spark.catalog.clearCache()
                        logger.info("Cleared Spark cache after error")
                    except:
                        pass
                        
                raise ProcessingException(f"Error in {operation_name}: {str(e)}") from e
                
        return wrapper
    return decorator


class ResourceMonitor:
    """Monitor resource usage during pipeline execution."""
    
    def __init__(self, spark_session, logger):
        self.spark = spark_session
        self.logger = logger
        
    def get_memory_usage(self) -> dict:
        """Get current memory usage statistics."""
        try:
            sc = self.spark.sparkContext
            status = sc.statusTracker()
            
            # Try different methods to get executor info
            try:
                executor_infos = status.getExecutorInfos()
            except AttributeError:
                # Fallback for different Spark versions
                try:
                    executor_infos = status.getExecutorSummaries()
                except AttributeError:
                    self.logger.warning("Could not access executor information")
                    return {'executors': 'unknown', 'memory_info': 'unavailable'}
            
            total_memory = sum(getattr(info, 'maxMemory', 0) for info in executor_infos)
            total_memory_used = sum(getattr(info, 'memoryUsed', 0) for info in executor_infos)
            
            if total_memory == 0:
                return {'executors': len(executor_infos), 'memory_info': 'unavailable'}
            
            return {
                'total_memory_mb': total_memory // (1024 * 1024),
                'used_memory_mb': total_memory_used // (1024 * 1024),
                'memory_utilization_percent': (total_memory_used / total_memory * 100) if total_memory > 0 else 0,
                'active_executors': len(executor_infos)
            }
        except Exception as e:
            self.logger.warning(f"Could not get memory usage: {e}")
            return {'executors': 'unknown', 'error': str(e)}
            
    def log_resource_usage(self, stage_name: str = ""):
        """Log current resource usage."""
        usage = self.get_memory_usage()
        if usage:
            stage_prefix = f"Resource usage for {stage_name}: " if stage_name else "Resource usage: "
            
            # Handle different response formats
            if 'used_memory_mb' in usage and 'total_memory_mb' in usage:
                self.logger.info(
                    f"{stage_prefix}"
                    f"{usage['used_memory_mb']}MB / {usage['total_memory_mb']}MB "
                    f"({usage['memory_utilization_percent']:.1f}%) across "
                    f"{usage['active_executors']} executors"
                )
            elif 'executors' in usage:
                if usage['executors'] == 'unknown':
                    self.logger.info(f"{stage_prefix}Memory info unavailable (local mode)")
                else:
                    self.logger.info(f"{stage_prefix}{usage['executors']} executors active")
            else:
                self.logger.info(f"{stage_prefix}Resource monitoring unavailable")


def validate_dataframe_health(df, stage_name: str, logger):
    """Validate DataFrame health and log warnings for potential issues."""
    try:
        # Check for empty DataFrame
        if df.count() == 0:
            logger.warning(f"DataFrame is empty after {stage_name}")
            return False
            
        # Check partition distribution
        partition_counts = df.rdd.glom().map(len).collect()
        if partition_counts:
            max_partition = max(partition_counts)
            min_partition = min(partition_counts)
            
            # Warn about severe skew
            if max_partition > 0 and (max_partition / max(min_partition, 1)) > 10:
                logger.warning(
                    f"Severe data skew detected after {stage_name}: "
                    f"max partition size {max_partition}, min partition size {min_partition}"
                )
                
        return True
        
    except Exception as e:
        logger.warning(f"Could not validate DataFrame health after {stage_name}: {e}")
        return True  # Assume healthy if we can't check