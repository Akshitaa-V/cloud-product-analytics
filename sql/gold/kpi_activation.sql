-- KPI: activation rate of new users
-- Grain: one row per signup week and main client (web / mobile).
-- A new user is activated when they create a measurement or a share link
-- within their first 7 days (day 0 to day 6). Only cohorts whose 7-day
-- window is fully inside the reporting period are included.
SELECT
    signup_week,
    primary_client,
    COUNT(*)                                                    AS new_users,
    SUM(CASE WHEN is_activated THEN 1 ELSE 0 END)              AS activated_users,
    ROUND(SUM(CASE WHEN is_activated THEN 1 ELSE 0 END) / COUNT(*), 4) AS activation_rate,
    percentile(days_to_activation, 0.5)                         AS median_days_to_activation
FROM dim_user
WHERE is_new_in_window
  AND activation_window_complete
GROUP BY signup_week, primary_client
ORDER BY signup_week, primary_client
