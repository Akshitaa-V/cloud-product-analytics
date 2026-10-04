"""Synthetic product-usage data for a B2B cloud platform that hosts 3D scan datasets.

Customer accounts upload laser-scan datasets, the platform processes them, and
users open them in a web or mobile viewer to measure, annotate, share and export.

The generator writes three raw sources, shaped like a typical product event export:

- ``accounts.csv``     one row per customer account (plan, seats, industry, ...)
- ``users.csv``        one row per user (role, main client, creation time)
- ``events/*.jsonl``   one JSON event per line, one file per month

It also injects realistic data problems (duplicates, missing ids, broken
timestamps, unknown event names, ...) and writes a ``manifest.json`` with the
exact number of each problem, so the validation layer can be tested against
known answers. Ground truth for activation is written to ``_ground_truth/``.

Everything is deterministic for a given seed.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

from .config import ACTIVATION_EVENTS, WINDOW_END, WINDOW_START

INDUSTRIES = ["Manufacturing", "Construction", "Architecture", "Facility Management", "Surveying"]
COUNTRIES = ["DE", "US", "GB", "FR", "NL", "CH", "AT", "JP"]
SEAT_RANGE = {"starter": (3, 5), "pro": (6, 20), "enterprise": (25, 80)}
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# Share of rows that receive each problem (relative to the clean event count).
ISSUE_RATES = {
    "missing_user_id": 0.0006,
    "unknown_user": 0.0003,
    "unknown_event_name": 0.0008,
    "unparseable_timestamp": 0.00015,
    "timestamp_out_of_range": 0.00025,
}
EPOCH_RATE = 0.002          # valid timestamps sent as epoch milliseconds
DUPLICATE_RATE = 0.005      # events re-sent by the client
INVALID_SIZE_RATE = 0.02    # share of uploads with a size of zero or below


@dataclass(frozen=True)
class GenConfig:
    start: date = WINDOW_START
    end: date = WINDOW_END
    n_accounts: int = 200
    n_internal_accounts: int = 3
    seed: int = 42
    inject_issues: bool = True
    # A slower processing pipeline release runs between these dates.
    regression_start: date = date(2026, 4, 13)
    regression_end: date = date(2026, 5, 10)


def _ts(dt: datetime) -> str:
    return dt.strftime(TS_FORMAT)


def _pipeline_version(cfg: GenConfig, day: date) -> str:
    if day < cfg.regression_start:
        return "2.7"
    if day <= cfg.regression_end:
        return "2.8"
    return "2.8.1"


def _app_version(client: str, day: date) -> str:
    prefix = {"web": "web", "mobile": "ios", "api": "api"}[client]
    return f"{prefix}-26.{day.month}"


# --------------------------------------------------------------------------- #
# Accounts and users
# --------------------------------------------------------------------------- #
def _make_accounts(cfg: GenConfig, rng: np.random.Generator) -> list[dict]:
    window_days = (cfg.end - cfg.start).days
    accounts = []
    for i in range(cfg.n_accounts):
        internal = i < cfg.n_internal_accounts
        plan = "enterprise" if internal else str(rng.choice(list(SEAT_RANGE), p=[0.5, 0.35, 0.15]))
        lo, hi = SEAT_RANGE[plan]
        seats = 10 if internal else int(rng.integers(lo, hi + 1))
        signup = cfg.start + timedelta(days=int(rng.integers(-200, max(window_days - 14, 1))))
        accounts.append(
            {
                "account_id": f"acc_{i + 1:04d}",
                "account_name": f"Internal Test {i + 1}" if internal else f"Customer {i + 1:03d}",
                "industry": "Internal" if internal else str(rng.choice(INDUSTRIES)),
                "country": "DE" if internal else str(rng.choice(COUNTRIES)),
                "plan": plan,
                "seats": seats,
                "signup_date": signup.isoformat(),
                "is_internal": "true" if internal else "false",
            }
        )
    return accounts


def _make_users(cfg: GenConfig, rng: np.random.Generator, accounts: list[dict]) -> list[dict]:
    users = []
    k = 0
    for acc in accounts:
        signup = date.fromisoformat(acc["signup_date"])
        n_users = max(1, round(acc["seats"] * rng.uniform(0.45, 0.95)))
        for j in range(n_users):
            role = "admin" if j == 0 else ("editor" if rng.random() < 0.35 else "viewer")
            offset_days = 0 if j == 0 else int(rng.exponential(30))
            created_day = signup + timedelta(days=offset_days)
            if created_day > cfg.end:
                continue
            # Office hours, so a user's first actions happen on the same day.
            created_at = datetime.combine(created_day, datetime.min.time()) + timedelta(
                seconds=int(rng.integers(7 * 3600, 18 * 3600))
            )
            mobile_share = 0.35 if role == "viewer" else 0.12
            client = "mobile" if rng.random() < mobile_share else "web"
            k += 1
            users.append(
                {
                    "user_id": f"usr_{k:05d}",
                    "account_id": acc["account_id"],
                    "role": role,
                    "primary_client": client,
                    "created_at": _ts(created_at),
                    # helper fields, not written to users.csv
                    "_created_at": created_at,
                    "_plan": acc["plan"],
                    "_api_user": acc["plan"] == "enterprise" and role != "viewer" and rng.random() < 0.25,
                }
            )
    return users


# --------------------------------------------------------------------------- #
# Event simulation
# --------------------------------------------------------------------------- #
class _EventSink:
    def __init__(self, cfg: GenConfig):
        self.cfg = cfg
        self.events: list[dict] = []
        self.last_ts = datetime.combine(cfg.end, datetime.max.time()).replace(microsecond=0)

    def add(self, user: dict, name: str, ts: datetime, client: str, **props) -> None:
        if ts > self.last_ts:
            return  # happens after the export window
        event = {
            "user_id": user["user_id"],
            "account_id": user["account_id"],
            "event_name": name,
            "event_ts": _ts(ts),
            "client": client,
            "app_version": _app_version(client, ts.date()),
            "_dt": ts,
        }
        props = {k: v for k, v in props.items() if v is not None}
        if props:
            event["properties"] = props
        self.events.append(event)


def _simulate_user(cfg, rng, user, sink, ds_counter) -> tuple[bool, int | None]:
    """Simulate one user's activity. Returns (is_activated, activation_offset)."""
    created_at: datetime = user["_created_at"]
    created_day = created_at.date()
    role, client, plan = user["role"], user["primary_client"], user["_plan"]

    p_activate = 0.58 if client == "web" else 0.33
    p_activate += 0.08 if plan == "enterprise" else 0.0
    p_activate += 0.07 if role != "viewer" else 0.0
    activated = rng.random() < min(p_activate, 0.95)
    act_offset = int(rng.integers(0, 7)) if activated else None

    base = rng.beta(2, 5) * {"admin": 1.3, "editor": 1.15, "viewer": 0.75}[role]
    tau, floor = (110.0, 0.55) if activated else (12.0, 0.08)

    first_day = max(created_day, cfg.start)
    for d in range((cfg.end - first_day).days + 1):
        day = first_day + timedelta(days=d)
        t = (day - created_day).days
        weekend = day.weekday() >= 5
        forced_aha = activated and t == act_offset
        p = base * (floor + (1 - floor) * math.exp(-t / tau))
        if weekend:
            p *= 0.25
        if t == 0:
            p = 0.9
        if not (forced_aha or rng.random() < p):
            continue

        aha_allowed = (activated and t >= act_offset) or t >= 7
        day_start = datetime.combine(day, datetime.min.time())
        if t == 0:
            ts = created_at + timedelta(minutes=int(rng.integers(2, 60)))
        else:
            hour = float(np.clip(rng.normal(11, 2.5), 7, 19))
            ts = day_start + timedelta(seconds=int(hour * 3600))

        n_sessions = 1 + int(rng.poisson(0.4))
        for s in range(n_sessions):
            if s > 0:
                ts += timedelta(minutes=int(rng.integers(45, 180)))
            sink.add(user, "session_start", ts, client)

            def step() -> datetime:
                nonlocal ts
                ts += timedelta(seconds=int(rng.integers(20, 420)))
                return ts

            for _ in range(int(rng.poisson(1.5)) + (1 if rng.random() < 0.8 else 0)):
                sink.add(user, "viewer_open", step(), client)
            m_rate = 0.9 if activated else 0.15
            if aha_allowed:
                n_meas = int(rng.poisson(m_rate))
                if forced_aha and s == 0:
                    n_meas = max(n_meas, 1)
                for _ in range(n_meas):
                    sink.add(user, "measurement_created", step(), client)
                if rng.random() < (0.12 if activated else 0.03):
                    sink.add(user, "share_link_created", step(), client)
            for _ in range(int(rng.poisson(0.3 if activated else 0.08))):
                sink.add(user, "annotation_created", step(), client)
            if rng.random() < (0.05 if plan != "starter" else 0.02):
                sink.add(user, "export_started", step(), client)

            # Upload chain: upload -> processed / failed -> viewed -> shared
            if role != "viewer" and not weekend and rng.random() < 0.12:
                ds_counter[0] += 1
                ds_id = f"ds_{ds_counter[0]:06d}"
                size = round(float(rng.lognormal(1.2, 0.8)), 2)
                up_ts = step()
                sink.add(user, "dataset_upload", up_ts, client, dataset_id=ds_id, size_gb=size)
                regression = cfg.regression_start <= up_ts.date() <= cfg.regression_end
                duration = float(rng.lognormal(math.log(600) + 0.35 * math.log(max(size, 0.1)), 0.35))
                if regression:
                    duration *= 1.7
                fail_p = 0.10 if regression else 0.04
                version = _pipeline_version(cfg, up_ts.date())
                if rng.random() < fail_p:
                    sink.add(user, "dataset_processing_failed", up_ts + timedelta(seconds=int(duration * 0.6)),
                             "web", dataset_id=ds_id, duration_s=round(duration * 0.6, 1),
                             status="failed", pipeline_version=version)
                else:
                    done = up_ts + timedelta(seconds=int(duration))
                    sink.add(user, "dataset_processed", done, "web", dataset_id=ds_id,
                             duration_s=round(duration, 1), status="success", pipeline_version=version)
                    if rng.random() < 0.85:
                        view_ts = done + timedelta(minutes=int(rng.exponential(120)) + 1)
                        sink.add(user, "viewer_open", view_ts, client, dataset_id=ds_id)
                        if aha_allowed and rng.random() < (0.45 if activated else 0.25):
                            sink.add(user, "share_link_created",
                                     view_ts + timedelta(minutes=int(rng.integers(2, 30))),
                                     client, dataset_id=ds_id)

            if user["_api_user"] and not weekend:
                for _ in range(int(rng.poisson(6))):
                    sink.add(user, "api_call", step(), "api")

    return activated, act_offset


