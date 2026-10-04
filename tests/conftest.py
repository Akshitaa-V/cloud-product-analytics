from __future__ import annotations

import json
from pathlib import Path

import pytest

from product_analytics.config import PipelineConfig
from product_analytics.generate import GenConfig, generate
from product_analytics.pipeline import run_all
from product_analytics.spark_utils import get_spark


@pytest.fixture(scope="session")
def spark():
    return get_spark("product-analytics-tests")


def _run(tmp: Path, spark, inject_issues: bool):
    raw = tmp / "raw"
    manifest = generate(raw, GenConfig(n_accounts=30, seed=7, inject_issues=inject_issues))
    cfg = PipelineConfig(raw_path=str(raw), lake_path=str(tmp / "lake"),
                         powerbi_path=str(tmp / "powerbi"), reports_path=str(tmp / "reports"))
    store = run_all(spark, cfg)
    return {"manifest": manifest, "store": store, "cfg": cfg, "raw": raw}


@pytest.fixture(scope="session")
def run(tmp_path_factory, spark):
    """Full pipeline on a small dataset with injected data problems."""
    return _run(tmp_path_factory.mktemp("with_issues"), spark, inject_issues=True)


@pytest.fixture(scope="session")
def clean_run(tmp_path_factory, spark):
    """Full pipeline on a small dataset without data problems (for ground-truth checks)."""
    return _run(tmp_path_factory.mktemp("clean"), spark, inject_issues=False)


def read_manifest(raw: Path) -> dict:
    return json.loads((raw / "manifest.json").read_text())
