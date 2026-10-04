"""The KPI library, the SQL files, the gold tables and the Power BI measures stay in sync."""
import re
from pathlib import Path

from product_analytics.config import REPO_ROOT
from product_analytics.kpi_library import load_library, render_markdown

LIB = load_library()


def test_every_kpi_has_a_sql_file():
    for k in LIB["kpis"]:
        assert (Path(REPO_ROOT) / k["sql"]).is_file(), k["sql"]


def test_documented_columns_match_the_gold_tables(run):
    for k in LIB["kpis"]:
        assert run["store"].read("gold", k["table"]).columns == k["columns"], k["id"]


def test_power_bi_measures_exist_in_dax_file():
    dax = (Path(REPO_ROOT) / "powerbi" / "measures.dax").read_text()
    defined = set(re.findall(r"MEASURE\s+\w+\[([^\]]+)\]", dax))
    for k in LIB["kpis"]:
        missing = set(k["power_bi_measures"]) - defined
        assert not missing, f"{k['id']}: {missing}"


def test_rendered_docs_are_up_to_date():
    docs = (Path(REPO_ROOT) / "docs" / "kpi_library.md").read_text()
    assert docs == render_markdown(LIB), "run: python -m product_analytics.kpi_library"
