-- KPI: dataset funnel from upload to share
-- Grain: one row per upload month.
-- Steps per dataset: uploaded -> processed successfully -> opened in the viewer
-- after processing -> shared with a link. Each step counts datasets, not events.
WITH ds AS (
    SELECT
        dataset_id,
        MIN(CASE WHEN event_name = 'dataset_upload' THEN event_ts END)            AS uploaded_at,
        MIN(CASE WHEN event_name = 'dataset_processed' THEN event_ts END)         AS processed_at,
        MIN(CASE WHEN event_name = 'viewer_open' THEN event_ts END)               AS first_viewed_at,
        MIN(CASE WHEN event_name = 'share_link_created' THEN event_ts END)        AS first_shared_at
    FROM fact_events
    WHERE dataset_id IS NOT NULL
    GROUP BY dataset_id
),
steps AS (
    SELECT
        trunc(to_date(uploaded_at), 'MM')                                          AS upload_month,
        1                                                                          AS uploaded,
        CASE WHEN processed_at IS NOT NULL THEN 1 ELSE 0 END                       AS processed,
        CASE WHEN processed_at IS NOT NULL AND first_viewed_at >= processed_at THEN 1 ELSE 0 END AS viewed,
        CASE WHEN processed_at IS NOT NULL AND first_shared_at >= processed_at THEN 1 ELSE 0 END AS shared
    FROM ds
    WHERE uploaded_at IS NOT NULL
)
SELECT
    upload_month,
    SUM(uploaded)                                   AS uploaded,
    SUM(processed)                                  AS processed,
    SUM(viewed)                                     AS viewed,
    SUM(shared)                                     AS shared,
    ROUND(SUM(processed) / SUM(uploaded), 4)        AS processed_rate,
    ROUND(SUM(viewed) / NULLIF(SUM(processed), 0), 4) AS viewed_rate,
    ROUND(SUM(shared) / NULLIF(SUM(viewed), 0), 4)  AS shared_rate,
    ROUND(SUM(shared) / SUM(uploaded), 4)           AS upload_to_share_rate
FROM steps
GROUP BY upload_month
ORDER BY upload_month
