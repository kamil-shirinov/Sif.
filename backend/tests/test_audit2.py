"""Tests for the second independent audit (audited at 25ca183). Each test name starts with
the item number of the fix list. No real prices: every series is synthetic."""
import copy
import importlib.util
import json

import numpy as np
import pandas as pd
import pytest

from storm import export, labels
from storm.backtest import index_metrics, provenance, provenance_mismatches
from storm.detector import run_detector
from storm.evaluate import link_alarm
from storm.exposure import book_for, simulate_book, stress_menu, stress_scenarios
from storm.features import pair_features
from storm.labels import label_all, label_as_of
from storm.paths import MOCK_BUNDLE, REPO_ROOT
from storm.validate import validate_bundle, validate_index
from tests.synthetic import write_spot
from tests.test_detector import CFG, EMPTY, toy
from tests.test_labels import _toy_spot

JPY = book_for("USDJPY")
T = lambda s: pd.Timestamp(f"2026-08-07 {s}", tz="UTC")  # noqa: E731


# ---------------------------------------------------------------- 1. point-in-time stress menu

def _menu(rets, as_of):
    """The audit's set-up: storms from the toy history, applied to the 20M long-USDJPY book
    (as in test_audit.py's stress tests, a book marked at its booking price, 160)."""
    feat = toy(rets, start="2026-08-07 10:00")
    book_mid = np.full(3, 160.0)
    path = simulate_book({"USDJPY": book_mid}, JPY)
    return stress_menu({"USDJPY": feat}, EMPTY, path, {"USDJPY": book_mid}, JPY, 1, as_of)


def test_1_stress_menu_does_not_depend_on_prices_after_the_snapshot():
    # The audit's reproducer: identical through 12:30, different afterwards.
    one = [0] * 100 + [-50] + [0] * 200
    two = [0] * 100 + [-50] + [0] * 99 + [-100] + [0] * 100
    a, b = toy(one, start="2026-08-07 10:00"), toy(two, start="2026-08-07 10:00")
    assert a.loc[:T("12:30")].equals(b.loc[:T("12:30")])
    menu_one, menu_two = _menu(one, T("12:30")), _menu(two, T("12:30"))
    assert menu_one == menu_two
    (row,) = menu_one
    assert row["pnl_usd"] == -100_503 and row["scenario"].startswith("USDJPY storm 07 Aug 11:25 UTC: -50 bp")


def test_1_full_history_labels_are_not_point_in_time_and_label_as_of_is():
    two = toy([0] * 100 + [-50] + [0] * 99 + [-100] + [0] * 100, start="2026-08-07 10:00")
    full = label_all({"USDJPY": two}, EMPTY)
    (merged,) = full.itertuples()                           # the -50 bp drop merged into a later storm
    assert merged.first_onset_utc == T("11:25") and merged.trough_utc > T("12:30")
    book_mid = np.full(3, 160.0)
    path = simulate_book({"USDJPY": book_mid}, JPY)
    assert stress_scenarios(full, path, {"USDJPY": book_mid}, JPY, 1, T("12:30")) == []   # the old bug
    (known,) = label_as_of({"USDJPY": two}, T("12:30"), EMPTY).itertuples()
    assert known.trough_utc == T("11:40") and known.end_utc <= T("12:30")


def test_1_label_as_of_equals_labelling_the_cut_history():
    rng = np.random.default_rng(1)
    rets = rng.normal(0, 1e-4, 3000)
    rets[1700:1703] = -12e-4
    rets[2000:2030] = -10e-4
    spot = _toy_spot(150 * np.cumprod(1 + rets))
    feat = pair_features(spot, "USDJPY")
    as_of = feat.index[1900]
    cut = pair_features(spot[spot["timestamp"] <= as_of], "USDJPY")
    pd.testing.assert_frame_equal(label_as_of({"USDJPY": feat}, as_of, EMPTY), label_all({"USDJPY": cut}, EMPTY))


# ---------------------------------------------------------------- 2. provenance of code and calendar content

def _inputs(tmp_path):
    processed = write_spot(tmp_path / "processed")
    cal = tmp_path / "calendar.csv"
    cal.write_text("time_utc,event,region,source_url,verified\n"
                   "2026-07-02T12:30:00Z,Payrolls,US,https://example.org,yes\n")
    cfg = processed / "detector_config.json"
    cfg.write_text(json.dumps({"config": CFG}))
    return processed, cal, cfg


def test_2_patching_a_label_constant_is_a_provenance_mismatch(tmp_path, monkeypatch):
    processed, cal, cfg = _inputs(tmp_path)
    recorded = provenance(processed, cal, cfg)
    assert provenance_mismatches(recorded, provenance(processed, cal, cfg)) == []
    monkeypatch.setattr(labels, "MIN_MOVE_BP", labels.MIN_MOVE_BP + 1)
    assert provenance_mismatches(recorded, provenance(processed, cal, cfg)) == ["code labels"]


