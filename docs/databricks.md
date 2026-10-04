# Running the pipeline on Databricks

The notebooks in `notebooks/` run the same code as the local pipeline, but store every
table as a Delta table in Unity Catalog. They work on the free
[Databricks Free Edition](https://www.databricks.com/learn/free-edition) with serverless compute.

## 1. Get the repository into Databricks

1. Sign in to Databricks Free Edition.
2. **Workspace** → **Create** → **Git folder**.
3. Paste the repository URL (`https://github.com/Akshitaa-V/cloud-product-analytics`) → **Create Git folder**.

## 2. Run the notebooks in order

Open each notebook in `notebooks/`, attach **Serverless** compute and click **Run all**:

| Notebook | What it does | Creates |
|---|---|---|
| `01_setup_and_raw_data` | Creates schema `workspace.product_analytics` and a volume, writes the raw files | volume `raw` |
| `02_bronze` | Loads raw files as they are | `bronze_events`, `bronze_accounts`, `bronze_users` |
| `03_silver` | Deduplicates, parses, validates, quarantines | `silver_events`, `silver_quarantine`, `silver_dq_summary`, ... |
| `04_gold` | Star schema and KPI tables | `gold_dim_*`, `gold_fact_*`, `gold_kpi_*` |
| `05_insights` | Prints the insights report from the KPI tables | – |

`_config` is not run directly; every notebook loads it with `%run ./_config`. The widgets
`catalog` and `schema` at the top of each notebook change where the tables go
(default `workspace.product_analytics`).

## 3. Schedule it as a job (optional)

1. **Jobs & Pipelines** → **Create** → **Job**.
2. Add four tasks of type **Notebook**, each with source **Workspace** pointing to the
   notebooks `02_bronze`, `03_silver`, `04_gold`, `05_insights` in your Git folder.
3. Make each task depend on the one before it. Use **Serverless** compute.
4. Add a daily schedule if you want, then **Run now**.

## 4. Explore with SQL

In the **SQL Editor**, for example:

```sql
SELECT week_start, median_processing_min, failure_rate, pipeline_version
FROM workspace.product_analytics.gold_kpi_processing_time
ORDER BY week_start;
```

## 5. Connect Power BI

See [`powerbi/BUILD.md`](../powerbi/BUILD.md), option B.

## Notes

- Raw data is generated inside the workspace, so no upload is needed.
- Re-running a notebook overwrites its tables; the pipeline is idempotent.
- The local Parquet store and the Databricks Delta store are chosen by
  `PipelineConfig(mode=...)`; the transformation code is the same in both.
