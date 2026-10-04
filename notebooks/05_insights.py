# Databricks notebook source
# MAGIC %md
# MAGIC # 05 · Insights
# MAGIC Computes the findings from the gold KPI tables and prints the insights report.

# COMMAND ----------

# MAGIC %pip install -q pyyaml

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

from product_analytics.insights import compute_insights, render_report

names = [
    "kpi_active_users", "kpi_activation", "kpi_retention_weekly", "kpi_feature_adoption",
    "kpi_upload_funnel", "kpi_processing_time", "kpi_account_health",
]
tables = {n: store.read("gold", n).toPandas() for n in names}
tables["dq_summary"] = store.read("silver", "dq_summary").toPandas()

print(render_report(compute_insights(tables)))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Retention by activation segment

# COMMAND ----------

display(spark.sql(f"""
    SELECT week_number,
           is_activated,
           ROUND(SUM(retained_users) / SUM(cohort_size), 3) AS retention_rate
    FROM {CATALOG}.{SCHEMA}.gold_kpi_retention_weekly
    GROUP BY week_number, is_activated
    ORDER BY week_number, is_activated
"""))
