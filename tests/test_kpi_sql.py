"""KPI SQL checked against small hand-made tables with known answers."""
from datetime import date, datetime
from pathlib import Path

import pytest

from product_analytics.config import REPO_ROOT
from product_analytics.gold import build_dim_date, run_kpi_sql

START, END = date(2026, 1, 1), date(2026, 3, 31)
PARAMS = {"window_start": START, "window_end": END}


def sql(name: str) -> str:
    return (Path(REPO_ROOT) / "sql" / "gold" / f"{name}.sql").read_text()


@pytest.fixture()
def dim_date(spark):
    df = build_dim_date(spark, START, END)
    df.createOrReplaceTempView("dim_date")
    return df


def _user_daily(spark, rows):
    df = spark.createDataFrame(
        [(u, "acc_1", d, 1, 1, 0, 0, 0) for u, d in rows],
        "user_id string, account_id string, activity_date date, events long, sessions long, "
        "viewer_opens long, measurements long, uploads long",
    )
    df.createOrReplaceTempView("fact_user_daily")
    return df


def test_active_users_rolling_windows(spark, dim_date):
    _user_daily(spark, [
        ("a", date(2026, 2, 1)), ("a", date(2026, 2, 10)),
        ("b", date(2026, 2, 5)),
        ("c", date(2026, 2, 10)),
    ])
    out = {r["date"]: r for r in run_kpi_sql(spark, sql("kpi_active_users"), PARAMS).collect()}
    day = out[date(2026, 2, 10)]
    assert (day["dau"], day["wau"], day["mau"]) == (2, 3, 3)
    assert day["stickiness"] == pytest.approx(round(2 / 3, 4))
    later = out[date(2026, 3, 9)]  # 2026-02-10 is now 27 days back: still inside MAU
    assert (later["dau"], later["wau"], later["mau"]) == (0, 0, 2)
    assert out[date(2026, 3, 10)]["mau"] == 0


def test_retention_weeks(spark, dim_date):
    # Two users created on Monday 2026-01-05; one returns in week 1 and week 3.
    spark.createDataFrame(
        [("u1", date(2026, 1, 5), date(2026, 1, 5), True, True),
         ("u2", date(2026, 1, 5), date(2026, 1, 5), True, True)],
        "user_id string, created_date date, signup_week date, is_new_in_window boolean, is_activated boolean",
    ).createOrReplaceTempView("dim_user")
    _user_daily(spark, [
        ("u1", date(2026, 1, 5)), ("u2", date(2026, 1, 5)),
        ("u1", date(2026, 1, 12)), ("u1", date(2026, 1, 13)),   # week 1, counted once
        ("u1", date(2026, 1, 26)),                               # week 3
    ])
    rows = run_kpi_sql(spark, sql("kpi_retention_weekly"), PARAMS).collect()
    rates = {r["week_number"]: r["retention_rate"] for r in rows}
    assert rates[0] == 1.0 and rates[1] == 0.5 and rates[2] == 0.0 and rates[3] == 0.5
    assert {r["cohort_size"] for r in rows} == {2}


def test_upload_funnel_counts_datasets_not_events(spark):
    ts = lambda h: datetime(2026, 2, 3, h)  # noqa: E731
    spark.createDataFrame(
        [
            ("ds1", "dataset_upload", ts(9)), ("ds1", "dataset_processed", ts(10)),
            ("ds1", "viewer_open", ts(11)), ("ds1", "viewer_open", ts(12)),
            ("ds1", "share_link_created", ts(13)),
            ("ds2", "dataset_upload", ts(9)), ("ds2", "dataset_processing_failed", ts(10)),
            ("ds3", "dataset_upload", ts(9)), ("ds3", "dataset_processed", ts(10)),
        ],
        "dataset_id string, event_name string, event_ts timestamp",
    ).createOrReplaceTempView("fact_events")
    r = run_kpi_sql(spark, sql("kpi_upload_funnel"), PARAMS).collect()[0]
    assert (r["uploaded"], r["processed"], r["viewed"], r["shared"]) == (3, 2, 1, 1)
    assert r["upload_to_share_rate"] == pytest.approx(round(1 / 3, 4))


def test_account_health_status_thresholds(spark, dim_date):
    spark.createDataFrame(
        [("acc_1", 10, date(2025, 6, 1)), ("acc_2", 10, date(2025, 6, 1)), ("acc_3", 10, date(2026, 3, 15))],
        "account_id string, seats int, signup_date date",
    ).selectExpr("*", "'pro' AS plan", "'Construction' AS industry").createOrReplaceTempView("dim_account")
    _user_daily(spark, [(f"u{i}", date(2026, 1, 10)) for i in range(7)])  # 7 of 10 seats for acc_1
    out = run_kpi_sql(spark, sql("kpi_account_health"), PARAMS)
    jan = {r["account_id"]: r for r in out.where("month = DATE'2026-01-01'").collect()}
    assert jan["acc_1"]["health_status"] == "healthy" and jan["acc_1"]["seat_utilization"] == 0.7
    assert jan["acc_2"]["health_status"] == "at_risk"
    assert "acc_3" not in jan  # signed up in March
