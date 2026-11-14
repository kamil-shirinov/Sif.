"""One test (or more) per finding of the independent backend audit (audited at 7938f60).
Each test name starts with the finding number. No real prices: every series is synthetic."""
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from storm import equity as eq
from storm import export
from storm.backtest import provenance
from storm.detector import WATCH, load_calendar, risk_frame, run_detector
from storm.evaluate import (LINK_BEFORE, alarm_matches, false_alarm_episodes, for_display, link_alarm, observed_minutes,
                            per_storm_row, score)
from storm.exposure import (Quotes, book_for, simulate_book, stress_scenarios, stress_test)
from storm.features import bar_features, pair_features
from storm.labels import label_all, scheduled_event, window_moves
from tests.synthetic import write_spot
from tests.test_detector import CFG, EMPTY, toy
from tests.test_equity import _raw, _session_index
from tests.test_labels import _toy_spot

JPY, EUR = book_for("USDJPY"), book_for("EURUSD")
T = lambda s: pd.Timestamp(f"2026-08-07 {s}", tz="UTC")  # noqa: E731


# ---------------------------------------------------------------- 1. time units

@pytest.mark.parametrize("unit", ["us", "ms", "s"])
def test_1_detector_is_independent_of_the_index_time_unit(unit):
    f = toy([0] * 30 + [-10, -10] + [0] * 10 + [-6] * 3 + [0] * 40)
    f.index = f.index.where(f.index < f.index[50], f.index + pd.Timedelta(minutes=3))   # a gap
    g = f.copy()
    g.index = g.index.as_unit(unit)
    pd.testing.assert_frame_equal(risk_frame(f, CFG).reset_index(drop=True),
                                  risk_frame(g, CFG).reset_index(drop=True))
    a, b = run_detector(f, EMPTY, CFG, exposure=1), run_detector(g, EMPTY, CFG, exposure=1)
    assert [(e["type"], e["time"]) for e in a.events] == [(e["type"], e["time"]) for e in b.events]
    assert (a.frame["state"].to_numpy() == b.frame["state"].to_numpy()).all()


def test_1_features_normalise_the_index_to_nanoseconds():
    spot = _toy_spot(np.full(50, 150.0))
    spot["timestamp"] = spot["timestamp"].dt.as_unit("us")
    assert pair_features(spot, "USDJPY").index.unit == "ns"


def test_1_pandas_is_pinned_below_3():
    from storm.paths import REPO_ROOT
    req = (REPO_ROOT / "backend" / "requirements.txt").read_text().splitlines()
    assert "pandas>=2.2,<3" in req


# ---------------------------------------------------------------- 2. execution

def _quotes(mid, half_spread):
    mid = np.asarray(mid, dtype=float)
    prev = np.concatenate([mid[:1], mid[:-1]])
    return Quotes(mid, prev, prev - half_spread, prev + half_spread, mid - half_spread, mid + half_spread,
                  np.ones(len(mid), dtype=bool))


def test_2_cut_fills_at_the_next_open_bid_for_usdjpy_and_records_its_cost():
    q = _quotes([100.0, 99.0, 98.0, 98.0], 0.01)
    p = simulate_book({"USDJPY": q}, JPY, [(2, "USDJPY", "cut")])          # signal on bar 1
    (f,) = p.fills
    assert (f["i"], f["signal_i"], f["side"], f["at"]) == (2, 1, "sell", "open")
    assert f["price"] == pytest.approx(99.0 - 0.01) and f["mid"] == pytest.approx(99.0)   # bar 2 open = 99
    assert f["qty"] == pytest.approx(15e6)
    assert f["cost_usd"] == pytest.approx(15e6 * 0.01 / 99.0)              # JPY cost converted at mid
    assert p.qty["USDJPY"][1] == pytest.approx(20e6) and p.qty["USDJPY"][2] == pytest.approx(5e6)


def test_2_eurusd_cut_buys_eur_back_at_the_ask_and_restore_sells_at_the_bid():
    q = _quotes([1.15, 1.16, 1.17, 1.17, 1.16], 0.0001)
    p = simulate_book({"EURUSD": q}, EUR, [(2, "EURUSD", "cut"), (4, "EURUSD", "restore")])
    cut, restore = p.fills
    assert cut["side"] == "buy" and cut["price"] == pytest.approx(1.16 + 0.0001)
    assert restore["side"] == "sell" and restore["price"] == pytest.approx(1.17 - 0.0001)
    assert cut["cost_usd"] == pytest.approx(cut["qty"] * 0.0001)
    assert p.spread_cost_usd == pytest.approx(cut["cost_usd"] + restore["cost_usd"])


