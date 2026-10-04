-- KPI: monthly account health (seat utilisation)
-- Grain: one row per customer account and month, from the account's signup month on.
-- Seat utilisation = distinct active users in the month / licensed seats.
-- Status: at_risk below 30 %, watch from 30 % to below 60 %, healthy from 60 %.
WITH usage AS (
    SELECT
        trunc(activity_date, 'MM')  AS month,
        account_id,
        COUNT(DISTINCT user_id)     AS active_users,
        SUM(events)                 AS events,
        SUM(uploads)                AS uploads
    FROM fact_user_daily
    GROUP BY trunc(activity_date, 'MM'), account_id
),
months AS (
    SELECT DISTINCT month_start AS month FROM dim_date
)
SELECT
    m.month,
    a.account_id,
    a.plan,
    a.industry,
    a.seats,
    COALESCE(u.active_users, 0)                             AS active_users,
    COALESCE(u.events, 0)                                   AS events,
    COALESCE(u.uploads, 0)                                  AS uploads,
    ROUND(COALESCE(u.active_users, 0) / a.seats, 4)         AS seat_utilization,
    CASE
        WHEN COALESCE(u.active_users, 0) / a.seats < 0.3 THEN 'at_risk'
        WHEN COALESCE(u.active_users, 0) / a.seats < 0.6 THEN 'watch'
        ELSE 'healthy'
    END                                                     AS health_status
FROM dim_account AS a
CROSS JOIN months AS m
LEFT JOIN usage AS u
    ON u.account_id = a.account_id
   AND u.month = m.month
WHERE trunc(a.signup_date, 'MM') <= m.month
ORDER BY m.month, a.account_id
