"""Shared settings for the pipeline.

The same code runs in two places:
- ``local``: PySpark on a laptop or in CI, tables stored as Parquet files.
- ``databricks``: Databricks (for example the Free Edition), tables stored as
  Delta tables in Unity Catalog, raw files in a Unity Catalog volume.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

WINDOW_START = date(2026, 1, 1)
WINDOW_END = date(2026, 6, 30)

# Events the product is allowed to send. Anything else is quarantined.
VALID_EVENT_NAMES = (
    "session_start",
    "viewer_open",
    "measurement_created",
    "annotation_created",
    "share_link_created",
    "export_started",
    "dataset_upload",
    "dataset_processed",
    "dataset_processing_failed",
    "api_call",
)

# Events that count as the first moment of value ("aha moment") for activation.
ACTIVATION_EVENTS = ("measurement_created", "share_link_created")

# Product feature each event belongs to (events without a feature are plumbing).
FEATURE_BY_EVENT = {
    "viewer_open": "Viewer",
    "measurement_created": "Measurements",
    "annotation_created": "Annotations",
    "share_link_created": "Sharing",
    "export_started": "Export",
    "dataset_upload": "Upload",
    "api_call": "API",
}


@dataclass
class PipelineConfig:
    mode: str = "local"  # "local" or "databricks"
    raw_path: str = str(REPO_ROOT / "data" / "raw")
    lake_path: str = str(REPO_ROOT / "data" / "lake")
    powerbi_path: str = str(REPO_ROOT / "data" / "powerbi")
    reports_path: str = str(REPO_ROOT / "reports")
    catalog: str = "workspace"
    schema: str = "product_analytics"
    window_start: date = WINDOW_START
    window_end: date = WINDOW_END
    kpi_library_path: str = str(REPO_ROOT / "kpis" / "kpi_library.yml")
    sql_root: str = str(REPO_ROOT)
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.mode not in ("local", "databricks"):
            raise ValueError(f"mode must be 'local' or 'databricks', got {self.mode!r}")
