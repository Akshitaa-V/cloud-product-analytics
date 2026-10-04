"""Run the layers in order: bronze -> silver -> gold (star schema + KPIs)."""
from __future__ import annotations

import time

from pyspark.sql import SparkSession

from . import bronze, gold, silver
from .config import PipelineConfig
from .spark_utils import TableStore

STAR_TABLES = ("dim_date", "dim_account", "dim_user", "fact_events", "fact_user_daily")


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run_bronze(spark: SparkSession, cfg: PipelineConfig, store: TableStore) -> None:
    for name, df in bronze.load_bronze(spark, cfg.raw_path).items():
        store.write(df, "bronze", name)
    _log("bronze: events, accounts, users loaded")


def run_silver(spark: SparkSession, cfg: PipelineConfig, store: TableStore) -> None:
    b_events = store.read("bronze", "events")
    users = store.write(silver.build_users(store.read("bronze", "users")), "silver", "users")
    accounts = store.write(silver.build_accounts(store.read("bronze", "accounts")), "silver", "accounts")
    valid, quarantine = silver.build_events(b_events, users, accounts, cfg.window_start, cfg.window_end)
    valid = store.write(valid, "silver", "events")
    quarantine = store.write(quarantine, "silver", "quarantine")
    dq = store.write(silver.build_dq_summary(spark, b_events, valid, quarantine), "silver", "dq_summary")
    _log("silver: data quality checks")
    for row in dq.collect():
        print(f"           {row['check']:<28} {row['action']:<20} {row['rows']:>8}")


def run_gold(spark: SparkSession, cfg: PipelineConfig, store: TableStore) -> None:
    silver_tables = {name: store.read("silver", name) for name in ("events", "users", "accounts")}
    star = gold.build_star_schema(spark, silver_tables, cfg.window_start, cfg.window_end)
    # Write the star schema first and read it back, so KPIs run on stored tables.
    star = {name: store.write(df, "gold", name) for name, df in star.items()}
    _log("gold: star schema written (" + ", ".join(STAR_TABLES) + ")")
    kpis = gold.build_kpis(spark, star, cfg.window_start, cfg.window_end, cfg.kpi_library_path, cfg.sql_root)
    for name, df in kpis.items():
        store.write(df, "gold", name)
    _log(f"gold: {len(kpis)} KPI tables written (" + ", ".join(kpis) + ")")


def run_all(spark: SparkSession, cfg: PipelineConfig) -> TableStore:
    store = TableStore(spark, cfg)
    run_bronze(spark, cfg, store)
    run_silver(spark, cfg, store)
    run_gold(spark, cfg, store)
    return store
