from pyspark.sql import DataFrame
from pyspark.sql.functions import udf, col
from pyspark.sql.types import StringType
from pyspark.ml.feature import MinHashLSH, HashingTF, VectorAssembler
import hashlib

@udf(returnType=StringType())
def hash_text_udf(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

def deduplicate_df(df: DataFrame, threshold: float) -> DataFrame:
    # Exact dedup
    df = df.dropDuplicates(['hash'])
    
    # Fuzzy dedup
    hashingTF = HashingTF(inputCol="words", outputCol="rawFeatures", numFeatures=1024)
    df = hashingTF.transform(df)
    
    assembler = VectorAssembler(inputCols=["rawFeatures"], outputCol="features")
    df = assembler.transform(df)
    
    mh = MinHashLSH(inputCol="features", outputCol="hashes", numHashTables=5)
    model = mh.fit(df)
    
    duplicates = model.approxSimilarityJoin(df, df, threshold, distCol="jaccardDist") \
        .filter("datasetA.id != datasetB.id") \
        .select(col("datasetA.id").alias("idA"), col("datasetB.id").alias("idB"), "jaccardDist")
    
    dup_ids = duplicates.select("idB").distinct()
    df = df.join(dup_ids, df.id == dup_ids.idB, "left_anti")
    
    return df