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


def _cal(tmp_path, *rows):
    cal = tmp_path / "calendar.csv"
    cal.write_text("time_utc,event,region,source_url,verified\n"
                   + "".join(f"{t},{name},US,https://example.org,yes\n" for t, name in rows))
    return load_calendar(cal)


def test_watch_window_runs_30_before_to_15_after_the_event(tmp_path):
    res = run_detector(toy([0] * 90), _cal(tmp_path, ("2026-07-30T10:40:00Z", "US CPI")), CFG)
    watch = res.frame.index[res.frame["state"] == WATCH]
    assert watch[0] == pd.Timestamp("2026-07-30 10:10", tz="UTC")
    assert watch[-1] == pd.Timestamp("2026-07-30 10:54", tz="UTC")
    assert len(watch) == 45
    assert [e["type"] for e in res.events] == ["watch"]
    ev = res.events[0]
    assert ev["time"] == watch[0] and ev["at"] == pd.Timestamp("2026-07-30 10:40", tz="UTC")
    assert ev["event"] == "US CPI"


def test_storm_overrides_watch_and_watch_resumes_after_all_clear(tmp_path):
    # Storm at 10:20 (minutes 20-21), all-clear 20 calm minutes later; event at 10:40.
    f = toy([0] * 20 + [-10, -10] + [0] * 70)
    res = run_detector(f, _cal(tmp_path, ("2026-07-30T10:40:00Z", "US CPI")), CFG, exposure=1)
    st = res.frame["state"]
    t = lambda hm: pd.Timestamp(f"2026-07-30 {hm}", tz="UTC")
    minute = pd.Timedelta(minutes=1)
    assert (st.loc[t("10:10"):t("10:20")] == WATCH).all()
    clear = next(e["time"] for e in res.events if e["type"] == "all_clear")
    assert (st.loc[t("10:21"):clear - minute] == STORM).all()
    assert clear < t("10:55")
    assert (st.loc[clear:t("10:54")] == WATCH).all() and st.loc[t("10:55")] == 0
    assert [e["type"] for e in res.events].count("watch") == 1   # one watch per calendar event


def test_watch_hidden_at_its_start_is_announced_when_first_shown(tmp_path):
    # A storm from 10:05 covers the window's start (10:10); the watch event fires on its first
    # visible minute, after the all-clear.
    f = toy([0] * 5 + [-10, -10] + [0] * 80)
    res = run_detector(f, _cal(tmp_path, ("2026-07-30T10:40:00Z", "US CPI")), CFG, exposure=1)
    first = res.frame.index[res.frame["state"] == WATCH][0]
    clear = next(e["time"] for e in res.events if e["type"] == "all_clear")
    watch = [e for e in res.events if e["type"] == "watch"]
    assert first == clear and len(watch) == 1 and watch[0]["time"] == first
