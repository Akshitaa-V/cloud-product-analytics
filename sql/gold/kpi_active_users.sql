-- KPI: active users (DAU / WAU / MAU) and stickiness
-- Grain: one row per calendar day.
-- A user is active on a day when they send at least one valid event.
-- WAU and MAU are rolling windows of 7 and 28 days ending on the row's date.
SELECT
    d.date,
    COUNT(DISTINCT CASE WHEN a.activity_date = d.date THEN a.user_id END)                  AS dau,
    COUNT(DISTINCT CASE WHEN a.activity_date >= date_sub(d.date, 6) THEN a.user_id END)    AS wau,
    COUNT(DISTINCT a.user_id)                                                               AS mau,
    ROUND(
        COUNT(DISTINCT CASE WHEN a.activity_date = d.date THEN a.user_id END)
        / NULLIF(COUNT(DISTINCT a.user_id), 0), 4)                                          AS stickiness,
    d.date >= date_add(:window_start, 27)                                                   AS is_full_window
FROM dim_date AS d
LEFT JOIN fact_user_daily AS a
    ON a.activity_date BETWEEN date_sub(d.date, 27) AND d.date
GROUP BY d.date
ORDER BY d.date
