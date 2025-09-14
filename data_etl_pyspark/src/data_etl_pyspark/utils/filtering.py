from pyspark.sql.functions import udf, col
from pyspark.sql.types import BooleanType, ArrayType, StringType
import langdetect
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import torch
import pandas as pd
from pyspark.sql.types import StructType, StructField

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

def quality_filter_udf(model_name, threshold, batch_size):
    @F.pandas_udf(schema, F.PandasUDFType.GROUPED_MAP)
    def udf_func(pdf: pd.DataFrame) -> pd.DataFrame:
        device = 0 if torch.cuda.is_available() else -1
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)
        pipe = pipeline("sentiment-analysis", model=model, tokenizer=tokenizer, device=device)
        
        texts = pdf['text'].tolist()
        results = pipe(texts, batch_size=batch_size, truncation=True, max_length=512)
        pdf['quality_pass'] = [res['score'] > threshold and res['label'] == 'POSITIVE' for res in results]
        return pdf
    return udf_func