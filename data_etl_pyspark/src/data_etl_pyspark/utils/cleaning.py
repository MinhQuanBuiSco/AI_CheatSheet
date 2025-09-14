from pyspark.sql.functions import udf
from pyspark.sql.types import StringType
import unicodedata
import re

@udf(returnType=StringType())
def clean_text_udf(text: str) -> str:
    if not text:
        return None
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
    text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', text)
    return text