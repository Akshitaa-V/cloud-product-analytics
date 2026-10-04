"""Export the gold tables as CSV files for Power BI Desktop (local runs).

On Databricks you do not need this: Power BI connects to the Delta tables directly.
Timestamps are written as ``yyyy-MM-dd HH:mm:ss`` (UTC) so Power BI reads them
as Date/Time without time-zone conversion.
"""
from __future__ import annotations

from pathlib import Path

from pyspark.sql import functions as F
from pyspark.sql.types import TimestampType

from .config import PipelineConfig
from .kpi_library import load_library
from .pipeline import STAR_TABLES
from .spark_utils import TableStore


def export_for_powerbi(store: TableStore, cfg: PipelineConfig) -> list[Path]:
    out = Path(cfg.powerbi_path)
    out.mkdir(parents=True, exist_ok=True)
    tables = list(STAR_TABLES) + [k["table"] for k in load_library(cfg.kpi_library_path)["kpis"]]
    written = []
    for name in tables:
        df = store.read("gold", name)
        for field in df.schema.fields:
            if isinstance(field.dataType, TimestampType):
                df = df.withColumn(field.name, F.date_format(field.name, "yyyy-MM-dd HH:mm:ss"))
        path = out / f"{name}.csv"
        df.toPandas().to_csv(path, index=False)
        written.append(path)
    return written
