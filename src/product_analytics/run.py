"""Command line entry point for local runs.

    python -m product_analytics.run                 # generate data (first run), run all layers, export, report
    python -m product_analytics.run --regenerate    # create fresh raw data first
    python -m product_analytics.run --skip-export   # no Power BI CSV export
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from .config import PipelineConfig
from .export_powerbi import export_for_powerbi
from .generate import GenConfig, generate
from .insights import write_insights
from .pipeline import _log, run_all
from .spark_utils import get_spark


def main() -> None:
    p = argparse.ArgumentParser(description="Run the product analytics pipeline locally.")
    p.add_argument("--regenerate", action="store_true", help="create new raw data even if it exists")
    p.add_argument("--accounts", type=int, default=GenConfig.n_accounts)
    p.add_argument("--seed", type=int, default=GenConfig.seed)
    p.add_argument("--skip-export", action="store_true")
    p.add_argument("--skip-insights", action="store_true")
    a = p.parse_args()

    started = time.time()
    cfg = PipelineConfig()
    if a.regenerate or not (Path(cfg.raw_path) / "manifest.json").exists():
        m = generate(cfg.raw_path, GenConfig(n_accounts=a.accounts, seed=a.seed))
        _log(f"raw: {m['accounts']} accounts, {m['users']} users, {m['raw_event_rows']} event rows")

    spark = get_spark()
    store = run_all(spark, cfg)
    if not a.skip_export:
        files = export_for_powerbi(store, cfg)
        _log(f"power bi: {len(files)} CSV files in {cfg.powerbi_path}")
    if not a.skip_insights:
        report = write_insights(store, cfg)
        _log(f"report: {report}")
    _log(f"done in {time.time() - started:.0f} s")


if __name__ == "__main__":
    main()
