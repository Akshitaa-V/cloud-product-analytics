# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Bronze
# MAGIC Loads the raw files into Delta tables as they are, with the source file name and load time.

# COMMAND ----------

# MAGIC %pip install -q pyyaml

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

from product_analytics.pipeline import run_bronze

run_bronze(spark, cfg, store)

# COMMAND ----------

display(spark.sql(f"""
    SELECT _source_file, COUNT(*) AS rows
    FROM {CATALOG}.{SCHEMA}.bronze_events
    GROUP BY _source_file
    ORDER BY _source_file
"""))
