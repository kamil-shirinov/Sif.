import pandas as pd
import pytest

from storm.evaluate import link_alarm, move_ahead_pct, score

T = lambda s: pd.Timestamp(f"2026-08-07 {s}", tz="UTC")  # noqa: E731


def _storm():
    return pd.DataFrame([{"storm_id": "usdjpy-x", "pair": "USDJPY", "onset_utc": T("12:20"),
                          "trough_utc": T("12:35"), "end_utc": T("12:46"),
                          "onset_mid": 100.0, "trough_mid": 99.0}])


def _mid():
    idx = pd.date_range(T("10:00"), T("16:00"), freq="min")
    s = pd.Series(100.0, index=idx)
    s[T("12:30")] = 99.4      # 40% of the fall still ahead at 12:30
    s[T("12:25")] = 99.8      # 80% at 12:25
    return s


def test_move_ahead_share():
    st = next(_storm().itertuples())
    mid = _mid()
    assert move_ahead_pct(T("12:25"), st, mid) == pytest.approx(80.0)
    assert move_ahead_pct(T("12:10"), st, mid) == 100.0      # before onset
    assert move_ahead_pct(T("12:40"), st, mid) == 0.0        # after the trough


def test_alarm_cleared_before_onset_is_not_credited():
    st = next(_storm().itertuples())
    assert link_alarm([(T("11:30"), T("12:00"))], st) is None
    assert link_alarm([(T("11:30"), T("12:00")), (T("12:30"), None)], st) == T("12:30")
    assert link_alarm([(T("10:00"), None)], st) is None       # older than onset - 60 min
    assert link_alarm([(T("12:25"), T("13:00"))], st) == T("12:25")


def test_score_counts_caught_and_false_alarms():
    alarms = {"USDJPY": [(T("12:25"), T("13:00")), (T("15:00"), T("15:30"))],
              "EURUSD": [(T("12:25"), T("13:00"))]}
    m = score(alarms, _storm(), {"USDJPY": _mid()}, days=2.0, squalls=3)
    assert m["storms"] == 1 and m["alarmed"] == 1 and m["caught"] == 1
    assert m["median_move_ahead_pct"] == 80.0 and m["median_minutes_to_alarm"] == 5.0
    assert m["false_alarms"] == 2          # 15:00 is past end + 60; EURUSD has no labelled storm
    assert m["false_alarms_per_day"] == 1.0 and m["squalls_per_day"] == 1.5


def test_false_alarms_count_per_pair_and_episodes_dedupe_across_pairs():
    # One USD shock at 15:00 alarms all three pairs (one within 15 min of the previous),
    # and a lone EURUSD alarm at 18:00: four false alarms, two episodes.
    alarms = {"USDJPY": [(T("15:00"), None)], "USDSGD": [(T("15:10"), None)],
              "EURUSD": [(T("15:20"), None), (T("18:00"), None)]}
    m = score(alarms, _storm(), {"USDJPY": _mid()}, days=2.0)
    assert m["false_alarms"] == 4 and m["false_alarms_per_day"] == 2.0
    assert m["false_alarm_episodes"] == 2 and m["false_alarm_episodes_per_day"] == 1.0
    m = score({"USDJPY": [(T("15:00"), None)], "EURUSD": [(T("15:16"), None)]}, _storm(),
              {"USDJPY": _mid()}, days=1.0)
    assert m["false_alarm_episodes"] == 2          # 16 minutes apart: not the same shock
