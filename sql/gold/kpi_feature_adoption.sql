-- KPI: monthly feature adoption across customer accounts
-- Grain: one row per month and feature.
-- An account adopts a feature in a month when any of its users sends at least
-- one event of that feature. The base is every account active in that month.
WITH monthly AS (
    SELECT trunc(event_date, 'MM') AS month, account_id, feature
    FROM fact_events
),
active AS (
    SELECT month, COUNT(DISTINCT account_id) AS active_accounts
    FROM monthly
    GROUP BY month
),
used AS (
    SELECT month, feature, COUNT(DISTINCT account_id) AS adopting_accounts
    FROM monthly
    WHERE feature IS NOT NULL
    GROUP BY month, feature
)
SELECT
    u.month,
    u.feature,
    u.adopting_accounts,
    a.active_accounts,
    ROUND(u.adopting_accounts / a.active_accounts, 4) AS adoption_rate
FROM used AS u
JOIN active AS a ON a.month = u.month
ORDER BY u.month, u.feature
