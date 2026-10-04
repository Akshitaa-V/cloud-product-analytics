-- KPI: weekly cohort retention
-- Grain: one row per signup week, activation segment and week number (0 to 12).
-- Week n of a user covers days 7n to 7n+6 after the user was created.
-- A cohort week is only reported once every user in the cohort could have
-- reached it, so recent cohorts do not look worse than they are.
WITH cohort AS (
    SELECT user_id, signup_week, created_date, is_activated
    FROM dim_user
    WHERE is_new_in_window
),
activity AS (
    SELECT DISTINCT
        c.signup_week,
        c.is_activated,
        c.user_id,
        CAST(FLOOR(datediff(a.activity_date, c.created_date) / 7) AS INT) AS week_number
    FROM cohort AS c
    JOIN fact_user_daily AS a
        ON a.user_id = c.user_id
       AND a.activity_date >= c.created_date
),
sizes AS (
    SELECT signup_week, is_activated, COUNT(*) AS cohort_size
    FROM cohort
    GROUP BY signup_week, is_activated
),
grid AS (
    SELECT s.signup_week, s.is_activated, s.cohort_size, w.week_number
    FROM sizes AS s
    CROSS JOIN (SELECT explode(sequence(0, 12)) AS week_number) AS w
    WHERE date_add(s.signup_week, 7 * w.week_number + 12) <= :window_end
)
SELECT
    g.signup_week,
    g.is_activated,
    g.week_number,
    g.cohort_size,
    COUNT(act.user_id)                              AS retained_users,
    ROUND(COUNT(act.user_id) / g.cohort_size, 4)    AS retention_rate
FROM grid AS g
LEFT JOIN activity AS act
    ON act.signup_week = g.signup_week
   AND act.is_activated = g.is_activated
   AND act.week_number = g.week_number
GROUP BY g.signup_week, g.is_activated, g.week_number, g.cohort_size
ORDER BY g.signup_week, g.is_activated, g.week_number
