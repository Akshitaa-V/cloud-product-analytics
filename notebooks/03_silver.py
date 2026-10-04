# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Silver
# MAGIC Deduplicates events, parses timestamps (ISO 8601 and epoch milliseconds), checks six
# MAGIC data quality rules and moves failing rows to `silver_quarantine` with a reason.

# COMMAND ----------

# MAGIC %pip install -q pyyaml

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

from product_analytics.pipeline import run_silver

run_silver(spark, cfg, store)

# COMMAND ----------

display(spark.table(f"{CATALOG}.{SCHEMA}.silver_dq_summary"))

# COMMAND ----------

display(spark.sql(f"""
    SELECT dq_reason, event_name, event_ts, user_id, _source_file
    FROM {CATALOG}.{SCHEMA}.silver_quarantine
    ORDER BY dq_reason
    LIMIT 50
"""))
