import numpy as np
import pandas as pd

from storm.detector import DEFAULT_CONFIG, STORM, WATCH, load_calendar, risk_frame, run_detector

EMPTY = pd.DataFrame(columns=["time_utc", "event", "region", "source_url", "verified"])
CFG = {**DEFAULT_CONFIG, "move_windows": [1, 3, 5], "strength_full": 10.0, "w_comove": 0.0,
       "storm_on": 0.8, "squall_on": 0.75, "storm_minutes": 2, "calm_off": 0.25, "calm_minutes": 20}


def toy(rets_bp, start="2026-07-30 10:00"):
    """Features with sd_24h = 1 bp, so a move of x bp over m minutes has strength x / sqrt(m)."""
    rets = np.asarray(rets_bp, dtype=float)
    mid = 100.0 * np.cumprod(1.0 + rets / 1e4)
    idx = pd.date_range(start, periods=len(mid), freq="min", tz="UTC")
    return pd.DataFrame({"mid": mid, "sd_24h": 1.0, "comove": 0}, index=idx)


def test_strength_is_largest_normalised_move():
    f = toy([0] * 10 + [-6, -6, 0, 0, 0, 0])
    rf = risk_frame(f, CFG)
    # minute 11: 1-min move 6 sd; 3-min move 12 / sqrt(3) = 6.93 sd, down
    assert abs(rf["strength"].iloc[11] - 12 / np.sqrt(3)) < 0.01
    assert rf["direction"].iloc[11] == -1
    assert abs(rf["risk"].iloc[11] - 0.69) < 0.01
    assert np.isnan(rf["strength"].iloc[0])


def test_window_across_gap_is_undefined():
    f = toy([0] * 12)
    f.index = f.index.where(f.index < f.index[6], f.index + pd.Timedelta(minutes=30))
    rf = risk_frame(f, {**CFG, "move_windows": [3]})
    assert rf["strength"].iloc[6:9].isna().all() and not np.isnan(rf["strength"].iloc[9])


def test_detection_is_direction_agnostic_alerts_are_not():
    f = toy([0] * 30 + [-10, -10] + [0] * 40)
    alarms = {x: run_detector(f, EMPTY, CFG, exposure=x).storm_alarms() for x in (1, -1, 0)}
    assert alarms[1] == alarms[-1] == alarms[0] and len(alarms[0]) == 1
    long_ = [e["type"] for e in run_detector(f, EMPTY, CFG, exposure=1).events]
    short = [e["type"] for e in run_detector(f, EMPTY, CFG, exposure=-1).events]
    flat = [e["type"] for e in run_detector(f, EMPTY, CFG, exposure=0).events]
    assert long_ == ["squall", "alarm", "all_clear"]      # a drop is danger for a long book
    assert short == ["fair_wind", "all_clear"]            # and a fair wind for a short one
    assert flat == ["all_clear"]                          # no book, no alerts; state still storms


def test_storm_level_needs_k_minutes_and_state_holds_until_all_clear():
    f = toy([0] * 30 + [-10, -10] + [0] * 40)
    res = run_detector(f, EMPTY, CFG, exposure=1)
    ev = {e["type"]: f.index.get_loc(e["time"]) for e in res.events}
    assert ev["squall"] == 30 and ev["alarm"] == 31        # k = 2: the second storm minute
    risk = res.frame["risk"].to_numpy()
    clear = ev["all_clear"]
    assert (risk[clear - 19:clear + 1] < CFG["calm_off"]).all() and risk[clear - 20] >= CFG["calm_off"]
    state = res.frame["state"].to_numpy()
    assert (state[31:clear] == STORM).all() and state[30] == 0 and state[clear] == 0


def test_single_spike_is_a_squall_not_a_storm():
    f = toy([0] * 30 + [-8.5] + [0] * 40)
    res = run_detector(f, EMPTY, CFG, exposure=1)
    assert [e["type"] for e in res.events] == ["squall", "all_clear"]
    assert res.storm_alarms() == [] and (res.frame["state"] != STORM).all()


def test_watch_before_calendar_release(tmp_path):
    cal = tmp_path / "calendar.csv"
    cal.write_text("time_utc,event,region,source_url,verified\n2026-07-30 10:40,US CPI,US,https://example.org,true\n")
    res = run_detector(toy([0] * 60), load_calendar(cal), CFG)
    watch = res.frame.index[res.frame["state"] == WATCH]
    assert watch[0] == pd.Timestamp("2026-07-30 10:10", tz="UTC")
    assert watch[-1] == pd.Timestamp("2026-07-30 10:39", tz="UTC")
    assert [e["type"] for e in res.events] == ["watch"]