def test_2_a_fill_waits_for_the_next_bar_with_a_real_quote():
    q = _quotes([100.0, 99.0, 99.0, 98.0, 97.0], 0.0)
    q.traded[2] = False                                     # bar 2 missing (held quotes)
    p = simulate_book({"USDJPY": q}, JPY, [(2, "USDJPY", "cut")])
    assert p.cut_i == 3 and p.fills[0]["price"] == pytest.approx(99.0)    # bar 3 opens at bar 2's held close


# ---------------------------------------------------------------- 3. margin order

def test_3_breach_at_the_alarm_close_is_a_margin_call_even_with_a_cut_scheduled():
    # 20M long USD on 1M: maintenance breaks below 97.561. The alarm bar (1) closes at 97.5;
    # the cut scheduled for bar 2 never happens.
    p = simulate_book({"USDJPY": np.array([100.0, 97.5, 99.0, 99.0])}, JPY, [(2, "USDJPY", "cut")])
    assert p.margin_call_i == 1 and p.cuts == [] and p.qty["USDJPY"][1] == 0


def test_3_maintenance_is_tested_at_the_open_before_a_trade_in_that_minute():
    # Bar 2 opens at 97.5 (gap below maintenance) and closes back at 99: the open test
    # liquidates before the scheduled cut can fill.
    mid = np.array([100.0, 99.0, 99.0, 99.0])
    q = Quotes(mid, np.array([100.0, 99.0, 97.5, 99.0]), np.array([100.0, 99.0, 97.5, 99.0]),
               np.array([100.0, 99.0, 97.5, 99.0]), mid, mid, np.ones(4, dtype=bool))
    p = simulate_book({"USDJPY": q}, JPY, [(2, "USDJPY", "cut")])
    assert p.margin_call_i == 2 and p.cuts == [] and p.fills[0]["action"] == "margin_call"
    assert p.fills[0]["at"] == "open" and p.fills[0]["price"] == 97.5


# ---------------------------------------------------------------- 4. causal bad prints

def test_4_bad_print_is_visible_at_its_minute_and_excluded_from_the_next_one():
    idx = _session_index([10])
    raw = _raw(idx, 2, sd_bp=1.0)
    k = 800                                                              # after the 720-bar warm-up
    raw.loc[k, ["close", "high"]] = raw.loc[k - 1, "close"] * 1.065      # spike; bar k+1 opens back
    bars = eq.bars_from_raw(raw, "X")
    f = bar_features(bars)
    clean = bar_features(bars[bars["bad_print"] == 0].drop(columns="bad_print"))
    t, nxt = idx[k], idx[k + 1]
    assert f.loc[t, "ret_bp"] == pytest.approx((1.065 - 1) * 1e4) and f.loc[t, "jump"] == 1   # visible
    assert f.loc[t, "sd_24h"] == pytest.approx(clean.loc[nxt, "sd_24h"])   # history before it
    after = f.index > t
    for col in ("sd_24h", "z", "vol_ratio"):                               # later bars never see it
        pd.testing.assert_series_equal(f.loc[after, col], clean.loc[clean.index > t, col], check_names=False)
    rf = risk_frame(f.assign(comove=0), CFG)
    assert rf.loc[t, "risk"] == 1.0 and rf.loc[t, "direction"] == 1       # it can alarm at its minute
    assert rf.loc[nxt:, "strength"].max() < 6                              # the reversal is never measured


# ---------------------------------------------------------------- 5. calendar

def test_5_only_verified_rows_with_a_source_url_create_watches(tmp_path):
    cal = tmp_path / "calendar.csv"
    cal.write_text("time_utc,event,region,source_url,verified\n"
                   "2026-07-30T10:40:00Z,Good,US,https://www.bls.gov/schedule/,yes\n"
                   "2026-07-30T12:40:00Z,Unverified,US,https://www.bls.gov/schedule/,no\n"
                   "2026-07-30T14:40:00Z,No source,US,,yes\n"
                   "2026-07-30T16:40:00Z,True is not yes,US,https://example.org,true\n")
    c = load_calendar(cal)
    assert c["event"].tolist() == ["Good"]
    res = run_detector(toy([0] * 480), c, CFG)
    assert [e["event"] for e in res.events if e["type"] == "watch"] == ["Good"]
    assert (res.frame["state"] == WATCH).sum() == 45


