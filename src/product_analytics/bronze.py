"""Bronze layer: load the raw files as they are, with load metadata.

Nothing is cleaned here. Every column stays a string where the source is a
string, so that broken values survive and can be inspected in the silver layer.
"""
from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, StringType, StructField, StructType

from .spark_utils import as_spark_path

EVENT_SCHEMA = StructType(
    [
        StructField("event_id", StringType()),
        StructField("user_id", StringType()),
        StructField("account_id", StringType()),
        StructField("event_name", StringType()),
        StructField("event_ts", StringType()),
        StructField("client", StringType()),
        StructField("app_version", StringType()),
        StructField(
            "properties",
            StructType(
                [
                    StructField("dataset_id", StringType()),
                    StructField("size_gb", DoubleType()),
                    StructField("duration_s", DoubleType()),
                    StructField("status", StringType()),
                    StructField("pipeline_version", StringType()),
                ]
            ),
        ),
    ]
)

ACCOUNT_SCHEMA = StructType(
    [StructField(c, StringType()) for c in
     ["account_id", "account_name", "industry", "country", "plan", "seats", "signup_date", "is_internal"]]
)
USER_SCHEMA = StructType(
    [StructField(c, StringType()) for c in ["user_id", "account_id", "role", "primary_client", "created_at"]]
)


def _with_load_metadata(df: DataFrame) -> DataFrame:
    return df.withColumn("_source_file", F.element_at(F.split(F.col("_metadata.file_path"), "/"), -1)).withColumn(
        "_ingested_at", F.current_timestamp()
    )


def load_bronze(spark: SparkSession, raw_path: str) -> dict[str, DataFrame]:
    root = as_spark_path(raw_path).rstrip("/")
    events = spark.read.schema(EVENT_SCHEMA).option("pathGlobFilter", "*.jsonl").json(f"{root}/events")
    accounts = spark.read.schema(ACCOUNT_SCHEMA).option("header", True).csv(f"{root}/accounts.csv")
    users = spark.read.schema(USER_SCHEMA).option("header", True).csv(f"{root}/users.csv")
    return {
        "events": _with_load_metadata(events),
        "accounts": _with_load_metadata(accounts),
        "users": _with_load_metadata(users),
    }
