import pandas as pd

from storm.backtest import kind_summary, watch_before_onset
from storm.detector import CALM, STORM, WATCH


def _storm(onset, event, kind="scheduled"):
    return pd.DataFrame([{"kind": kind, "onset_utc": pd.Timestamp(onset, tz="UTC"),
                          "event_utc": pd.Timestamp(event, tz="UTC") if event else pd.NaT}]).itertuples().__next__()


def _frame(states, start="2026-08-07 12:00"):
    idx = pd.date_range(start, periods=len(states), freq="min", tz="UTC")
    return pd.DataFrame({"state": states}, index=idx)


def test_warning_is_onset_minus_first_watch_minute():
    # event 12:30, watch from 12:00; onset 12:20 -> 20 minutes of warning
    w = watch_before_onset(_storm("2026-08-07 12:20", "2026-08-07 12:30"), _frame([WATCH] * 45), 30)
    assert w == {"watch_start_utc": "2026-08-07 12:00", "watch_before_onset": True, "warning_minutes": 20}


def test_no_watch_before_onset_when_a_storm_holds_the_state():
    states = [STORM] * 20 + [WATCH] * 25
    w = watch_before_onset(_storm("2026-08-07 12:20", "2026-08-07 12:30"), _frame(states), 30)
    assert w["watch_before_onset"] is False and w["warning_minutes"] is None
    u = watch_before_onset(_storm("2026-08-07 12:20", None, "unscheduled"), _frame([CALM] * 45), 30)
    assert u["watch_before_onset"] is None


def test_combined_counts_a_watch_or_a_caught_alarm():
    rows = [
        {"storm_id": "a", "kind": "scheduled", "watch_before_onset": True, "warning_minutes": 20,
         "alarm_utc": None, "alarm_minutes": None, "move_ahead_pct": None, "caught": False, "covered": True},
        {"storm_id": "b", "kind": "unscheduled", "watch_before_onset": None, "warning_minutes": None,
         "alarm_utc": "x", "alarm_minutes": 3, "move_ahead_pct": 60.0, "caught": True, "covered": True},
        {"storm_id": "c", "kind": "unscheduled", "watch_before_onset": None, "warning_minutes": None,
         "alarm_utc": "y", "alarm_minutes": 9, "move_ahead_pct": 10.0, "caught": False, "covered": False},
    ]
    k = kind_summary(rows)
    assert k["combined"] == {"storms": 3, "covered": 2, "covered_pct": 66.7}
    assert k["scheduled"]["watched_before_onset"] == 1 and k["scheduled"]["median_warning_minutes"] == 20
    assert k["unscheduled"]["v1"]["storms"] == 2 and k["unscheduled"]["v1"]["caught"] == 1