# ---------------------------------------------------------------- 6 and 7. stress

def _storms(*rows):
    return pd.DataFrame([{"storm_id": s, "pair": p, "onset_utc": T(o), "trough_utc": T(tr),
                          "onset_mid": om, "trough_mid": tm, "move_bp": (tm / om - 1) * 1e4}
                         for s, p, o, tr, om, tm in rows])


def test_6_stress_menu_uses_only_storms_whose_trough_came_before_the_snapshot():
    path = simulate_book({"USDJPY": np.full(3, 160.0)}, JPY)
    storms = _storms(("a", "USDJPY", "10:00", "10:30", 160.0, 155.0),
                     ("b", "USDJPY", "11:50", "12:05", 160.0, 150.0),     # trough after the snapshot
                     ("c", "EURUSD", "12:20", "12:40", 1.15, 1.16))       # the replay's own time
    menu = stress_scenarios(storms, path, {"USDJPY": np.full(3, 160.0)}, JPY, 1, T("12:00"))
    assert len(menu) == 1 and menu[0]["scenario"].startswith("USDJPY storm 07 Aug 10:00")
    assert stress_scenarios(storms, path, {"USDJPY": np.full(3, 160.0)}, JPY, 1, T("10:30")) == []


def test_7_stress_uses_marked_eurusd_notional_and_the_snapshots_holdings():
    # A EURUSD +3% storm (USD -2.9126%) on the full long-USD EURUSD book: P&L -600k exactly.
    # Marked notional is 20.6M after the shock: maintenance 515k, so equity 400k is a call.
    full = simulate_book({"EURUSD": np.full(3, 1.15)}, EUR)
    storms = _storms(("e", "EURUSD", "10:00", "10:15", 1.15, 1.15 * 1.03))
    (row,) = stress_scenarios(storms, full, {"EURUSD": np.full(3, 1.15)}, EUR, 1, T("12:00"))
    assert row["pnl_usd"] == -600_000 and row["margin_call"] is True
    assert "applied as USD -291 bp" in row["scenario"]
    # After a 75% cut the same shock costs a quarter (plus nothing else: no spread here).
    cut = simulate_book({"EURUSD": np.full(3, 1.15)}, EUR, [(1, "EURUSD", "cut")])
    (row,) = stress_scenarios(storms, cut, {"EURUSD": np.full(3, 1.15)}, EUR, 2, T("12:00"))
    assert row["pnl_usd"] == -150_000 and row["margin_call"] is False


def test_7_stress_shock_is_unrounded():
    path = simulate_book({"USDJPY": np.full(3, 160.0)}, JPY)
    storms = _storms(("a", "USDJPY", "10:00", "10:30", 160.0, 160.0 * (1 - 0.0290449)))
    (row,) = stress_scenarios(storms, path, {"USDJPY": np.full(3, 160.0)}, JPY, 1, T("12:00"))
    assert row["pnl_usd"] == round(20e6 * (1 - 1 / (1 - 0.0290449)))       # not the -290.4 bp rounding


def test_7_navigator_stress_keeps_its_signature_and_results():
    onset = pd.Timestamp("1970-01-01T00:01:00Z")
    storms = pd.DataFrame([{"pair": "EURUSD", "onset_utc": onset, "move_bp": 300.0,
                            "usd_move_bp": (1 / 1.03 - 1) * 1e4}])
    (row,) = stress_test(storms, pd.Series([1.0], index=[onset - pd.Timedelta(minutes=1)]), EUR)
    assert row["pnl_usd"] == -600_000 and row["margin_call"] is True


# ---------------------------------------------------------------- 8. one matcher

def _storm_row(onset="12:20", trough="12:35"):
    return SimpleNamespace(storm_id="s", pair="USDJPY", onset_utc=T(onset), trough_utc=T(trough),
                           end_utc=T("12:46"), onset_mid=100.0, trough_mid=99.0,
                           first_onset_utc=T("12:15"), first_onset_mid=100.0)


def test_8_matcher_rejects_an_alarm_that_cleared_before_onset():
    st = _storm_row()
    assert not alarm_matches(T("11:30"), T("12:00"), st)
    assert alarm_matches(T("11:30"), T("12:20"), st) and alarm_matches(T("12:25"), None, st)
    assert link_alarm([(T("11:30"), T("12:00"))], st) is None


