"""Independent statistical invariants and scorer/oracle agreement, not snapshots."""
import copy
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from storm.detector import DetectorResult, Episode
from storm.evaluate import score
from storm.exposure import Quotes
from storm.labels import STORM_COLUMNS
from storm.stats.bootstrap import uncertainty, paired_caught_difference
from storm.stats.datasets import Unit, evaluate_unit
from storm.stats.policy import PolicyInput, batch, oracle, check_batch
from storm.stats.protocol import rng_for
from storm.stats.pooling import prepare_pooling, pooled_metric
from storm.stats.randomization import prepare_train, caught_counts, alarms_at, null_summary, holm


def fixture_unit():
    idx = pd.date_range("2026-08-01", periods=180, freq="min", tz="UTC")
    mid = np.ones(180)
    mid[60:76] = np.linspace(1, 0.97, 16)
    mid[76:] = 0.97
    feat = pd.DataFrame({"mid": mid}, index=idx)
    storm = {"storm_id": "s", "pair": "EURUSD", "onset_utc": idx[60], "trough_utc": idx[75],
             "end_utc": idx[80], "onset_mid": 1.0, "trough_mid": .97, "first_onset_utc": idx[55],
             "first_onset_mid": 1.0, "kind": "unscheduled", "move_bp": -300, "duration_min": 15}
    storms = pd.DataFrame([storm])
    cal = pd.DataFrame(columns=["time_utc"])
    unit = Unit("test", "test-unit", {"EURUSD": feat}, storms, idx[0], idx[-1] + pd.Timedelta(minutes=1), cal)
    episodes = [Episode(idx[63], idx[63], -1, idx[90]), Episode(idx[130], idx[130], -1, None)]
    detection = DetectorResult(pd.DataFrame({"risk": np.ones(180)}, index=idx),
        [{"type": "alarm", "time": idx[64], "clear": idx[90]}, {"type": "alarm", "time": idx[131], "clear": None}], episodes)
    return unit, detection


def test_translation_preserves_counts_clock_durations_and_matches_original_scorer():
    unit, detection = fixture_unit()
    train = prepare_train(unit, "EURUSD", detection)
    offsets = train.feasible
    values, _ = caught_counts(unit, {"EURUSD": train}, {"EURUSD": offsets}, len(offsets))
    for k, offset in enumerate(offsets):
        rows = alarms_at(train, offset)
        assert len(rows) == len(train.alarms)
        assert sorted(int((c-a)/pd.Timedelta(minutes=1)) for a, c, _ in rows) == sorted(train.durations)
        exact = score({"EURUSD": [(a,c) for a,c,_ in rows]}, unit.storms, {"EURUSD": unit.feats["EURUSD"].mid}, 1)
        assert values[k] == exact["caught"]
    # A right-censored train must not acquire a fictional restore.
    assert train.censored.tolist() == [False, True]


def test_null_p_value_ties_and_holm_monotonicity():
    a = null_summary(4, [0, 4, 5])
    assert a["exceedances"] == 2 and a["p_value"] == .75
    tests = [{"p_value": .01}, {"p_value": .04}, {"p_value": .03}]
    holm(tests)
    assert [t["holm_p_value"] for t in tests] == pytest.approx([.03, .06, .06])


def test_zero_storms_null_conditional_medians_and_zero_alarm_days():
    empty = uncertainty([], [{"dataset": "x", "unit": "u", "date": "d", "observed_minutes": 1440, "episodes": 0}], "empty", 40)
    assert empty["point"]["caught_share"] is None
    assert empty["intervals"]["median_share_ahead_pct"]["ci95"] == [None, None]
    assert empty["intervals"]["false_alert_episodes_per_observed_day"]["ci95"] == [0, 0]
    unit, detection = fixture_unit()
    data = evaluate_unit(unit, {"EURUSD": []})
    res = uncertainty(data["per_storm"], data["daily"], "missed", 40)
    assert res["point"]["caught_share"] == 0
    assert res["intervals"]["median_minutes_to_alarm"]["undefined_replicates"] == 40


def test_bootstrap_paired_and_stable_streams():
    unit, _ = fixture_unit()
    data = evaluate_unit(unit, {"EURUSD": [(unit.feats["EURUSD"].index[61], None)]})
    rows = data["per_storm"]
    other = copy.deepcopy(rows)
    other[0]["caught"] = False
    result = paired_caught_difference(rows, other, "paired", 40)
    assert result["estimate"] == 1 and result["ci95"] == [1, 1]
    assert np.array_equal(rng_for("a").integers(100, size=20), rng_for("a").integers(100, size=20))


