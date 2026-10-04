-- KPI: dataset processing time and failure rate
-- Grain: one row per week (Monday start).
-- Median and 90th percentile cover successful jobs; the failure rate covers
-- all finished jobs. pipeline_version shows the release most jobs ran on.
SELECT
    trunc(event_date, 'WEEK')                                                     AS week_start,
    SUM(CASE WHEN event_name = 'dataset_processed' THEN 1 ELSE 0 END)             AS processed_jobs,
    SUM(CASE WHEN event_name = 'dataset_processing_failed' THEN 1 ELSE 0 END)     AS failed_jobs,
    ROUND(percentile(CASE WHEN event_name = 'dataset_processed' THEN duration_s END, 0.5) / 60, 1) AS median_processing_min,
    ROUND(percentile(CASE WHEN event_name = 'dataset_processed' THEN duration_s END, 0.9) / 60, 1) AS p90_processing_min,
    ROUND(
        SUM(CASE WHEN event_name = 'dataset_processing_failed' THEN 1 ELSE 0 END)
        / COUNT(*), 4)                                                            AS failure_rate,
    mode(pipeline_version)                                                        AS pipeline_version
FROM fact_events
WHERE event_name IN ('dataset_processed', 'dataset_processing_failed')
GROUP BY trunc(event_date, 'WEEK')
ORDER BY week_start
