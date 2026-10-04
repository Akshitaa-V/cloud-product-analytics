# KPI library

Generated from `kpis/kpi_library.yml` by `python -m product_analytics.kpi_library`. Edit the YAML file, not this page.

| KPI | Question it answers | Owner | Grain | Table |
|---|---|---|---|---|
| [Active users and stickiness](#active-users) | How many people use the platform, and how often do they come back? | Product Management | one row per calendar day | `kpi_active_users` |
| [Activation rate](#activation) | Do new users reach their first moment of value in their first week? | Product Management | one row per signup week and main client (web or mobile) | `kpi_activation` |
| [Weekly cohort retention](#retention-weekly) | What share of each signup cohort is still active n weeks later? | Product Management | one row per signup week, activation segment and week number (0 to 12) | `kpi_retention_weekly` |
| [Feature adoption](#feature-adoption) | Which product features do active customer accounts use each month? | Product Management | one row per month and feature | `kpi_feature_adoption` |
| [Upload to share funnel](#upload-funnel) | How many uploaded datasets get processed, opened and shared? | Cloud Engineering | one row per upload month | `kpi_upload_funnel` |
| [Processing time and failure rate](#processing-time) | How long does dataset processing take, and how often does it fail? | Cloud Engineering | one row per week (Monday start) | `kpi_processing_time` |
| [Account health (seat utilisation)](#account-health) | Which customer accounts use far fewer seats than they pay for? | Customer Success | one row per customer account and month | `kpi_account_health` |

## active-users

**Active users and stickiness**

- **Question:** How many people use the platform, and how often do they come back?
- **Definition:** A user is active on a day when they send at least one valid event from a customer account. WAU and MAU count distinct active users in the 7 and 28 days ending on that date.
- **Formula:** `stickiness = DAU / MAU`
- **Grain:** one row per calendar day
- **Owner:** Product Management
- **SQL:** [`sql/gold/kpi_active_users.sql`](../sql/gold/kpi_active_users.sql)
- **Output columns:** `date`, `dau`, `wau`, `mau`, `stickiness`, `is_full_window`
- **Power BI measures:** Active Users, WAU (7d), MAU (28d), Stickiness (28d)
- **Caveats:** The first 27 days of the window do not have a full 28-day history; use is_full_window = true for trend charts. Internal test accounts are excluded.

## activation

**Activation rate**

- **Question:** Do new users reach their first moment of value in their first week?
- **Definition:** A new user is activated when they create a measurement or a share link within day 0 to day 6 after their account was created.
- **Formula:** `activation_rate = activated_users / new_users`
- **Grain:** one row per signup week and main client (web or mobile)
- **Owner:** Product Management
- **SQL:** [`sql/gold/kpi_activation.sql`](../sql/gold/kpi_activation.sql)
- **Output columns:** `signup_week`, `primary_client`, `new_users`, `activated_users`, `activation_rate`, `median_days_to_activation`
- **Power BI measures:** New Users, Activated Users, Activation Rate
- **Caveats:** Only users created inside the reporting window whose 7-day window has ended are counted, so the latest week is never half-measured.

## retention-weekly

**Weekly cohort retention**

- **Question:** What share of each signup cohort is still active n weeks later?
- **Definition:** Week n covers days 7n to 7n+6 after a user was created. A user is retained in week n when they are active on at least one day of that week.
- **Formula:** `retention_rate = retained_users / cohort_size`
- **Grain:** one row per signup week, activation segment and week number (0 to 12)
- **Owner:** Product Management
- **SQL:** [`sql/gold/kpi_retention_weekly.sql`](../sql/gold/kpi_retention_weekly.sql)
- **Output columns:** `signup_week`, `is_activated`, `week_number`, `cohort_size`, `retained_users`, `retention_rate`
- **Power BI measures:** Retention Rate
- **Caveats:** A cohort week is shown only after every user in the cohort could have reached it. Split by is_activated to compare activated and not activated users.

## feature-adoption

**Feature adoption**

- **Question:** Which product features do active customer accounts use each month?
- **Definition:** An account adopts a feature in a month when any of its users sends at least one event of that feature. The base is every account active that month.
- **Formula:** `adoption_rate = adopting_accounts / active_accounts`
- **Grain:** one row per month and feature
- **Owner:** Product Management
- **SQL:** [`sql/gold/kpi_feature_adoption.sql`](../sql/gold/kpi_feature_adoption.sql)
- **Output columns:** `month`, `feature`, `adopting_accounts`, `active_accounts`, `adoption_rate`
- **Power BI measures:** Feature Adoption Rate
- **Caveats:** Measured per account, not per user. A feature with no adopters in a month has no row for that month.

## upload-funnel

**Upload to share funnel**

- **Question:** How many uploaded datasets get processed, opened and shared?
- **Definition:** Each dataset moves through four steps - uploaded, processed successfully, opened in the viewer after processing, shared with a link after processing.
- **Formula:** `upload_to_share_rate = shared / uploaded`
- **Grain:** one row per upload month
- **Owner:** Cloud Engineering
- **SQL:** [`sql/gold/kpi_upload_funnel.sql`](../sql/gold/kpi_upload_funnel.sql)
- **Output columns:** `upload_month`, `uploaded`, `processed`, `viewed`, `shared`, `processed_rate`, `viewed_rate`, `shared_rate`, `upload_to_share_rate`
- **Power BI measures:** Uploads, Upload to Share Rate
- **Caveats:** Counts datasets, not events. Datasets uploaded late in the last month have had less time to be opened and shared.

## processing-time

**Processing time and failure rate**

- **Question:** How long does dataset processing take, and how often does it fail?
- **Definition:** Median and 90th percentile duration of successful processing jobs, and the share of finished jobs that failed. pipeline_version is the most common release in that week.
- **Formula:** `failure_rate = failed_jobs / (processed_jobs + failed_jobs)`
- **Grain:** one row per week (Monday start)
- **Owner:** Cloud Engineering
- **SQL:** [`sql/gold/kpi_processing_time.sql`](../sql/gold/kpi_processing_time.sql)
- **Output columns:** `week_start`, `processed_jobs`, `failed_jobs`, `median_processing_min`, `p90_processing_min`, `failure_rate`, `pipeline_version`
- **Power BI measures:** Processing Jobs, Median Processing (min), Processing Failure Rate
- **Caveats:** Weeks at the edges of the window are partial. Duration depends on dataset size, so compare weeks, not single jobs.

## account-health

**Account health (seat utilisation)**

- **Question:** Which customer accounts use far fewer seats than they pay for?
- **Definition:** Seat utilisation is the number of distinct active users in a month divided by the account's licensed seats. at_risk below 30 percent, watch from 30 to below 60 percent, healthy from 60 percent.
- **Formula:** `seat_utilization = active_users / seats`
- **Grain:** one row per customer account and month
- **Owner:** Customer Success
- **SQL:** [`sql/gold/kpi_account_health.sql`](../sql/gold/kpi_account_health.sql)
- **Output columns:** `month`, `account_id`, `plan`, `industry`, `seats`, `active_users`, `events`, `uploads`, `seat_utilization`, `health_status`
- **Power BI measures:** Seat Utilization, At-Risk Accounts
- **Caveats:** Thresholds are a starting point for Customer Success and should be tuned against real churn. Rows start in the account's signup month.
