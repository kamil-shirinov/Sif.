import numpy as np
import pandas as pd

from storm.detector import STORM, WATCH, load_calendar, run_detector


def _feat(risk_like_z):
    # With vol_ratio = 1 and comove = 0, risk = 0.12 * |z|.
    z = np.asarray(risk_like_z, dtype=float) / 0.12
    idx = pd.date_range("2026-07-30 10:00", periods=len(z), freq="min", tz="UTC")
    return pd.DataFrame({"z": z, "vol_ratio": 1.0, "comove": 0}, index=idx)


EMPTY = pd.DataFrame(columns=["time_utc", "event", "region", "source_url", "verified"])


def test_storm_needs_two_minutes_and_twenty_calm():
    risk = [0.1, 0.8, 0.1, 0.8, 0.9, 0.5] + [0.1] * 19 + [0.1, 0.1]
    out, events = run_detector(_feat(risk), EMPTY)
    state = out["state"].tolist()
    assert state[:4] == [0, 0, 0, 0]
    assert state[4] == STORM
    assert all(s == STORM for s in state[4:24])
    assert state[25] == 0
    assert [(e["type"], out.index.get_loc(e["time"])) for e in events] == [("alarm", 4), ("all_clear", 25)]


def test_watch_before_calendar_release(tmp_path):
    cal = tmp_path / "calendar.csv"
    cal.write_text("time_utc,event,region,source_url,verified\n2026-07-30 10:40,US CPI,US,https://example.org,true\n")
    out, events = run_detector(_feat([0.1] * 60), load_calendar(cal))
    watch = out.index[out["state"] == WATCH]
    assert watch[0] == pd.Timestamp("2026-07-30 10:10", tz="UTC")
    assert watch[-1] == pd.Timestamp("2026-07-30 10:39", tz="UTC")
    (ev,) = events
    assert ev["type"] == "watch" and ev["at"] == pd.Timestamp("2026-07-30 10:40", tz="UTC")


def test_empty_calendar_does_not_crash(tmp_path):
    cal = tmp_path / "calendar.csv"
    cal.write_text("time_utc,event,region,source_url,verified\n")
    assert load_calendar(cal).empty
    assert load_calendar(tmp_path / "missing.csv").empty
    out, events = run_detector(_feat([0.1] * 5), load_calendar(cal))
    assert (out["state"] == 0).all() and events == []
