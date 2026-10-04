"""Load, check and document the KPI library (``kpis/kpi_library.yml``).

Run ``python -m product_analytics.kpi_library`` to regenerate ``docs/kpi_library.md``.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .config import REPO_ROOT

REQUIRED_FIELDS = (
    "id", "name", "question", "owner", "grain", "table", "sql",
    "definition", "formula", "columns", "caveats", "power_bi_measures",
)


def load_library(path: str | Path = REPO_ROOT / "kpis" / "kpi_library.yml") -> dict:
    with open(path, encoding="utf-8") as fh:
        lib = yaml.safe_load(fh)
    problems = []
    ids = set()
    for kpi in lib.get("kpis", []):
        missing = [f for f in REQUIRED_FIELDS if f not in kpi]
        if missing:
            problems.append(f"{kpi.get('id', '?')}: missing {missing}")
        if kpi.get("id") in ids:
            problems.append(f"duplicate id {kpi['id']}")
        ids.add(kpi.get("id"))
    if problems:
        raise ValueError("KPI library is invalid: " + "; ".join(problems))
    return lib


def render_markdown(lib: dict) -> str:
    lines = [
        "# KPI library",
        "",
        "Generated from `kpis/kpi_library.yml` by `python -m product_analytics.kpi_library`. "
        "Edit the YAML file, not this page.",
        "",
        "| KPI | Question it answers | Owner | Grain | Table |",
        "|---|---|---|---|---|",
    ]
    for k in lib["kpis"]:
        lines.append(f"| [{k['name']}](#{k['id'].replace('_', '-')}) | {k['question']} | {k['owner']} | {k['grain']} | `{k['table']}` |")
    for k in lib["kpis"]:
        lines += [
            "",
            f"## {k['id'].replace('_', '-')}",
            "",
            f"**{k['name']}**",
            "",
            f"- **Question:** {k['question']}",
            f"- **Definition:** {k['definition'].strip()}",
            f"- **Formula:** `{k['formula']}`",
            f"- **Grain:** {k['grain']}",
            f"- **Owner:** {k['owner']}",
            f"- **SQL:** [`{k['sql']}`](../{k['sql']})",
            f"- **Output columns:** {', '.join(f'`{c}`' for c in k['columns'])}",
            f"- **Power BI measures:** {', '.join(k['power_bi_measures'])}",
            f"- **Caveats:** {k['caveats'].strip()}",
        ]
    return "\n".join(lines) + "\n"


def main() -> None:
    lib = load_library()
    target = REPO_ROOT / "docs" / "kpi_library.md"
    target.parent.mkdir(exist_ok=True)
    target.write_text(render_markdown(lib), encoding="utf-8")
    print(f"wrote {target.relative_to(REPO_ROOT)} ({len(lib['kpis'])} KPIs)")


if __name__ == "__main__":
    main()
