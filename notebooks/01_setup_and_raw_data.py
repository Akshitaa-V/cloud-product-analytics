# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Setup and raw data
# MAGIC Creates the schema and a Unity Catalog volume, then writes the raw source files
# MAGIC (accounts, users, monthly event files) into the volume.

# COMMAND ----------

# MAGIC %pip install -q pyyaml

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.raw")

# COMMAND ----------

from product_analytics.generate import GenConfig, generate

manifest = generate(RAW_PATH, GenConfig())
print({k: manifest[k] for k in ("accounts", "users", "clean_events", "raw_event_rows")})
print("injected problems:", manifest["issues"])

# COMMAND ----------

display(dbutils.fs.ls(f"{RAW_PATH}/events"))
