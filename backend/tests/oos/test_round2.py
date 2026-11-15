"""Registered ordering, weekly reset execution, pooled summaries and report agreement."""
import copy
import json

import numpy as np
import pandas as pd
import pytest

from storm.detector import load_calendar, run_detector
from storm.exposure import book_for, policy_backtest
from storm.features import pair_features
from storm.evaluate import for_display
from storm.oos.protocol import DOCS, sha256
from storm.oos.protocol2 import REGISTRATION2, check_registration2, registration2
from storm.oos.report2 import render2
from storm.oos.round2 import (START, evaluate_year, monthly_metrics, policy_summary,
                              selected_prefix, weekly_book, transport_audit)


def features(start="2025-01-06", days=5):
    idx = pd.date_range(start, periods=days * 1440, freq="min", tz="UTC")
    price = 100 + np.sin(np.arange(len(idx)) / 13) * 0.001
    df = pd.DataFrame({"timestamp": idx})
    for col in ("open", "high", "low", "close"):
        df[col + "_mid"] = price
        df[col + "_bid"] = price - 0.0005
        df[col + "_ask"] = price + 0.0005
    feat = pair_features(df, "USDJPY")
    feat["comove"] = 0
    return feat


def fake_manifest(spec):
    return {"preregistration_sha256": sha256(REGISTRATION2),
            "selected_months": [w["id"] for w in spec["months"]],
            "selected_end": spec["months"][-1]["end_exclusive"],
            "months": [{**w, "completed": True, "pairs": [
                {"pair": p, "status": "unusable", "reason": "synthetic unavailable feed", "raw": {},
                 "finished_utc": "2026-11-15T05:00:00Z"} for p in spec["pairs"]]} for w in spec["months"]]}


def test_second_registration_is_frozen_and_separate():
    spec = check_registration2()
    assert len(spec["months"]) == 12
    assert spec["pairs"] == ["EURUSD", "USDJPY", "USDSGD", "GBPUSD", "AUDUSD", "USDCHF"]
    assert spec["differences_from_registration_1"]["config_changed"] is False
    assert spec["differences_from_registration_1"]["code_modules_changed"] == ["exposure", "export", "equity"]
    assert spec["runtime"]["python"] == "3.10.0"


def test_deadline_prefix_is_chronological_and_keeps_unusable_pairs():
    spec = registration2()
    manifest = fake_manifest(spec)
    assert len(selected_prefix(spec, manifest)) == 12  # unusable is still a completed attempt
    for window in manifest["months"][3:]:
        window["completed"] = False
    manifest["selected_months"] = [w["id"] for w in manifest["months"][:3]]
    manifest["selected_end"] = manifest["months"][2]["end_exclusive"]
    assert len(selected_prefix(spec, manifest)) == 3
    manifest["months"][5]["completed"] = True
    with pytest.raises(ValueError, match="chronological prefix"):
        selected_prefix(spec, manifest)


def test_deadline_cannot_count_late_completion():
    spec = registration2()
    manifest = fake_manifest(spec)
    manifest["months"][0]["pairs"][0]["finished_utc"] = "2026-11-15T07:06:00Z"
    with pytest.raises(ValueError, match="after hard cutoff"):
        selected_prefix(spec, manifest)


def test_weekly_policy_matches_core_without_a_carry_in():
    feat = features()
    cfg, cal = registration2()["config"], load_calendar()
    detected = run_detector(feat, cal, cfg, exposure=1)
    start, end = feat.index[0], feat.index[-1] + pd.Timedelta(minutes=1)
    weekly = weekly_book("USDJPY", feat, detected.events, start, end)
    original = policy_backtest({"USDJPY": feat}, cfg, start, end, cal, book_for("USDJPY"))
    for ship in ("prepared", "unprepared"):
        for key in ("final_equity_usd", "max_drawdown_usd", "max_drawdown_pct", "margin_calls", "spread_cost_usd"):
            assert weekly[ship][key] == original[ship][key]


