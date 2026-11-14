import pandas as pd
import pytest

from storm.evaluate import for_display
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
    assert k["combined"] == {"storms": 3, "covered": 2, "covered_pct": pytest.approx(200 / 3)}   # unrounded
    assert k["scheduled"]["watched_before_onset"] == 1 and k["scheduled"]["median_warning_minutes"] == 20
    assert k["unscheduled"]["v1"]["storms"] == 2 and k["unscheduled"]["v1"]["caught"] == 1


def test_quiet_watches_counted_per_release():
    from storm.backtest import watch_outcomes, watch_line
    cal = pd.DataFrame({"time_utc": pd.to_datetime(["2026-08-07 12:30", "2026-08-12 12:30", "2026-08-13 12:30",
                                                    "2026-09-02 12:30"], utc=True),
                        "event": ["NFP", "CPI", "PPI", "outside"]})
    storms = pd.DataFrame({"storm_id": ["usdjpy-a", "eurusd-a", "usdjpy-b", "usdjpy-c"],
                           "onset_utc": pd.to_datetime(["2026-08-07 12:20", "2026-08-07 12:29",
                                                        "2026-08-12 12:45",    # window ends 12:45: outside
                                                        "2026-08-13 12:00"],   # window starts 12:00: inside
                                                       utc=True)})
    w = watch_outcomes(cal, storms, 30, 15, pd.Timestamp("2026-08-01", tz="UTC"), pd.Timestamp("2026-09-01", tz="UTC"))
    assert (w["releases"], w["with_storm"], w["quiet"]) == (3, 2, 1)
    assert w["watch_precision"] == pytest.approx(2 / 3) and w["quiet_share_pct"] == pytest.approx(100 / 3)
    assert for_display(w)["watch_precision"] == 0.67 and for_display(w)["quiet_share_pct"] == 33.3
    assert w["quiet_releases"] == ["CPI (2026-08-12 12:30 UTC)"]
    assert w["per_release"][0]["storms"] == ["usdjpy-a", "eurusd-a"]
    assert watch_line(w, "August") == "August: 3 scheduled releases, 2 produced a storm, 1 were quiet (watch precision 0.67)"
    none = watch_outcomes(cal.iloc[:0], storms, 30, 15, pd.Timestamp("2026-08-01", tz="UTC"),
                          pd.Timestamp("2026-09-01", tz="UTC"))
    assert none["releases"] == 0 and none["watch_precision"] is None


def test_index_metrics_carry_the_evidence_card_figures():
    from storm.backtest import index_metrics
    from storm.validate import validate_index
    v1 = {"storms": 6, "alarmed": 6, "caught": 4, "median_move_ahead_pct": 57.4,
          "median_minutes_to_alarm": 3.5, "false_alarms_per_day": 0.56, "false_alarm_episodes_per_day": 0.37}
    m = {"split": "test: August 2026", "methods": {"v1": v1}, "watch_precision": 0.29,
         "policy": {"prepared": {"max_drawdown_usd": 191021, "max_drawdown_pct": 17.3},
                    "unprepared": {"max_drawdown_usd": 226151, "max_drawdown_pct": 20.6}}}
    ix = index_metrics(m)
    assert ix["alarmed"] == 6 and ix["median_minutes_to_alarm"] == 3.5
    assert ix["prepared_max_drawdown_pct"] == 17.3 and ix["unprepared_max_drawdown_usd"] == 226151
    assert ix["false_alarm_episodes_per_day"] == 0.37 and ix["watch_precision"] == 0.29
    assert validate_index({"schema_version": 1, "storms": [], "metrics": ix}) == []
