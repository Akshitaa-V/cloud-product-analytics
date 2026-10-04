# Databricks notebook source
# MAGIC %md
# MAGIC # Shared configuration
# MAGIC Run by every pipeline notebook with `%run ./_config`. Sets the catalog, schema and
# MAGIC raw-file volume, and makes the `product_analytics` package in `src/` importable.

# COMMAND ----------

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.getcwd(), ".."))
SRC = os.path.join(REPO_ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "product_analytics")
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
RAW_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/raw"

spark.conf.set("spark.sql.session.timeZone", "UTC")

from product_analytics.config import PipelineConfig  # noqa: E402
from product_analytics.spark_utils import TableStore  # noqa: E402

cfg = PipelineConfig(
    mode="databricks",
    raw_path=RAW_PATH,
    catalog=CATALOG,
    schema=SCHEMA,
    kpi_library_path=os.path.join(REPO_ROOT, "kpis", "kpi_library.yml"),
    sql_root=REPO_ROOT,
)
store = TableStore(spark, cfg)
print(f"catalog={CATALOG} schema={SCHEMA} raw={RAW_PATH}")
