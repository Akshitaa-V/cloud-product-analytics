"""Referential integrity and activation ground truth for the gold star schema."""
import csv

import pyspark.sql.functions as F


def _orphans(child, parent, child_key, parent_key=None):
    parent_key = parent_key or child_key
    return child.join(parent.select(F.col(parent_key).alias("_k")), F.col(child_key) == F.col("_k"), "left_anti")


def test_facts_reference_existing_dimensions(run):
    s = run["store"]
    fe, fud = s.read("gold", "fact_events"), s.read("gold", "fact_user_daily")
    du, da, dd = s.read("gold", "dim_user"), s.read("gold", "dim_account"), s.read("gold", "dim_date")
    assert _orphans(fe, du, "user_id").count() == 0
    assert _orphans(fe, da, "account_id").count() == 0
    assert _orphans(fe, dd, "event_date", "date").count() == 0
    assert _orphans(fud, dd, "activity_date", "date").count() == 0


def test_dimension_keys_are_unique(run):
    s = run["store"]
    for table, key in (("dim_user", "user_id"), ("dim_account", "account_id"), ("dim_date", "date")):
        df = s.read("gold", table)
        assert df.count() == df.select(key).distinct().count(), table


def test_dim_date_covers_the_whole_window(run):
    cfg = run["cfg"]
    dd = run["store"].read("gold", "dim_date")
    assert dd.count() == (cfg.window_end - cfg.window_start).days + 1


def test_activation_matches_generator_ground_truth(clean_run):
    with open(clean_run["raw"] / "_ground_truth" / "activation.csv") as fh:
        truth = {r["user_id"]: r["is_activated"] == "true" for r in csv.DictReader(fh)}
    rows = (
        clean_run["store"].read("gold", "dim_user")
        .where("is_new_in_window AND activation_window_complete")
        .select("user_id", "is_activated").collect()
    )
    assert rows
    mismatches = [r["user_id"] for r in rows if truth[r["user_id"]] != r["is_activated"]]
    assert mismatches == []
