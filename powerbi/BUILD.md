# Power BI report: build guide

This guide builds a three-page Power BI report on top of the gold layer. You can load the
data in two ways:

- **Option A, CSV (simplest):** the files in `data/powerbi/` created by `python -m product_analytics.run`.
- **Option B, Databricks:** connect Power BI straight to the `gold_*` Delta tables in Databricks.

Both give the same model. Plan about one to two hours for the first build.

## 1. Load the data

### Option A: CSV files

1. Run the pipeline once: `python -m product_analytics.run` (see the main README).
2. Open Power BI Desktop → **Get data** → **Text/CSV**.
3. Load each of these files from `data/powerbi/` (one at a time, click **Load**):
   `dim_date`, `dim_account`, `dim_user`, `fact_events`, `fact_user_daily`,
   `kpi_retention_weekly`, `kpi_feature_adoption`, `kpi_upload_funnel`,
   `kpi_processing_time`, `kpi_account_health`.
4. Keep the table names exactly as the file names (the DAX measures use them).

### Option B: Databricks

1. Run the notebooks `01` to `04` in Databricks (see `docs/databricks.md`).
2. In Databricks, open **SQL Warehouses** → your warehouse → **Connection details**. Copy
   **Server hostname** and **HTTP path**.
3. In Databricks, create a personal access token: your user icon → **Settings** →
   **Developer** → **Access tokens** → **Generate new token**.
4. In Power BI Desktop → **Get data** → search **Azure Databricks** (works for any Databricks
   workspace) → paste hostname and HTTP path → **Import** → sign in with the token.
5. Select the tables `workspace.product_analytics.gold_*` listed in Option A.
6. Rename each query to drop the `gold_` prefix (for example `gold_dim_date` → `dim_date`),
   so the DAX measures find their tables.

## 2. Check data types (Power Query)

Power BI usually detects these correctly. Open **Transform data** and confirm:

| Table | Column | Type |
|---|---|---|
| dim_date | date, month_start, week_start | Date |
| dim_user | created_date, signup_week, activation_date | Date |
| dim_user | is_new_in_window, activation_window_complete, is_activated | True/False |
| fact_events, fact_user_daily | event_date / activity_date | Date |
| fact_events | duration_s, size_gb | Decimal number |
| kpi_* | month, week_start, upload_month, signup_week | Date |
| kpi_* | *_rate, seat_utilization | Decimal number |

Click **Close & Apply**.

## 3. Mark the date table

Select `dim_date` → **Table tools** → **Mark as date table** → choose the column `date`.

## 4. Relationships (star schema)

Open **Model view** and create these relationships (many-to-one, single direction):

| From (many) | To (one) |
|---|---|
| fact_events[event_date] | dim_date[date] |
| fact_events[user_id] | dim_user[user_id] |
| fact_events[account_id] | dim_account[account_id] |
| fact_user_daily[activity_date] | dim_date[date] |
| fact_user_daily[user_id] | dim_user[user_id] |
| fact_user_daily[account_id] | dim_account[account_id] |
| kpi_account_health[account_id] | dim_account[account_id] |

Do **not** link `dim_user` to `dim_account`. The facts already reach both, and a third path
would make the model ambiguous. Delete any relationship Power BI created on its own that is
not in this table.

The other KPI tables stay unlinked. They are already aggregated by the SQL in `sql/gold/`.

## 5. Add the measures

1. Open **DAX query view** (left sidebar).
2. Paste the whole content of `powerbi/measures.dax` → **Run**.
3. Click **Update model: Add new measures** above `DEFINE`.
4. Set formats: select each measure → **Measure tools**:
   - Percent with 1 decimal: `Stickiness (28d)`, `Activation Rate`, `Retention Rate`,
     `Feature Adoption Rate`, `Processing Failure Rate`, `Upload to Share Rate`, `Seat Utilization`
   - Decimal with 1 decimal: `Median Processing (min)`
   - Whole number: the rest

## 6. Build the three pages

### Page 1: Engagement overview

- Cards: `MAU (28d)`, `Stickiness (28d)`, `Activation Rate`, `Seat Utilization`.
- Line chart: X axis `dim_date[date]`, values `Active Users`, `WAU (7d)`, `MAU (28d)`.
  Add a filter on `dim_date[date]` from 2026-01-28 so MAU starts with a full 28-day window.
- Slicers: `dim_account[plan]`, `dim_account[industry]`, `dim_account[country]`.

### Page 2: Activation and retention

- Clustered bar chart: Y axis `dim_user[primary_client]`, X axis `Activation Rate`.
- Line chart: X axis `kpi_retention_weekly[week_number]`, Y axis `Retention Rate`,
  legend `kpi_retention_weekly[is_activated]`.
- Matrix (cohort table): rows `kpi_retention_weekly[signup_week]`, columns
  `kpi_retention_weekly[week_number]`, values `Retention Rate`. Turn on **Conditional
  formatting → Background color** for a heatmap.

### Page 3: Upload pipeline and account health

- Upload funnel: clustered column chart with `kpi_upload_funnel[upload_month]` on the X axis
  and `uploaded`, `processed`, `viewed`, `shared` (Sum) as values. Add a card with
  `Upload to Share Rate`.
- Line and clustered column chart: X axis `dim_date[week_start]`, line `Median Processing (min)`,
  columns `Processing Failure Rate`.
- Table: `kpi_account_health` columns `account_id`, `plan`, `seats`, `active_users`,
  `seat_utilization`, `health_status`. Filter `month` to the latest month and
  `health_status` = `at_risk`. Sort by `seat_utilization` ascending.

## 7. Check your numbers

With the default data (seed 42, 200 accounts), these values match the pipeline. If yours
differ, check the relationships and the date-table setting first.

| Measure (no filters) | Expected |
|---|---|
| Active Users | 1,753 |
| MAU (28d) on 2026-06-30 | 1,271 |
| Activation Rate | 55.7 % (517 of 929 new users) |
| Uploads | 2,154 |
| Processing Failure Rate | 5.2 % |
| Median Processing (min) | 16.2 |
| Upload to Share Rate | 34.3 % |
| At-Risk Accounts (June 2026) | 19 |

## 8. Save and publish to GitHub

1. Save as `powerbi/product_analytics.pbix`.
2. **File → Export → Export to PDF** → save as `powerbi/product_analytics_report.pdf`.
3. Take a screenshot of each page and save them as `docs/img/powerbi_engagement.png`,
   `docs/img/powerbi_retention.png`, `docs/img/powerbi_pipeline.png`.
4. Uncomment the screenshot block in `README.md`, then commit and push.