def test_8_export_uses_the_same_matcher_for_bundle_alarms(tmp_path):
    # A sharp drop at 10:00 alarms and clears (20 calm minutes) by ~10:23. A storm labelled
    # with onset 10:40 is within 60 minutes of that alarm, but the alarm cleared first: the
    # bundle must not credit it (no move_ahead_pct, "turbulence").
    rng = np.random.default_rng(3)
    rets = rng.normal(0, 1e-4, 3000)
    rets[2000:2003] = -8e-4
    spot = _toy_spot(150 * np.cumprod(1 + rets), start="2026-07-01 00:00")
    feat = pair_features(spot, "USDJPY").assign(comove=0)
    res = run_detector(feat, EMPTY, CFG, exposure=1)
    alarm = next(e for e in res.events if e["type"] == "alarm")
    assert alarm["clear"] is not None
    onset = alarm["clear"] + pd.Timedelta(minutes=5)
    trough = onset + pd.Timedelta(minutes=10)
    storms = pd.DataFrame([{"storm_id": "usdjpy-test", "pair": "USDJPY", "onset_utc": onset, "trough_utc": trough,
                            "end_utc": trough, "move_bp": -10.0, "usd_move_bp": -10.0, "duration_min": 10,
                            "onset_mid": float(feat["mid"][onset]), "trough_mid": float(feat["mid"][trough]),
                            "kind": "unscheduled", "event": "", "event_utc": pd.NaT,
                            "first_onset_utc": onset, "first_onset_mid": float(feat["mid"][onset])}])
    assert onset - LINK_BEFORE <= alarm["time"] <= trough        # the old window-only rule credited it
    st = next(storms.itertuples())
    assert not alarm_matches(alarm["time"], alarm["clear"], st)
    ctx = export.Context({"USDJPY": feat}, storms, EMPTY, CFG)
    bundle, _ = export.build_bundle(ctx, st, *export.default_window(feat, st))
    ev = next(e for e in bundle["events"] if e["type"] == "alarm")
    assert ev["move_ahead_pct"] is None and "(turbulence)" in ev["text"]


# ---------------------------------------------------------------- 9. no rounding before classification

def test_9_caught_is_decided_on_the_unrounded_share():
    st = _storm_row()
    idx = pd.date_range(T("12:00"), T("13:00"), freq="min")
    mid = pd.Series(100.0, index=idx)
    mid[T("12:25")] = 99.4996                     # 49.96% ahead: rounds to 50.0, but is not >= 50
    row = per_storm_row(st, T("12:25"), mid)
    assert row["move_ahead_pct"] == pytest.approx(49.96) and row["caught"] is False
    assert for_display(row)["move_ahead_pct"] == 50.0                      # only the display rounds
    assert for_display({"median_move_ahead_pct_first_onset": 57.5718})["median_move_ahead_pct_first_onset"] == 57.6


def test_9_false_alarm_rate_is_unrounded_for_the_tuning_constraint():
    alarms = {"USDJPY": [(T("15:00"), None), (T("16:00"), None), (T("17:00"), None)]}
    m = score(alarms, pd.DataFrame([vars(_storm_row())]), {"USDJPY": pd.Series(dtype=float)}, days=2.995)
    assert m["false_alarms_per_day"] == pytest.approx(3 / 2.995) and m["false_alarms_per_day"] > 1.0
    assert for_display(m)["false_alarms_per_day"] == 1.0                   # would have passed <= 1.0 rounded


# ---------------------------------------------------------------- 10. scheduled matching and hidden watch

def test_10_scheduled_matching_is_15_minutes_inclusive_on_both_sides(tmp_path):
    cal = tmp_path / "calendar.csv"
    cal.write_text("time_utc,event,region,source_url,verified\n2026-07-02T12:30:00Z,Payrolls,US,https://example.org,yes\n")
    c = load_calendar(cal)
    t = lambda hm: pd.Timestamp(f"2026-07-02 {hm}", tz="UTC")  # noqa: E731
    assert scheduled_event(t("12:15"), c)[0] == "Payrolls" and scheduled_event(t("12:45"), c)[0] == "Payrolls"
    assert scheduled_event(t("12:14"), c) is None and scheduled_event(t("12:46"), c) is None
    # (the watch hidden at its start by a storm is test_detector.py::
    #  test_watch_hidden_at_its_start_is_announced_when_first_shown)


# ---------------------------------------------------------------- 11. false-alarm episodes

