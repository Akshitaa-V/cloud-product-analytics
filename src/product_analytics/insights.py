"""Turn the KPI tables into a short insights report with charts.

Every number in ``reports/insights.md`` is computed from the gold tables when
the pipeline runs; nothing is typed in by hand.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from .config import PipelineConfig  # noqa: E402
from .spark_utils import TableStore  # noqa: E402

INK, MUTED, ACCENT, ACCENT2, ALERT = "#1f2933", "#7b8794", "#2563eb", "#0d9488", "#dc2626"


def _pct(x: float) -> str:
    return f"{x * 100:.1f} %"


def _style(ax, title: str) -> None:
    ax.set_title(title, loc="left", fontsize=11, color=INK, pad=10)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(MUTED)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(axis="y", color="#e4e7eb", linewidth=0.8)
    ax.set_axisbelow(True)


def compute_insights(t: dict[str, pd.DataFrame]) -> dict:
    res: dict = {}

    # Engagement
    au = t["kpi_active_users"].sort_values("date")
    full = au[au["is_full_window"]]
    last28 = au.tail(28)
    res["mau_start"] = int(full["mau"].iloc[0])
    res["mau_start_date"] = str(full["date"].iloc[0])
    res["mau_end"] = int(au["mau"].iloc[-1])
    res["mau_growth"] = res["mau_end"] / res["mau_start"] - 1
    res["stickiness_28d"] = float(last28["dau"].mean() / au["mau"].iloc[-1])

    # Activation by client
    act = t["kpi_activation"]
    by_client = act.groupby("primary_client")[["new_users", "activated_users"]].sum()
    by_client["rate"] = by_client["activated_users"] / by_client["new_users"]
    res["activation_overall"] = float(act["activated_users"].sum() / act["new_users"].sum())
    res["activation_by_client"] = by_client["rate"].to_dict()
    res["new_users"] = int(act["new_users"].sum())

    # Retention in week 4, activated vs not
    ret = t["kpi_retention_weekly"]
    w4 = ret[ret["week_number"] == 4].groupby("is_activated")[["retained_users", "cohort_size"]].sum()
    res["w4_retention"] = (w4["retained_users"] / w4["cohort_size"]).to_dict()

    # Processing time: weeks well above the usual median
    pt = t["kpi_processing_time"].sort_values("week_start")
    pt = pt[(pt["processed_jobs"] + pt["failed_jobs"]) >= 10]
    baseline = float(pt["median_processing_min"].median())
    slow = pt[pt["median_processing_min"] > 1.3 * baseline]
    rest = pt[~pt.index.isin(slow.index)]
    res["proc_baseline_min"] = baseline
    if len(slow):
        res["slow_weeks"] = {
            "first": str(slow["week_start"].min()),
            "last": str(slow["week_start"].max()),
            "count": int(len(slow)),
            "versions": sorted(slow["pipeline_version"].unique().tolist()),
            "median_min": float(slow["median_processing_min"].median()),
            "failure_rate": float(slow["failed_jobs"].sum() / (slow["processed_jobs"] + slow["failed_jobs"]).sum()),
            "other_failure_rate": float(rest["failed_jobs"].sum() / (rest["processed_jobs"] + rest["failed_jobs"]).sum()),
        }

    # Funnel
    fn = t["kpi_upload_funnel"]
    res["funnel"] = {k: int(fn[k].sum()) for k in ("uploaded", "processed", "viewed", "shared")}

    # Feature adoption in the last month
    fa = t["kpi_feature_adoption"]
    last_month = fa["month"].max()
    fa_last = fa[fa["month"] == last_month].sort_values("adoption_rate", ascending=False)
    res["adoption_month"] = str(last_month)[:7]
    res["adoption"] = list(zip(fa_last["feature"], fa_last["adoption_rate"]))

    # Account health in the last month
    ah = t["kpi_account_health"]
    ah_last = ah[ah["month"] == ah["month"].max()]
    res["accounts_last_month"] = int(len(ah_last))
    res["at_risk"] = int((ah_last["health_status"] == "at_risk").sum())
    res["at_risk_by_plan"] = (
        ah_last.assign(r=ah_last["health_status"] == "at_risk").groupby("plan")["r"].mean().to_dict()
    )

    # Data quality
    dq = t["dq_summary"].set_index("check")["rows"]
    res["dq_raw"] = int(dq["raw_rows"])
    res["dq_duplicates"] = int(dq["duplicate_event_id"])
    res["dq_quarantined"] = int(t["dq_summary"].query("action == 'quarantined'")["rows"].sum())
    return res


def make_charts(t: dict[str, pd.DataFrame], out_dir: Path) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []

    au = t["kpi_active_users"].sort_values("date").copy()
    au["date"] = pd.to_datetime(au["date"])
    au["dau_7d"] = au["dau"].rolling(7).mean()
    au = au[au["is_full_window"]]  # skip the first 27 days without a full 28-day history
    fig, ax = plt.subplots(figsize=(8, 3.4))
    ax.plot(au["date"], au["mau"], color=ACCENT, linewidth=2, label="MAU (rolling 28 days)")
    ax.plot(au["date"], au["wau"], color=ACCENT2, linewidth=1.5, label="WAU (rolling 7 days)")
    ax.plot(au["date"], au["dau_7d"], color=MUTED, linewidth=1.5, label="DAU (7-day average)")
    _style(ax, "Active users")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(out_dir / "active_users.png", dpi=150)
    plt.close(fig)
    files.append("active_users.png")

    ret = t["kpi_retention_weekly"]
    curve = ret.groupby(["is_activated", "week_number"])[["retained_users", "cohort_size"]].sum()
    curve["rate"] = curve["retained_users"] / curve["cohort_size"]
    fig, ax = plt.subplots(figsize=(8, 3.4))
    for flag, color, label in ((True, ACCENT, "Activated in week 1"), (False, ALERT, "Not activated")):
        c = curve.loc[flag]
        ax.plot(c.index, c["rate"] * 100, marker="o", markersize=3, color=color, linewidth=2, label=label)
    _style(ax, "Weekly retention by activation (% of cohort active)")
    ax.set_xlabel("Weeks since signup", color=MUTED, fontsize=8)
    ax.set_ylim(0, 105)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "retention_by_activation.png", dpi=150)
    plt.close(fig)
    files.append("retention_by_activation.png")

    pt = t["kpi_processing_time"].sort_values("week_start").copy()
    pt["week_start"] = pd.to_datetime(pt["week_start"])
    fig, ax = plt.subplots(figsize=(8, 3.4))
    ax.plot(pt["week_start"], pt["median_processing_min"], color=ACCENT, linewidth=2, label="Median (min)")
    ax.plot(pt["week_start"], pt["p90_processing_min"], color=MUTED, linewidth=1.5, label="90th percentile (min)")
    _style(ax, "Dataset processing time per week")
    ax2 = ax.twinx()
    ax2.bar(pt["week_start"], pt["failure_rate"] * 100, width=5, color=ALERT, alpha=0.25, label="Failure rate (%)")
    ax2.set_ylim(0, 40)
    ax.set_ylabel("Minutes", color=MUTED, fontsize=8)
    ax2.set_ylabel("Failure rate (%)", color=MUTED, fontsize=8)
    ax2.tick_params(colors=MUTED, labelsize=8)
    ax2.spines["top"].set_visible(False)
    lines = ax.get_legend_handles_labels()
    bars = ax2.get_legend_handles_labels()
    ax.legend(lines[0] + bars[0], lines[1] + bars[1], frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(out_dir / "processing_time.png", dpi=150)
    plt.close(fig)
    files.append("processing_time.png")
    return files


def render_report(r: dict) -> str:
    web = r["activation_by_client"].get("web", 0.0)
    mobile = r["activation_by_client"].get("mobile", 0.0)
    w4_yes = r["w4_retention"].get(True, 0.0)
    w4_no = r["w4_retention"].get(False, 0.0)
    f = r["funnel"]
    top = r["adoption"][:2]
    low = r["adoption"][-2:]

    lines = [
        "# Product insights",
        "",
        "Generated by `python -m product_analytics.run` from the KPI tables in the gold layer. "
        "The data is synthetic, so the findings describe the simulated platform, not a real company.",
        "",
        "## Summary",
        "",
        f"1. **Activation drives retention.** Users who reach a first measurement or share link in their "
        f"first week are still active in week 4 at {_pct(w4_yes)}, against {_pct(w4_no)} for everyone else.",
        f"2. **Mobile sign-ups activate less often.** {_pct(web)} of new web users activate, but only "
        f"{_pct(mobile)} of new mobile users ({r['new_users']} new users in total).",
    ]
    if "slow_weeks" in r:
        s = r["slow_weeks"]
        lines.append(
            f"3. **A processing release slowed the pipeline.** From the week of {s['first']} to the week of "
            f"{s['last']} ({s['count']} weeks, pipeline version {', '.join(s['versions'])}), median processing "
            f"time was {s['median_min']:.1f} min against a usual {r['proc_baseline_min']:.1f} min, and "
            f"{_pct(s['failure_rate'])} of jobs failed against {_pct(s['other_failure_rate'])} in other weeks."
        )
    lines += [
        f"4. **Seat utilisation flags churn risk early.** In the last month, {r['at_risk']} of "
        f"{r['accounts_last_month']} customer accounts used fewer than 30 % of their seats.",
        "",
        "## Engagement",
        "",
        f"MAU grew from {r['mau_start']} ({r['mau_start_date']}, first day with a full 28-day window) to "
        f"{r['mau_end']} at the end of the period (+{_pct(r['mau_growth'])}). Stickiness over the last 28 days "
        f"(average DAU / MAU) is {_pct(r['stickiness_28d'])}.",
        "",
        "![Active users](charts/active_users.png)",
        "",
        "## Activation and retention",
        "",
        f"Overall activation rate: {_pct(r['activation_overall'])}. Retention curves split by activation:",
        "",
        "![Retention by activation](charts/retention_by_activation.png)",
        "",
        "## Upload pipeline",
        "",
        f"Across the period, {f['uploaded']} datasets were uploaded, {f['processed']} processed successfully, "
        f"{f['viewed']} opened after processing and {f['shared']} shared "
        f"({_pct(f['shared'] / f['uploaded'])} from upload to share).",
        "",
        "![Processing time](charts/processing_time.png)",
        "",
        "## Feature adoption",
        "",
        f"In {r['adoption_month']}, the most adopted features were "
        + " and ".join(f"{n} ({_pct(v)} of active accounts)" for n, v in top)
        + "; the least adopted were "
        + " and ".join(f"{n} ({_pct(v)})" for n, v in low)
        + ".",
        "",
        "## Account health",
        "",
        "Share of accounts at risk in the last month, by plan: "
        + ", ".join(f"{p} {_pct(v)}" for p, v in sorted(r["at_risk_by_plan"].items()))
        + ".",
        "",
        "## Suggested next steps",
        "",
        "- Product: test a guided first measurement in the mobile app, since mobile sign-ups activate less "
        "often and activation is linked to retention.",
        "- Cloud Engineering: add the weekly processing-time KPI to release checks so a slower pipeline "
        "version is caught in its first week.",
        "- Customer Success: review accounts marked at_risk each month before their renewal date.",
        "",
        "## Data quality",
        "",
        f"Of {r['dq_raw']} raw event rows, {r['dq_duplicates']} duplicates were removed and "
        f"{r['dq_quarantined']} rows were quarantined with a reason (see `silver/dq_summary`). "
        "No row is dropped without a record.",
        "",
    ]
    return "\n".join(lines)


def write_insights(store: TableStore, cfg: PipelineConfig) -> Path:
    names = [
        "kpi_active_users", "kpi_activation", "kpi_retention_weekly", "kpi_feature_adoption",
        "kpi_upload_funnel", "kpi_processing_time", "kpi_account_health",
    ]
    tables = {n: store.read("gold", n).toPandas() for n in names}
    tables["dq_summary"] = store.read("silver", "dq_summary").toPandas()
    out = Path(cfg.reports_path)
    make_charts(tables, out / "charts")
    report = out / "insights.md"
    report.write_text(render_report(compute_insights(tables)), encoding="utf-8")
    return report
