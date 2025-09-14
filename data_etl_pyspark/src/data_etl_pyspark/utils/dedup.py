from pyspark.sql import DataFrame
from pyspark.sql.functions import udf, col, sha2, length, when, isnan, isnull
from pyspark.sql.types import StringType
from pyspark.ml.feature import MinHashLSH, HashingTF, VectorAssembler
import hashlib
import logging


@udf(returnType=StringType())
def hash_text_udf(text: str) -> str:
    """Generate SHA256 hash of text."""
    if not text:
        return None
    return hashlib.sha256(text.encode()).hexdigest()


def deduplicate_df(df: DataFrame, threshold: float, logger: logging.Logger = None) -> DataFrame:
    """
    Optimized deduplication with exact and fuzzy matching.
    
    Args:
        df: Input DataFrame with 'hash', 'words', and 'id' columns
        threshold: Similarity threshold for fuzzy deduplication
        logger: Optional logger instance
        
    Returns:
        Deduplicated DataFrame
    """
    if logger is None:
        logger = logging.getLogger(__name__)
        
    original_count = df.count()
    
    # Step 1: Exact deduplication using hash
    logger.info("Performing exact deduplication...")
    df_exact = df.filter(col("hash").isNotNull()).dropDuplicates(['hash'])
    exact_dedup_count = df_exact.count()
    exact_removed = original_count - exact_dedup_count
    
    logger.info(f"Exact deduplication: {original_count:,} → {exact_dedup_count:,} ({exact_removed:,} exact duplicates removed)")
    
    # Step 2: Fuzzy deduplication (skip for demo to save memory)
    if exact_dedup_count > 500:  # Skip fuzzy dedup for demo (much lower threshold)
        logger.info("Skipping fuzzy deduplication for memory efficiency in demo")
        return df_exact.drop("hash")  # Clean up hash column
    
    try:
        logger.info(f"Performing fuzzy deduplication with threshold {threshold}...")
        
        # Filter out rows without words to avoid errors
        # Note: words is an array, so we use size() instead of length()
        from pyspark.sql.functions import size
        df_with_words = df_exact.filter(
            col("words").isNotNull() & 
            (size(col("words")) > 0)
        )
        
        # Create features for similarity matching
        hashingTF = HashingTF(
            inputCol="words", 
            outputCol="rawFeatures", 
            numFeatures=2048  # Increased for better precision
        )
        df_features = hashingTF.transform(df_with_words)
        
        # Assemble features
        assembler = VectorAssembler(inputCols=["rawFeatures"], outputCol="features")
        df_vectors = assembler.transform(df_features)
        
        # Fuzzy deduplication using MinHashLSH
        mh = MinHashLSH(
            inputCol="features", 
            outputCol="hashes", 
            numHashTables=10  # Increased for better recall
        )
        model = mh.fit(df_vectors)
        
        # Find similar pairs
        duplicates = model.approxSimilarityJoin(
            df_vectors, df_vectors, threshold, distCol="jaccardDist"
        ).filter("datasetA.id < datasetB.id")  # Avoid self-joins and duplicates
        
        # Select IDs to remove (keep the one with smaller ID)
        dup_ids_to_remove = duplicates.select(col("datasetB.id").alias("id")).distinct()
        
        # Remove fuzzy duplicates
        df_final = df_vectors.join(dup_ids_to_remove, "id", "left_anti")
        
        final_count = df_final.count()
        fuzzy_removed = exact_dedup_count - final_count
        
        logger.info(f"Fuzzy deduplication: {exact_dedup_count:,} → {final_count:,} ({fuzzy_removed:,} fuzzy duplicates removed)")
        
        # Clean up intermediate columns
        columns_to_drop = ["rawFeatures", "features", "hashes", "hash"]
        for col_name in columns_to_drop:
            if col_name in df_final.columns:
                df_final = df_final.drop(col_name)
                
        return df_final
        
    except Exception as e:
        logger.warning(f"Fuzzy deduplication failed: {e}. Falling back to exact deduplication only.")
        return df_exact.drop("hash")


def create_content_hash(text: str, algorithm: str = "sha256") -> str:
    """Create hash of text content with specified algorithm."""
    if not text:
        return None
        
    if algorithm == "sha256":
        return hashlib.sha256(text.encode()).hexdigest()
    elif algorithm == "md5":
        return hashlib.md5(text.encode()).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def estimate_dedup_savings(df: DataFrame, sample_fraction: float = 0.1) -> dict:
    """Estimate deduplication savings by sampling."""
    logger = logging.getLogger(__name__)
    
    try:
        # Sample data for estimation
        sample_df = df.sample(sample_fraction, seed=42)
        sample_count = sample_df.count()
        
        if sample_count == 0:
            return {"estimated_duplicates": 0, "estimated_savings_pct": 0}
        
        # Count unique hashes in sample
        unique_hashes = sample_df.select("hash").distinct().count()
        sample_duplicates = sample_count - unique_hashes
        
        # Estimate total duplicates
        estimated_total_duplicates = int(sample_duplicates / sample_fraction)
        total_rows = df.count()
        
        savings_pct = (estimated_total_duplicates / total_rows * 100) if total_rows > 0 else 0
        
        logger.info(f"Deduplication estimate: ~{estimated_total_duplicates:,} duplicates ({savings_pct:.1f}% of data)")
        
        return {
            "estimated_duplicates": estimated_total_duplicates,
            "estimated_savings_pct": savings_pct,
            "sample_size": sample_count
        }
        
    except Exception as e:
        logger.warning(f"Could not estimate deduplication savings: {e}")
        return {"estimated_duplicates": 0, "estimated_savings_pct": 0}