def test_week_reset_pays_for_carry_in_alarm_and_restores():
    feat = features()
    first = feat.index[0]
    events = [{"type": "alarm", "time": first - pd.Timedelta(minutes=30)},
              {"type": "all_clear", "time": first + pd.Timedelta(minutes=5)}]
    weekly = weekly_book("USDJPY", feat, events, first, first + pd.Timedelta(days=5))
    assert weekly["carry_in_alarm_utc"] == events[0]["time"].isoformat()
    trades = weekly["prepared"]["trades"]
    assert trades[0]["action"] == "cut"
    assert trades[0]["signal_utc"] == first.isoformat()
    assert trades[0]["utc"] == (first + pd.Timedelta(minutes=1)).isoformat()
    assert trades[0]["side"] == "sell"
    assert trades[0]["fill_price"] < trades[0]["mid_price"]
    assert weekly["prepared"]["spread_cost_usd"] > 0
    assert weekly["prepared"]["restores"] == 1
    events[1]["time"] = first
    weekly = weekly_book("USDJPY", feat, events, first, first + pd.Timedelta(days=5))
    assert weekly["carry_in_alarm_utc"] is None
    assert weekly["prepared"]["cuts"] == 0


def test_week_below_coverage_threshold_is_listed_unavailable():
    feat = features(days=1)
    result = weekly_book("USDJPY", feat, [], feat.index[0], feat.index[0] + pd.Timedelta(days=5))
    assert result["status"] == "unavailable"
    assert "coverage" in result["reason"]


def test_helped_classification_is_unrounded_and_margin_outcomes_are_distinct():
    rows = []
    for delta, outcome in [(0.0001, "avoided"), (-2, "induced"), (0, "both"), (3, "neither")]:
        ship = {"spread_cost_usd": 1.0, "margin_calls": 0, "cuts": 1, "restores": 1, "fills": 2,
                "final_equity_usd": 1_000_000.0, "max_drawdown_usd": 10.0, "max_drawdown_pct": 0.001}
        rows.append({"status": "usable", "difference_usd": delta, "margin_outcome": outcome,
                     "prepared": ship, "unprepared": ship})
    summary = policy_summary(rows)
    assert summary["helped"] == 2 and summary["ties"] == 1 and summary["hurt"] == 1
    assert summary["helped_share_pct"] == 50
    assert summary["total_difference_usd"] == pytest.approx(1.0001)
    assert summary["margin_calls_avoided"] == summary["margin_calls_induced"] == summary["both_margin_called"] == 1


def test_monthly_false_episodes_do_not_split_at_calendar_boundary():
    feat = features(start="2025-01-31", days=2)
    first = pd.Timestamp("2025-01-31 23:58", tz="UTC")
    second = first + pd.Timedelta(minutes=5)
    false = [{"pair": "USDJPY", "alarm_utc": t.isoformat()} for t in (first, second)]
    annual = {"per_storm": []}
    detected = run_detector(feat, load_calendar(), registration2()["config"], exposure=1)
    common = (annual, false, {"USDJPY": [(first, None), (second, None)]},
              {"USDJPY": detected}, {"USDJPY": feat})
    jan = monthly_metrics(*common, pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp("2025-02-01", tz="UTC"))
    feb = monthly_metrics(*common, pd.Timestamp("2025-02-01", tz="UTC"), pd.Timestamp("2025-03-01", tz="UTC"))
    assert jan["false_alarm_episodes"] == 1 and feb["false_alarm_episodes"] == 0
    assert jan["false_alarms"] == feb["false_alarms"] == 1


def test_missing_all_source_data_is_explicit_and_does_not_swap_periods():
    spec = registration2()
    result = evaluate_year(spec, fake_manifest(spec))
    assert result["usable_pair_months"] == 0
    assert result["status"] == "unassessed_no_usable_observations"
    assert len(result["pairs"]) == 6
    assert sum(len(p["months"]) for p in result["pairs"]) == 72
    assert result["policy"]["usable_pair_weeks"] == 0
    assert all(w["status"] == "unavailable" for w in result["weeks"])


