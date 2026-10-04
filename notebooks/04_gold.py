# Databricks notebook source
# MAGIC %md
# MAGIC # 04 · Gold
# MAGIC Builds the star schema (`gold_dim_*`, `gold_fact_*`) and every KPI table listed in
# MAGIC `kpis/kpi_library.yml` from the SQL files in `sql/gold/`.

# COMMAND ----------

# MAGIC %pip install -q pyyaml

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

from product_analytics.pipeline import run_gold

run_gold(spark, cfg, store)

# COMMAND ----------

display(spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA} LIKE 'gold_*'"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Quick checks

# COMMAND ----------

display(spark.sql(f"""
    SELECT date, dau, wau, mau, stickiness
    FROM {CATALOG}.{SCHEMA}.gold_kpi_active_users
    WHERE is_full_window
    ORDER BY date
"""))

# COMMAND ----------

display(spark.sql(f"""
    SELECT week_start, median_processing_min, p90_processing_min, failure_rate, pipeline_version
    FROM {CATALOG}.{SCHEMA}.gold_kpi_processing_time
    ORDER BY week_start
"""))
