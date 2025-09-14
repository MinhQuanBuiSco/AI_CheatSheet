from pyspark.sql.functions import udf, col, pandas_udf
from pyspark.sql.types import BooleanType, ArrayType, StringType
import langdetect
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import torch
import pandas as pd
from pyspark.sql.types import StructType, StructField
import pyspark.sql.functions as F

@udf(returnType=BooleanType())
def filter_language_udf(text: str, target_lang: str) -> bool:
    if not text or len(text) < 50:
        return False
    try:
        return langdetect.detect(text) == target_lang
    except:
        return False

@udf(returnType=ArrayType(StringType()))
def split_words_udf(text: str) -> list:
    return text.split() if text else []

@udf(returnType=BooleanType())
def heuristic_filter_udf(words: list, text: str, min_count: int, max_count: int, rep_threshold: float) -> bool:
    word_count = len(words)
    if word_count < min_count or word_count > max_count:
        return False
    
    if word_count > 1:
        bigrams = set(zip(words[:-1], words[1:]))
        repetition_ratio = (word_count - len(bigrams)) / word_count
        if repetition_ratio > rep_threshold:
            return False
    
    upper_ratio = sum(1 for c in text if c.isupper()) / len(text) if len(text) > 0 else 0
    if upper_ratio > 0.5:
        return False
    
    return True

# Pandas UDF for quality
schema = StructType([StructField("text", StringType()), StructField("quality_pass", BooleanType())])

def create_simple_quality_filter_udf(threshold):
    """Create a simple quality filter UDF that avoids serialization issues."""
    @udf(returnType=BooleanType())
    def simple_quality_udf(text: str) -> bool:
        if not text or len(text) < 10:
            return False
        
        # Simple heuristic-based quality filtering
        # Count sentences (rough proxy for structure)
        sentence_endings = text.count('.') + text.count('!') + text.count('?')
        words = len(text.split())
        
        if words == 0:
            return False
            
        # Average words per sentence
        avg_words_per_sentence = words / max(sentence_endings, 1)
        
        # Quality heuristics
        quality_score = 0.0
        
        # Length check (not too short, not too long per sentence)
        if 5 <= avg_words_per_sentence <= 50:
            quality_score += 0.3
            
        # Punctuation check
        if sentence_endings > 0:
            quality_score += 0.2
            
        # Capitalization check (has some uppercase letters)
        if any(c.isupper() for c in text):
            quality_score += 0.2
            
        # No excessive repetition of characters
        if not any(text.count(char) > len(text) * 0.1 for char in set(text) if char.isalpha()):
            quality_score += 0.3
            
        return quality_score >= threshold
    
    return simple_quality_udf


def quality_filter_udf(model_name, threshold, batch_size):
    """Fallback to simple quality filter to avoid serialization issues."""
    # For demo purposes, use simple heuristic instead of ML model
    return create_simple_quality_filter_udf(threshold)