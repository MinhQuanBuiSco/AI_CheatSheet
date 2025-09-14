"""Data quality validation utilities for the pipeline."""

from pyspark.sql import DataFrame
from pyspark.sql.functions import col, count, when, isnan, isnull, length, mean, stddev, min as spark_min, max as spark_max
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of data validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    metrics: Dict[str, Any]
    
    
class DataValidator:
    """Comprehensive data validation for pipeline stages."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        
    def validate_schema(self, df: DataFrame, expected_columns: List[str]) -> ValidationResult:
        """Validate DataFrame schema against expected columns."""
        errors = []
        warnings = []
        metrics = {}
        
        actual_columns = set(df.columns)
        expected_columns_set = set(expected_columns)
        
        # Check for missing columns
        missing_columns = expected_columns_set - actual_columns
        if missing_columns:
            errors.append(f"Missing required columns: {missing_columns}")
            
        # Check for extra columns
        extra_columns = actual_columns - expected_columns_set
        if extra_columns:
            warnings.append(f"Unexpected columns found: {extra_columns}")
            
        metrics['total_columns'] = len(actual_columns)
        metrics['expected_columns'] = len(expected_columns)
        metrics['missing_columns'] = len(missing_columns)
        metrics['extra_columns'] = len(extra_columns)
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings, metrics)
    
    def validate_data_quality(self, df: DataFrame, stage_name: str) -> ValidationResult:
        """Validate data quality metrics."""
        errors = []
        warnings = []
        metrics = {}
        
        try:
            total_rows = df.count()
            metrics['total_rows'] = total_rows
            
            if total_rows == 0:
                errors.append("DataFrame is empty")
                return ValidationResult(False, errors, warnings, metrics)
            
            # Check for null values in key columns
            key_columns = ['text', 'cleaned_text', 'id']
            for col_name in key_columns:
                if col_name in df.columns:
                    null_count = df.filter(col(col_name).isNull()).count()
                    null_percentage = (null_count / total_rows) * 100
                    metrics[f'{col_name}_null_count'] = null_count
                    metrics[f'{col_name}_null_percentage'] = null_percentage
                    
                    if null_percentage > 10:  # More than 10% null values
                        warnings.append(f"High null percentage in {col_name}: {null_percentage:.1f}%")
                    elif null_percentage > 50:  # More than 50% null values
                        errors.append(f"Excessive null percentage in {col_name}: {null_percentage:.1f}%")
            
            # Validate text length distribution
            if 'cleaned_text' in df.columns:
                length_stats = df.select(
                    mean(length(col('cleaned_text'))).alias('mean_length'),
                    stddev(length(col('cleaned_text'))).alias('stddev_length'),
                    spark_min(length(col('cleaned_text'))).alias('min_length'),
                    spark_max(length(col('cleaned_text'))).alias('max_length')
                ).collect()[0]
                
                mean_len = length_stats['mean_length'] or 0
                min_len = length_stats['min_length'] or 0
                max_len = length_stats['max_length'] or 0
                
                metrics['text_length_mean'] = mean_len
                metrics['text_length_min'] = min_len
                metrics['text_length_max'] = max_len
                
                # Check for unreasonable text lengths
                if mean_len < 10:
                    warnings.append(f"Average text length is very short: {mean_len:.1f}")
                elif mean_len > 100000:
                    warnings.append(f"Average text length is very long: {mean_len:.1f}")
                
                if max_len > 1000000:  # 1MB of text
                    warnings.append(f"Some texts are extremely long: {max_len} characters")
            
            # Check for duplicate IDs if ID column exists
            if 'id' in df.columns:
                unique_ids = df.select('id').distinct().count()
                duplicate_ids = total_rows - unique_ids
                metrics['duplicate_ids'] = duplicate_ids
                
                if duplicate_ids > 0:
                    warnings.append(f"Found {duplicate_ids} duplicate IDs")
            
            # Stage-specific validations
            if stage_name == 'data_loading':
                # Check if we loaded reasonable amount of data
                if total_rows < 100:
                    warnings.append(f"Very small dataset loaded: {total_rows} rows")
                    
            elif stage_name == 'cleaning_and_filtering':
                # Check retention rate isn't too low
                if 'words' in df.columns:
                    empty_words = df.filter(col('words').isNull() | (length(col('words')) == 0)).count()
                    empty_percentage = (empty_words / total_rows) * 100
                    metrics['empty_words_percentage'] = empty_percentage
                    
                    if empty_percentage > 20:
                        warnings.append(f"High percentage of empty word lists: {empty_percentage:.1f}%")
                        
            elif stage_name == 'deduplication':
                # Validate deduplication didn't remove everything
                if total_rows < 10:
                    warnings.append(f"Very few rows remaining after deduplication: {total_rows}")
                    
            elif stage_name == 'quality_filtering':
                # Check quality filtering results
                if total_rows < 5:
                    errors.append(f"Too few rows remaining after quality filtering: {total_rows}")
            
            self.logger.info(f"Data validation for {stage_name}: {len(errors)} errors, {len(warnings)} warnings")
            
        except Exception as e:
            errors.append(f"Validation failed with error: {str(e)}")
            self.logger.error(f"Data validation error in {stage_name}: {e}")
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings, metrics)
    
    def validate_pipeline_output(self, df: DataFrame) -> ValidationResult:
        """Validate final pipeline output quality."""
        errors = []
        warnings = []
        metrics = {}
        
        try:
            # Schema validation for final output
            required_columns = ['text']
            schema_result = self.validate_schema(df, required_columns)
            
            errors.extend(schema_result.errors)
            warnings.extend(schema_result.warnings)
            metrics.update(schema_result.metrics)
            
            if not schema_result.is_valid:
                return ValidationResult(False, errors, warnings, metrics)
            
            # Content validation
            total_rows = df.count()
            metrics['final_output_rows'] = total_rows
            
            if total_rows == 0:
                errors.append("Final output is empty")
                return ValidationResult(False, errors, warnings, metrics)
            
            # Check for empty or very short texts
            if 'text' in df.columns:
                short_texts = df.filter(length(col('text')) < 50).count()
                short_percentage = (short_texts / total_rows) * 100
                metrics['short_texts_percentage'] = short_percentage
                
                if short_percentage > 30:
                    warnings.append(f"High percentage of short texts: {short_percentage:.1f}%")
                
                # Sample some texts for manual inspection
                sample_texts = df.select('text').limit(3).collect()
                metrics['sample_texts'] = [row['text'][:100] + '...' for row in sample_texts]
            
            # Final quality checks
            if total_rows < 100:
                warnings.append(f"Small final dataset: {total_rows} rows")
            elif total_rows > 10000000:
                self.logger.info(f"Large final dataset: {total_rows:,} rows")
            
        except Exception as e:
            errors.append(f"Output validation failed: {str(e)}")
            self.logger.error(f"Output validation error: {e}")
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings, metrics)


class SchemaEnforcer:
    """Enforce and fix schema issues in DataFrames."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        
    def enforce_text_pipeline_schema(self, df: DataFrame, stage: str) -> DataFrame:
        """Enforce standard schema for text processing pipeline."""
        
        if stage == 'input':
            # Ensure we have required columns
            if 'text' not in df.columns:
                # Try to find a text column with different name
                text_candidates = ['content', 'body', 'message', 'document']
                for candidate in text_candidates:
                    if candidate in df.columns:
                        df = df.withColumnRenamed(candidate, 'text')
                        self.logger.info(f"Renamed column '{candidate}' to 'text'")
                        break
                else:
                    raise ValueError("No text column found in input data")
                    
        elif stage == 'output':
            # Ensure final output has clean schema
            required_columns = ['text']
            for col_name in required_columns:
                if col_name not in df.columns:
                    raise ValueError(f"Required column '{col_name}' missing from output")
            
            # Remove any temporary columns that shouldn't be in final output
            temp_columns = ['hash', 'words', 'dummy_key', 'rawFeatures', 'features', 'hashes']
            for col_name in temp_columns:
                if col_name in df.columns:
                    df = df.drop(col_name)
                    self.logger.debug(f"Removed temporary column: {col_name}")
        
        return df


def create_data_quality_report(validation_results: Dict[str, ValidationResult], 
                             output_path: str = "./data_quality_report.json") -> Dict[str, Any]:
    """Create comprehensive data quality report."""
    import json
    from datetime import datetime
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'overall_status': 'PASSED',
        'stages': {},
        'summary': {
            'total_errors': 0,
            'total_warnings': 0,
            'failed_stages': []
        }
    }
    
    for stage_name, result in validation_results.items():
        stage_report = {
            'status': 'PASSED' if result.is_valid else 'FAILED',
            'errors': result.errors,
            'warnings': result.warnings,
            'metrics': result.metrics
        }
        
        report['stages'][stage_name] = stage_report
        report['summary']['total_errors'] += len(result.errors)
        report['summary']['total_warnings'] += len(result.warnings)
        
        if not result.is_valid:
            report['overall_status'] = 'FAILED'
            report['summary']['failed_stages'].append(stage_name)
    
    # Save report to file
    try:
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
    except Exception as e:
        logging.getLogger(__name__).warning(f"Could not save data quality report: {e}")
    
    return report