def test_prefix_keeps_the_rest_of_years_planned_weeks_visible():
    spec = registration2()
    manifest = fake_manifest(spec)
    for month in manifest["months"][1:]:
        month["completed"] = False
    manifest["selected_months"] = ["2025-01"]
    manifest["selected_end"] = "2025-02-01"
    result = evaluate_year(spec, manifest)
    assert len(result["weeks"]) == 318
    assert result["policy"]["planned_pair_weeks"] == 318
    assert any(w["status"] == "not_completed_by_deadline" for w in result["weeks"])
    assert all(w["status"] == "not_completed_by_deadline" for w in result["weeks"]
               if pd.Timestamp(w["from_utc"]) >= pd.Timestamp("2025-02-01", tz="UTC"))


def test_one_detector_pass_feeds_monthly_scoring_and_all_weekly_books(tmp_path, monkeypatch):
    import storm.oos.round2 as module
    monkeypatch.setattr(module, "DATA2", tmp_path)
    spec = registration2()
    manifest = fake_manifest(spec)
    feat = features(start="2024-12-27", days=10)
    mid = feat["mid"].copy()
    mid.loc[pd.Timestamp("2025-01-02", tz="UTC"):] *= 0.97
    bars = pd.DataFrame({"timestamp": feat.index})
    for field in ("open", "high", "low", "close"):
        bars[field + "_mid"] = mid.to_numpy()
        bars[field + "_bid"] = mid.to_numpy() - 0.0005
        bars[field + "_ask"] = mid.to_numpy() + 0.0005
    path = tmp_path / "USDJPY_SPOT.parquet"
    bars.to_parquet(path, index=False)
    rec = manifest["months"][0]["pairs"][1]
    rec.update(status="usable", reason=None, parquet={"path": path.name})
    calls = []
    def counted(*args, **kwargs):
        calls.append(1)
        return run_detector(*args, **kwargs)
    monkeypatch.setattr(module, "run_detector", counted)
    exact = evaluate_year(spec, manifest)
    assert len(calls) == 1
    assert exact["metrics"]["storms"] > 0
    assert sum(r["metrics"]["storms"] for p in exact["pairs"] for r in p["months"] if r["metrics"]) == exact["metrics"]["storms"]
    assert len(exact["weeks"]) == 318  # fifty-three independently reset weeks on each of six pairs
    result = {"exact": exact, "display": for_display(exact), "provenance": {
        "preregistration_commit": "synthetic", "base_commit": "synthetic", "config_sha256": "synthetic"}}
    result = json.loads(json.dumps(result, allow_nan=False))
    assert "Every primary miss" in render2(result)


def test_exhausted_artifacts_cannot_be_queried_again(tmp_path, monkeypatch):
    import storm.oos.round2 as module
    monkeypatch.setattr(module, "DATA2", tmp_path)
    url = "https://datafeed.dukascopy.com/datafeed/USDJPY/2025/00/02/BID_candles_min_1.bi5"
    (tmp_path / "exhausted-urls.json").write_text(json.dumps([url]))
    folder = tmp_path / "2025-01/raw"
    folder.mkdir(parents=True)
    log = folder / "USDJPY_bid_http.jsonl"
    log.write_text(json.dumps({"url": url, "status": 503, "network": False, "exhausted_previous_pass": True}) + "\n")
    manifest = {"months": [{"id": "2025-01"}]}
    assert transport_audit(manifest)["known_network_requests"] == 0
    log.write_text(json.dumps({"url": url, "status": 200}) + "\n")
    with pytest.raises(ValueError, match="queried again"):
        transport_audit(manifest)


def test_results2_markdown_and_json_agree():
    saved = json.loads((DOCS / "results-2.json").read_text())
    assert (DOCS / "results-2.md").read_text() == render2(saved)
    assert saved["provenance"]["preregistration_sha256"] == sha256(REGISTRATION2)
    assert len(saved["exact"]["pairs"]) == 6
    modified = copy.deepcopy(saved)
    modified["exact"]["metrics"]["caught"] += 1
    with pytest.raises(ValueError, match="display disagrees"):
        render2(modified)
