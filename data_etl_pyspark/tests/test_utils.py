import pytest
from pyspark.sql import SparkSession
from utils.cleaning import clean_text_udf

@pytest.fixture(scope="session")
def spark():
    return SparkSession.builder.master("local[2]").appName("tests").getOrCreate()

def test_clean_text_udf(spark):
    df = spark.createDataFrame([("Hello   world! test@email.com 123-456-7890",)], ["text"])
    result = df.withColumn("cleaned", clean_text_udf(col("text"))).collect()[0]["cleaned"]
    assert result == "Hello world! [EMAIL] [PHONE]"