# --------------------------------------------------------------------------- #
# Data problems
# --------------------------------------------------------------------------- #
def _inject_issues(cfg, rng, events: list[dict]) -> tuple[list[dict], dict]:
    n = len(events)
    counts = {k: max(1, round(rate * n)) for k, rate in ISSUE_RATES.items()}
    n_epoch = max(1, round(EPOCH_RATE * n))
    n_dup = max(1, round(DUPLICATE_RATE * n))

    upload_idx = np.array([i for i, e in enumerate(events) if e["event_name"] == "dataset_upload"])
    n_size = max(1, round(INVALID_SIZE_RATE * len(upload_idx))) if len(upload_idx) else 0
    size_idx = rng.choice(upload_idx, n_size, replace=False) if n_size else np.array([], dtype=int)

    pool = np.setdiff1d(np.arange(n), size_idx)
    needed = sum(counts.values()) + n_epoch + n_dup
    chosen = rng.choice(pool, needed, replace=False)

    groups, pos = {}, 0
    for name, c in list(counts.items()) + [("epoch", n_epoch), ("duplicate", n_dup)]:
        groups[name] = chosen[pos:pos + c]
        pos += c

    for i in size_idx:
        events[i]["properties"]["size_gb"] = float(rng.choice([0.0, -1.0, -0.5]))
    for k, i in enumerate(groups["missing_user_id"]):
        events[i]["user_id"] = None
    for k, i in enumerate(groups["unknown_user"]):
        events[i]["user_id"] = f"usr_ghost_{k:03d}"
    for i in groups["unknown_event_name"]:
        events[i]["event_name"] = str(rng.choice(["viewr_open", "debug_ping", "test_event"]))
    for i in groups["unparseable_timestamp"]:
        events[i]["event_ts"] = str(rng.choice(["2026/03/04 10:00", "unknown", ""]))
    for i in groups["timestamp_out_of_range"]:
        events[i]["event_ts"] = "2027" + events[i]["event_ts"][4:]
    for i in groups["epoch"]:
        events[i]["event_ts"] = str(int((events[i]["_dt"] - datetime(1970, 1, 1)).total_seconds() * 1000))

    duplicates = [copy.deepcopy(events[i]) for i in groups["duplicate"]]

    issues = {k: int(len(v)) for k, v in groups.items() if k not in ("epoch", "duplicate")}
    issues["invalid_dataset_size"] = int(n_size)
    manifest = {
        "issues": issues,
        "epoch_timestamps": int(n_epoch),
        "duplicate_rows": int(n_dup),
    }
    return events + duplicates, manifest


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #
def generate(out_dir: str | Path, cfg: GenConfig = GenConfig()) -> dict:
    """Generate all raw files into ``out_dir`` and return the manifest."""
    out = Path(out_dir)
    (out / "events").mkdir(parents=True, exist_ok=True)
    (out / "_ground_truth").mkdir(parents=True, exist_ok=True)
    for old in (out / "events").glob("*.jsonl"):
        old.unlink()

    rng = np.random.default_rng(cfg.seed)
    accounts = _make_accounts(cfg, rng)
    users = _make_users(cfg, rng, accounts)

    sink = _EventSink(cfg)
    ds_counter = [0]
    truth = []
    for user in users:
        activated, _ = _simulate_user(cfg, rng, user, sink, ds_counter)
        created_day = user["_created_at"].date()
        if cfg.start <= created_day <= cfg.end:
            truth.append({"user_id": user["user_id"], "created_date": created_day.isoformat(),
                          "is_activated": "true" if activated else "false"})

    events = sorted(sink.events, key=lambda e: (e["_dt"], e["user_id"], e["event_name"]))
    for i, e in enumerate(events, start=1):
        e["event_id"] = f"evt_{i:08d}"
        e["_month"] = e["_dt"].strftime("%Y-%m")
    n_clean = len(events)

    internal_ids = {a["account_id"] for a in accounts if a["is_internal"] == "true"}
    if cfg.inject_issues:
        events, manifest = _inject_issues(cfg, rng, events)
    else:
        manifest = {"issues": {}, "epoch_timestamps": 0, "duplicate_rows": 0}

    # Valid events from internal test accounts: they stay valid but are excluded from KPIs.
    manifest["internal_account_events"] = sum(
        1 for e in events[:n_clean]
        if e["account_id"] in internal_ids and _is_clean(e, cfg)
    )

    # Write events, one file per month (re-sent duplicates land in the same file).
    by_month: dict[str, list[dict]] = {}
    for e in events:
        by_month.setdefault(e["_month"], []).append(e)
    field_order = ["event_id", "user_id", "account_id", "event_name", "event_ts", "client", "app_version", "properties"]
    for month, rows in sorted(by_month.items()):
        with open(out / "events" / f"events_{month}.jsonl", "w", encoding="utf-8") as fh:
            for e in rows:
                fh.write(json.dumps({k: e[k] for k in field_order if k in e}) + "\n")

    with open(out / "accounts.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(accounts[0]))
        w.writeheader()
        w.writerows(accounts)
    user_fields = ["user_id", "account_id", "role", "primary_client", "created_at"]
    with open(out / "users.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=user_fields)
        w.writeheader()
        w.writerows({k: u[k] for k in user_fields} for u in users)
    with open(out / "_ground_truth" / "activation.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["user_id", "created_date", "is_activated"])
        w.writeheader()
        w.writerows(truth)

    manifest.update(
        {
            "config": {k: (v.isoformat() if isinstance(v, date) else v) for k, v in asdict(cfg).items()},
            "accounts": len(accounts),
            "users": len(users),
            "clean_events": n_clean,
            "raw_event_rows": len(events),
            "datasets_uploaded": ds_counter[0],
        }
    )
    with open(out / "manifest.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    return manifest


def _is_clean(e: dict, cfg: GenConfig) -> bool:
    """True when the row passes every validation rule (epoch timestamps are fine)."""
    from .config import VALID_EVENT_NAMES

    if e["user_id"] is None or e["user_id"].startswith("usr_ghost_"):
        return False
    if e["event_name"] not in VALID_EVENT_NAMES:
        return False
    ts = e["event_ts"]
    if not ts.isdigit():
        if len(ts) != 20 or not ts.startswith("20") or ts[4] != "-":
            return False
        if not (cfg.start.isoformat() <= ts[:10] <= cfg.end.isoformat()):
            return False
    if e["event_name"] == "dataset_upload" and e.get("properties", {}).get("size_gb", 1) <= 0:
        return False
    return True


def main() -> None:
    p = argparse.ArgumentParser(description="Generate synthetic raw product data.")
    p.add_argument("--out", default="data/raw")
    p.add_argument("--accounts", type=int, default=GenConfig.n_accounts)
    p.add_argument("--seed", type=int, default=GenConfig.seed)
    p.add_argument("--clean", action="store_true", help="do not inject data problems")
    a = p.parse_args()
    m = generate(a.out, GenConfig(n_accounts=a.accounts, seed=a.seed, inject_issues=not a.clean))
    print(json.dumps({k: m[k] for k in ("accounts", "users", "clean_events", "raw_event_rows")}, indent=2))


if __name__ == "__main__":
    main()