def test_2_patching_a_function_is_a_provenance_mismatch(tmp_path, monkeypatch):
    from storm import exposure
    processed, cal, cfg = _inputs(tmp_path)
    recorded = provenance(processed, cal, cfg)
    monkeypatch.setattr(exposure, "max_drawdown", lambda equity: (0.0, 0.0))
    assert provenance_mismatches(recorded, provenance(processed, cal, cfg)) == ["code exposure"]


def test_2_every_calculation_module_is_fingerprinted(tmp_path):
    processed, cal, cfg = _inputs(tmp_path)
    assert set(provenance(processed, cal, cfg)["code"]) >= {
        "labels", "features", "detector", "evaluate", "exposure", "backtest", "export", "equity", "tune"}


def test_2_export_refuses_metrics_computed_with_another_calendar_than_the_file(tmp_path):
    processed, cal, cfg = _inputs(tmp_path)
    v1 = {"storms": 1, "caught": 1, "median_move_ahead_pct": 60.0, "false_alarms_per_day": 0.5}
    # run_backtest(calendar=EMPTY, calendar_path=cal) records the file's hash and the empty content.
    rec = provenance(processed, cal, cfg, calendar=EMPTY)
    assert rec["calendar"] == provenance(processed, cal, cfg)["calendar"]
    (processed / "metrics.json").write_text(json.dumps({"split": "test", "methods": {"v1": v1}, "provenance": rec}))
    with pytest.raises(export.StaleMetrics, match="calendar_content"):
        export.load_index_metrics(processed, cal)
    rec = provenance(processed, cal, cfg)
    (processed / "metrics.json").write_text(json.dumps({"split": "test", "methods": {"v1": v1}, "provenance": rec}))
    assert export.load_index_metrics(processed, cal)["caught"] == 1


def test_2_an_older_provenance_without_code_is_refused(tmp_path):
    processed, cal, cfg = _inputs(tmp_path)
    rec = provenance(processed, cal, cfg)
    del rec["code"], rec["calendar_content"]
    bad = provenance_mismatches(rec, provenance(processed, cal, cfg))
    assert "calendar_content" in bad and "code labels" in bad


# ---------------------------------------------------------------- 3. first_onset in bundles and index.json

def _two_step_storm_bundle():
    """A 36 bp drop, then 5 hours later a 300 bp fall: one storm whose first onset is far
    before its onset (outside the replay window)."""
    rng = np.random.default_rng(0)
    rets = rng.normal(0, 1e-4, 3000)
    rets[1700:1703] = -12e-4
    rets[2000:2030] = -10e-4
    feat = pair_features(_toy_spot(150 * np.cumprod(1 + rets)), "USDJPY").assign(comove=0)
    storms = label_all({"USDJPY": feat}, EMPTY)
    st = next(storms.itertuples())
    ctx = export.Context({"USDJPY": feat}, storms, EMPTY, CFG)
    bundle, _ = export.build_bundle(ctx, st, *export.default_window(feat, st))
    return bundle, st, feat


def test_3_bundle_carries_first_onset_and_the_alarm_against_both_onsets():
    b, st, feat = _two_step_storm_bundle()
    s = b["storm"]
    assert st.first_onset_utc < st.onset_utc - pd.Timedelta(hours=3)
    assert s["first_onset_i"] == int((st.first_onset_utc - st.onset_utc) / pd.Timedelta(minutes=1)) + s["onset_i"]
    assert s["first_onset_i"] < 0                              # before the window: documented, allowed
    assert s["alarm_i"] is not None
    assert s["alarm_minutes"] == s["alarm_i"] - s["onset_i"]
    assert s["alarm_minutes_first_onset"] == s["alarm_i"] - s["first_onset_i"]
    assert s["move_ahead_pct"] is not None and s["move_ahead_pct_first_onset"] is not None
    # the same alarm metrics.json scores (storm.evaluate.link_alarm over the storm-level alarms)
    res = run_detector(feat, EMPTY, CFG)
    early = [a for a, c in res.storm_alarms() if a < st.onset_utc - pd.Timedelta(hours=3)]
    assert early                                               # the first drop alarmed and cleared ...
    linked = link_alarm(res.storm_alarms(), st)                # ... and is not this storm's alarm
    assert linked > early[-1]
    assert s["alarm_i"] == int((linked - st.onset_utc) / pd.Timedelta(minutes=1)) + s["onset_i"]
    assert validate_bundle(b) == []


def test_3_validator_accepts_first_onset_fields_and_rejects_bad_ones():
    b = json.loads(MOCK_BUNDLE.read_text())
    on = b["storm"]["onset_i"]
    fields = {"first_onset_i": on - 500, "alarm_i": on + 3, "alarm_minutes": 3, "alarm_minutes_first_onset": 503,
              "move_ahead_pct": 80.0, "move_ahead_pct_first_onset": 90.0}
    ok = copy.deepcopy(b)
    ok["storm"].update(fields)
    assert validate_bundle(ok) == []
    none = copy.deepcopy(b)
    none["storm"].update({**{k: None for k in fields}, "first_onset_i": on})
    assert validate_bundle(none) == []
    for patch, msg in (({"first_onset_i": on + 1}, "first_onset_i"),
                       ({"alarm_i": None}, "null when alarm_i is null"),
                       ({"move_ahead_pct": 101.0}, "move_ahead_pct"),
                       ({"alarm_i": b["n"]}, "alarm_i")):
        bad = copy.deepcopy(ok)
        bad["storm"].update(patch)
        assert any(msg in e for e in validate_bundle(bad)), patch
    part = copy.deepcopy(b)
    part["storm"]["alarm_i"] = on
    assert any("give all of" in e for e in validate_bundle(part))


