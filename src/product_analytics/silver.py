"""Silver layer: deduplicate, parse, validate and conform.

Rows that break a rule are not dropped. They move to a quarantine table with
the first rule they broke, so every removed row can be explained and counted.

Rules, checked in this order:

1. missing_user_id         the event has no user id
2. unknown_user            the user id does not exist in the user table
3. unknown_event_name      the event name is not in the tracking plan
4. unparseable_timestamp   the timestamp is neither ISO 8601 nor epoch milliseconds
5. timestamp_out_of_range  the timestamp falls outside the reporting window
6. invalid_dataset_size    an upload reports a size of zero, below zero or none
"""
from __future__ import annotations

from datetime import date

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import LongType, StringType, StructField, StructType

from .config import VALID_EVENT_NAMES

RULES = (
    "missing_user_id",
    "unknown_user",
    "unknown_event_name",
    "unparseable_timestamp",
    "timestamp_out_of_range",
    "invalid_dataset_size",
)
ISO_FORMAT = "yyyy-MM-dd'T'HH:mm:ss'Z'"


def parse_event_timestamp(col: F.Column) -> F.Column:
    """ISO 8601 (``2026-03-04T10:15:00Z``) or epoch milliseconds (13 digits) -> timestamp."""
    return F.when(col.rlike(r"^[0-9]{13}$"), F.timestamp_millis(col.cast(LongType()))).otherwise(
        F.try_to_timestamp(col, F.lit(ISO_FORMAT))
    )


def build_users(bronze_users: DataFrame) -> DataFrame:
    return (
        bronze_users.dropDuplicates(["user_id"])
        .withColumn("created_at", F.try_to_timestamp(F.col("created_at"), F.lit(ISO_FORMAT)))
        .withColumn("created_date", F.to_date("created_at"))
        .select("user_id", "account_id", "role", "primary_client", "created_at", "created_date")
    )


def build_accounts(bronze_accounts: DataFrame) -> DataFrame:
    return (
        bronze_accounts.dropDuplicates(["account_id"])
        .withColumn("seats", F.col("seats").cast("int"))
        .withColumn("signup_date", F.to_date("signup_date"))
        .withColumn("is_internal", F.lower(F.col("is_internal")) == F.lit("true"))
        .select("account_id", "account_name", "industry", "country", "plan", "seats", "signup_date", "is_internal")
    )


def build_events(
    bronze_events: DataFrame,
    users: DataFrame,
    accounts: DataFrame,
    window_start: date,
    window_end: date,
) -> tuple[DataFrame, DataFrame]:
    """Return (valid events, quarantined rows)."""
    deduped = bronze_events.dropDuplicates(["event_id"])

    known_users = users.select(
        F.col("user_id").alias("_known_user_id"), F.col("account_id").alias("_user_account_id")
    )
    parsed = (
        deduped.withColumn("event_ts_parsed", parse_event_timestamp(F.col("event_ts")))
        .withColumn("ts_was_epoch", F.coalesce(F.col("event_ts").rlike(r"^[0-9]{13}$"), F.lit(False)))
        .join(F.broadcast(known_users), F.col("user_id") == F.col("_known_user_id"), "left")
    )

    event_date = F.to_date("event_ts_parsed")
    size = F.col("properties.size_gb")
    reason = (
        F.when(F.col("user_id").isNull(), "missing_user_id")
        .when(F.col("_known_user_id").isNull(), "unknown_user")
        .when(~F.col("event_name").isin(*VALID_EVENT_NAMES) | F.col("event_name").isNull(), "unknown_event_name")
        .when(F.col("event_ts_parsed").isNull(), "unparseable_timestamp")
        .when((event_date < F.lit(window_start)) | (event_date > F.lit(window_end)), "timestamp_out_of_range")
        .when((F.col("event_name") == "dataset_upload") & (size.isNull() | (size <= 0)), "invalid_dataset_size")
    )
    checked = parsed.withColumn("dq_reason", reason)

    quarantine = checked.where(F.col("dq_reason").isNotNull()).select(
        "event_id", "user_id", "account_id", "event_name", "event_ts", "client", "app_version",
        F.to_json("properties").alias("properties_json"), "dq_reason", "_source_file",
    )

    internal = accounts.select(F.col("account_id").alias("_acc_id"), "is_internal")
    valid = (
        checked.where(F.col("dq_reason").isNull())
        .withColumn("account_id", F.coalesce(F.col("_user_account_id"), F.col("account_id")))
        .join(F.broadcast(internal), F.col("account_id") == F.col("_acc_id"), "left")
        .select(
            "event_id",
            "user_id",
            "account_id",
            "event_name",
            F.col("event_ts_parsed").alias("event_ts"),
            F.to_date("event_ts_parsed").alias("event_date"),
            "client",
            "app_version",
            F.col("properties.dataset_id").alias("dataset_id"),
            F.col("properties.size_gb").alias("size_gb"),
            F.col("properties.duration_s").alias("duration_s"),
            F.col("properties.status").alias("status"),
            F.col("properties.pipeline_version").alias("pipeline_version"),
            "ts_was_epoch",
            F.coalesce(F.col("is_internal"), F.lit(False)).alias("is_internal"),
            "_source_file",
        )
    )
    return valid, quarantine


def build_dq_summary(
    spark: SparkSession, bronze_events: DataFrame, valid: DataFrame, quarantine: DataFrame
) -> DataFrame:
    """One row per check with the number of affected rows. Small table, so counting is cheap."""
    raw_rows = bronze_events.count()
    unique_rows = bronze_events.select("event_id").distinct().count()
    by_reason = {r["dq_reason"]: r["n"] for r in quarantine.groupBy("dq_reason").agg(F.count("*").alias("n")).collect()}
    valid_rows = valid.count()
    epoch_rows = valid.where("ts_was_epoch").count()
    internal_rows = valid.where("is_internal").count()

    rows = [("raw_rows", "info", raw_rows), ("duplicate_event_id", "removed", raw_rows - unique_rows)]
    rows += [(rule, "quarantined", int(by_reason.get(rule, 0))) for rule in RULES]
    rows += [
        ("epoch_timestamp_normalized", "fixed", epoch_rows),
        ("internal_account_event", "excluded_from_kpis", internal_rows),
        ("valid_rows", "info", valid_rows),
    ]
    schema = StructType(
        [StructField("check", StringType()), StructField("action", StringType()), StructField("rows", LongType())]
    )
    df = spark.createDataFrame([(c, a, int(n)) for c, a, n in rows], schema)
    return df.withColumn("share_of_raw", F.round(F.col("rows") / F.lit(raw_rows), 5))
