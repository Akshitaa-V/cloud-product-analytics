import json

from product_analytics.generate import GenConfig, generate


def test_same_seed_gives_same_data(tmp_path):
    a = generate(tmp_path / "a", GenConfig(n_accounts=10, seed=3))
    b = generate(tmp_path / "b", GenConfig(n_accounts=10, seed=3))
    assert a == b
    for f in sorted((tmp_path / "a" / "events").glob("*.jsonl")):
        assert f.read_bytes() == (tmp_path / "b" / "events" / f.name).read_bytes()


def test_clean_mode_has_no_problems(tmp_path):
    m = generate(tmp_path, GenConfig(n_accounts=10, seed=3, inject_issues=False))
    assert m["issues"] == {} and m["duplicate_rows"] == 0
    assert m["raw_event_rows"] == m["clean_events"]


def test_events_are_valid_json_lines(tmp_path):
    generate(tmp_path, GenConfig(n_accounts=10, seed=3))
    for f in (tmp_path / "events").glob("*.jsonl"):
        for line in f.read_text().splitlines():
            event = json.loads(line)
            assert {"event_id", "event_name", "event_ts", "account_id"} <= set(event)