def test_11_alert_episode_is_anchored_at_its_first_alarm():
    # 15:00, 15:14, 15:28: a chained rule would make one episode 28 minutes long; anchored,
    # 15:28 is 28 minutes after the opening alarm, so it opens a second episode.
    assert false_alarm_episodes([T("15:00"), T("15:14"), T("15:28")]) == 2
    assert false_alarm_episodes([T("15:00"), T("15:15")]) == 1           # 15 minutes: inclusive
    assert false_alarm_episodes([]) == 0


# ---------------------------------------------------------------- 12. first onset

def test_12_storms_carry_first_onset_and_alarms_are_scored_against_both():
    rng = np.random.default_rng(0)
    rets = rng.normal(0, 1e-4, 3000)
    rets[2000:2030] = -10e-4
    feat = pair_features(_toy_spot(150 * np.cumprod(1 + rets)), "USDJPY")
    s = next(label_all({"USDJPY": feat}, EMPTY).itertuples())
    assert s.first_onset_utc <= s.onset_utc
    alarm = s.onset_utc + pd.Timedelta(minutes=3)
    row = per_storm_row(s, alarm, feat["mid"])
    assert row["minutes"] == 3
    assert row["minutes_first_onset"] == int((alarm - s.first_onset_utc) / pd.Timedelta(minutes=1))
    assert row["move_ahead_pct_first_onset"] is not None


# ---------------------------------------------------------------- 13. drawdown: see test_exposure.py

# ---------------------------------------------------------------- 14. coverage

def test_14_no_one_minute_return_across_a_missing_minute():
    f = toy([0] * 10)
    spot = _toy_spot(np.linspace(150, 151, 10))
    spot = spot.drop(index=5)                      # minute 5 missing: 4 -> 6 is a 2-minute gap
    feat = pair_features(spot, "USDJPY")
    assert np.isnan(feat["ret_bp"].iloc[5]) and not np.isnan(feat["ret_bp"].iloc[6])
    # the detector's m-minute windows need exactly m clock minutes too
    f = f.drop(index=f.index[5]).assign(sd_24h=1.0)
    rf = risk_frame(f, {**CFG, "move_windows": [1]})
    assert np.isnan(rf["strength"].iloc[5])


def test_14_label_window_needs_13_of_15_minutes_observed():
    rng = np.random.default_rng(0)
    rets = rng.normal(0, 1e-4, 3000)
    rets[2000:2030] = -10e-4
    spot = _toy_spot(150 * np.cumprod(1 + rets))
    feat = pair_features(spot, "USDJPY")
    w = window_moves(feat)
    end = feat.index[2015]
    assert w.loc[end, "observed"] == 15 and w.loc[end, "trigger"]
    sparse = pair_features(spot.drop(index=range(2005, 2008)), "USDJPY")   # 3 of 15 missing
    ws = window_moves(sparse)
    assert ws.loc[end, "observed"] == 12 and not ws.loc[end, "trigger"]


def test_14_observed_minutes_count_each_pairs_own_bars():
    a = toy([0] * 10)
    b = toy([0] * 6)
    start, end = a.index[0], a.index[-1] + pd.Timedelta(minutes=1)
    assert observed_minutes({"A": a, "B": b}, start, end) == 16          # not 2 x 10


# ---------------------------------------------------------------- 15. provenance

def test_15_export_refuses_metrics_whose_provenance_does_not_match(tmp_path):
    processed = write_spot(tmp_path / "processed")
    cal = tmp_path / "calendar.csv"
    cal.write_text("time_utc,event,region,source_url,verified\n")
    (processed / "detector_config.json").write_text(json.dumps({"config": CFG}))
    v1 = {"storms": 1, "caught": 1, "median_move_ahead_pct": 60.0, "false_alarms_per_day": 0.5}
    metrics = {"split": "test", "methods": {"v1": v1}, "provenance": provenance(processed, cal,
                                                                                processed / "detector_config.json")}
    (processed / "metrics.json").write_text(json.dumps(metrics))
    assert export.load_index_metrics(processed, cal)["caught"] == 1
    cal.write_text("time_utc,event,region,source_url,verified\n2026-07-02T12:30:00Z,X,US,https://example.org,yes\n")
    with pytest.raises(export.StaleMetrics, match="calendar"):
        export.load_index_metrics(processed, cal)
    del metrics["provenance"]
    (processed / "metrics.json").write_text(json.dumps(metrics))
    with pytest.raises(export.StaleMetrics, match="no provenance"):
        export.load_index_metrics(processed, cal)
