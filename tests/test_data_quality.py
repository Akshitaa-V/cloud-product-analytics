"""The silver layer must find exactly the problems the generator injected."""
import pyspark.sql.functions as F

from product_analytics.silver import RULES


def _dq(run) -> dict:
    return {r["check"]: r["rows"] for r in run["store"].read("silver", "dq_summary").collect()}


def test_each_rule_catches_exactly_the_injected_rows(run):
    dq = _dq(run)
    issues = run["manifest"]["issues"]
    for rule in RULES:
        assert dq[rule] == issues[rule], rule


def test_duplicates_are_removed(run):
    assert _dq(run)["duplicate_event_id"] == run["manifest"]["duplicate_rows"]
    events = run["store"].read("silver", "events")
    assert events.count() == events.select("event_id").distinct().count()


def test_epoch_timestamps_are_parsed_not_dropped(run):
    assert _dq(run)["epoch_timestamp_normalized"] == run["manifest"]["epoch_timestamps"]
    cfg = run["cfg"]
    bad = run["store"].read("silver", "events").where(
        F.col("event_date").isNull()
        | (F.col("event_date") < F.lit(cfg.window_start))
        | (F.col("event_date") > F.lit(cfg.window_end))
    )
    assert bad.count() == 0


def test_no_row_is_lost(run):
    dq = _dq(run)
    quarantined = sum(dq[r] for r in RULES)
    assert dq["raw_rows"] == dq["duplicate_event_id"] + quarantined + dq["valid_rows"]


def test_internal_accounts_are_kept_in_silver_but_not_in_gold(run):
    store = run["store"]
    assert _dq(run)["internal_account_event"] == run["manifest"]["internal_account_events"]
    internal = [r["account_id"] for r in store.read("silver", "accounts").where("is_internal").collect()]
    assert internal
    assert store.read("gold", "fact_events").where(F.col("account_id").isin(internal)).count() == 0
