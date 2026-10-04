"""Spark session and table storage for local runs and Databricks."""
from __future__ import annotations

import shutil
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession

from .config import PipelineConfig


def get_spark(app_name: str = "product-analytics") -> SparkSession:
    """Return the active session (Databricks) or start a local one."""
    active = SparkSession.getActiveSession()
    if active is not None:
        active.conf.set("spark.sql.session.timeZone", "UTC")
        return active
    spark = (
        SparkSession.builder.master("local[*]")
        .appName(app_name)
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.ui.enabled", "false")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.driver.memory", "2g")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def as_spark_path(path: str) -> str:
    """Local paths become absolute POSIX paths (works on Windows too); /Volumes paths stay as they are."""
    if path.startswith("/Volumes/") or "://" in path:
        return path
    return Path(path).resolve().as_posix()


class TableStore:
    """Reads and writes pipeline tables.

    local:       one Parquet file per table under ``lake_path/<layer>/<name>.parquet``.
                 Written through Arrow, so no Hadoop/winutils setup is needed on Windows.
    databricks:  Delta tables named ``<catalog>.<schema>.<layer>_<name>``.
    """

    def __init__(self, spark: SparkSession, cfg: PipelineConfig):
        self.spark = spark
        self.cfg = cfg

    def table_name(self, layer: str, name: str) -> str:
        return f"{self.cfg.catalog}.{self.cfg.schema}.{layer}_{name}"

    def _local_file(self, layer: str, name: str) -> Path:
        return Path(self.cfg.lake_path) / layer / f"{name}.parquet"

    def write(self, df: DataFrame, layer: str, name: str) -> DataFrame:
        if self.cfg.mode == "databricks":
            (
                df.write.mode("overwrite")
                .option("overwriteSchema", "true")
                .saveAsTable(self.table_name(layer, name))
            )
            return self.spark.table(self.table_name(layer, name))

        import pyarrow.parquet as pq

        target = self._local_file(layer, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_dir():
            shutil.rmtree(target)
        pq.write_table(df.toArrow(), target)
        return self.read(layer, name)

    def read(self, layer: str, name: str) -> DataFrame:
        if self.cfg.mode == "databricks":
            return self.spark.table(self.table_name(layer, name))

        import pyarrow.parquet as pq

        return self.spark.createDataFrame(pq.read_table(self._local_file(layer, name)))