def test_pooled_overlap_removes_duplicate_exposure_storms_and_whole_books_without_relabelling():
    from dataclasses import replace
    unit, _ = fixture_unit()
    idx = unit.feats["EURUSD"].index
    prior = replace(unit, dataset="oos_round1", name="prior", end=idx[100], metadata={"source":"Dukascopy"})
    later = replace(unit, dataset="oos_round2", name="later", metadata={"source":"Dukascopy"}, policy_windows=[
        {"name":"overlap", "pairs":["EURUSD"], "start":idx[0], "end":idx[-1]},
        {"name":"distinct", "pairs":["EURUSD"], "start":idx[150], "end":unit.end}])
    prepare_pooling([later, prior])  # Priority must not depend on input order.
    assert later.metadata["pooling_summary"]["duplicate_minutes_by_pair"] == {"EURUSD":100}
    assert later.metadata["pool_keep_book"] == {"overlap":False,"distinct":True}
    assert later.metadata["pool_keep_storm"] == {"s":False}
    # This retained alarm is in the original storm's false-exclusion buffer. Removing
    # that storm from the pooled contribution must not turn the alarm false.
    alarms = {"EURUSD":[(idx[100],idx[120])]}
    original = evaluate_unit(later, alarms)
    pooled = pooled_metric(later, alarms, original)
    assert original["storms"] == 1 and pooled["storms"] == 0
    assert sum(r["observed_minutes"] for r in pooled["daily"]) == 80
    assert pooled["false_alarm_episodes"] == 0
    assert prior.metadata["pooling_summary"]["duplicate_minutes_by_pair"] == {"EURUSD":0}


def test_frozen_policy_restore_and_initial_margin_are_exercised():
    n = 8
    idx = pd.date_range("2026-08-01", periods=n, freq="min", tz="UTC")
    price = np.array([100,100,100,95,90,95,120,121.])
    q = Quotes.from_mid(price)
    book = {"equity_usd":1e6,"position_usd":4e6,"symbol":"NVDA","maintenance_margin":.15,"cut_fraction":.75}
    inp = PolicyInput("restore",["NVDA"],idx,{"NVDA":q},book,True,idx[0],idx[-1])
    actions = [(1,"NVDA","cut"),(5,"NVDA","restore")]
    result = batch(inp,[actions])[0]
    assert result == pytest.approx(oracle(inp,actions),rel=1e-9,abs=1e-5)
    assert result["cuts"] == result["restores"] == 1
    book = {**book,"position_usd":10e6}
    inp = replace(inp, book=book)
    result = batch(inp,[actions])[0]
    assert result == pytest.approx(oracle(inp,actions),rel=1e-9,abs=1e-5)
    assert result["margin_calls"] == 1 and result["cuts"] == 0


@pytest.mark.parametrize("stock", [False, True])
def test_native_policy_agrees_with_frozen_oracle_including_margin_gaps_and_restores(stock):
    rng = np.random.default_rng(42)
    n = 240
    idx = pd.date_range("2026-08-01", periods=n, freq="min", tz="UTC")
    pairs = ["NVDA"] if stock else ["EURUSD", "USDJPY"]
    quotes = {}
    for p in pairs:
        mid = np.exp(np.cumsum(rng.normal(0, .008, n))) * (100 if p != "EURUSD" else 1)
        po = np.r_[mid[0], mid[:-1]] * np.exp(rng.normal(0, .004, n))
        spread = 0 if stock else .0002
        traded = np.ones(n, bool)
        traded[60:70] = False
        mid[60:70] = mid[59]
        po[60:70] = mid[59]
        quotes[p] = Quotes(mid, po, po*(1-spread), po*(1+spread), mid*(1-spread), mid*(1+spread), traded)
    book = {"equity_usd": 1e6, "position_usd": 4e6, "symbol": "NVDA", "maintenance_margin": .15, "cut_fraction": .75} if stock else {
        "equity_usd": 1e6, "legs": [{"pair": p, "usd_notional": 10e6} for p in pairs], "maintenance_margin": .025, "cut_fraction": .75}
    inp = PolicyInput("synthetic", pairs, idx, quotes, book, stock, idx[0], idx[-1])
    schedules = [[], [(5,pairs[0],"cut"),(62,pairs[0],"restore")],
                 [(25,p,"cut") for p in pairs] + [(80,p,"restore") for p in pairs],
                 [(1,pairs[0],"cut"),(170,pairs[0],"restore")]]
    results = batch(inp, schedules)
    assert check_batch(inp, schedules, results)["passed"]
    for actions, result in zip(schedules, results):
        assert result == pytest.approx(oracle(inp, actions), rel=1e-9, abs=1e-5)