def test_3_index_metrics_carry_the_first_onset_figures():
    v1 = {"storms": 6, "caught": 4, "median_move_ahead_pct": 57.4, "false_alarms_per_day": 0.51,
          "caught_first_onset": 4, "median_move_ahead_pct_first_onset": 57.6,
          "median_minutes_to_alarm_first_onset": 9.0}
    m = index_metrics({"split": "test: August 2026", "methods": {"v1": v1}})
    assert (m["caught_first_onset"], m["median_move_ahead_pct_first_onset"],
            m["median_minutes_to_alarm_first_onset"]) == (4, 57.6, 9.0)
    assert validate_index({"schema_version": 1, "storms": [], "metrics": m}) == []
    m["caught_first_onset"] = 7
    assert any("caught_first_onset" in e for e in validate_index({"schema_version": 1, "storms": [], "metrics": m}))


# ---------------------------------------------------------------- 4. the no-warning check's exclusion

def _no_warning_check():
    spec = importlib.util.spec_from_file_location("no_warning_check", REPO_ROOT / "scripts" / "no_warning_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_4_a_window_well_before_the_storm_is_normal():
    nw = _no_warning_check()
    storms = pd.DataFrame([{"pair": "USDJPY", "onset_utc": T("12:00"), "first_onset_utc": T("12:00"),
                            "end_utc": T("12:30")}])
    spans = nw.storm_spans(storms, "USDJPY")
    assert spans == [(T("11:00"), T("13:30"))]                  # 60 min either side, no extra 90
    assert not nw.is_excluded(T("10:30"), spans)                # the audit's 09:00-10:30 candidate
    assert not nw.is_excluded(T("11:00"), spans)                # ends exactly where the span starts
    assert nw.is_excluded(T("11:01"), spans)
    assert nw.is_excluded(T("15:00"), spans) is False and nw.is_excluded(T("14:59"), spans)


def test_4_the_span_starts_at_the_first_onset():
    nw = _no_warning_check()
    storms = pd.DataFrame([{"pair": "USDJPY", "onset_utc": T("12:00"), "first_onset_utc": T("09:00"),
                            "end_utc": T("12:30")}])
    spans = nw.storm_spans(storms, "USDJPY")
    assert spans == [(T("08:00"), T("13:30"))]
    assert nw.is_excluded(T("10:30"), spans) and not nw.is_excluded(T("08:00"), spans)


# ---------------------------------------------------------------- 5. the naive baseline can false-alarm

def test_5_naive_baseline_false_alarms_on_the_two_drop_toy():
    # The 11:40 drop merges into the 13:05 storm (6-hour merge), so the naive alarm at 11:40
    # is outside [onset - 60 min, end + 60 min]: a false alarm. August's zero is data, not design.
    from storm.backtest import naive_alarms
    from storm.evaluate import score
    f = toy([0] * 100 + [-50] + [0] * 99 + [-100] + [0] * 100, start="2026-08-07 10:00")
    storms = label_all({"USDJPY": f}, EMPTY)
    alarms = naive_alarms(f)
    assert [a for a, _ in alarms] == [T("11:40"), T("13:20")]
    m = score({"USDJPY": alarms}, storms, {"USDJPY": f["mid"]}, 1.0)
    assert m["false_alarms"] == 1 and m["alarmed"] == 1


def test_5_triggers_exactly_6_hours_apart_are_one_storm():
    # The first drop (minute 100) triggers the windows ending at minutes 100 to 114; the gap
    # is from its last triggering window to the next one.
    rets = [0] * 100 + [-50] + [0] * 373 + [-50] + [0] * 400      # next trigger at 474: 360 min
    assert len(label_all({"USDJPY": toy(rets, start="2026-08-07 00:00")}, EMPTY)) == 1
    rets = [0] * 100 + [-50] + [0] * 374 + [-50] + [0] * 400      # 361 min: two storms
    assert len(label_all({"USDJPY": toy(rets, start="2026-08-07 00:00")}, EMPTY)) == 2


# ---------------------------------------------------------------- 6. refresh: index order is kept

def test_6_rescanning_the_folder_keeps_the_index_order(tmp_path):
    b = json.loads(MOCK_BUNDLE.read_text())
    for sid in ("z-first", "a-second", "m-new"):
        export.write_bundle({**b, "storm_id": sid, "source": "sgx"}, tmp_path)
    (tmp_path / "index.json").write_text(json.dumps({"schema_version": 1, "metrics": None, "storms": [
        {"file": "z-first.json"}, {"file": "a-second.json"}]}))
    export.write_index(tmp_path, None, None)
    files = [s["file"] for s in json.loads((tmp_path / "index.json").read_text())["storms"]]
    assert files == ["z-first.json", "a-second.json", "m-new.json"]
