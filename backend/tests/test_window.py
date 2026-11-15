"""No replay opens inside a danger alarm: the prepared ship may not hold cargo the policy cut.

The 30 July USDJPY bundle once began at 10:29, eleven minutes into a 10:18 alarm that the
window had cut off, so the first frame showed state STORM over a ship at full size until the
next alarm at 13:37. Every series here is synthetic."""
import numpy as np
import pandas as pd
import pytest

from storm import export
from storm.detector import run_detector
from storm.exposure import cut_since, leg_exposure
from storm.features import pair_features
from storm.labels import label_all
from storm.validate import validate_bundle
from tests.test_detector import CFG, EMPTY
from tests.test_labels import _toy_spot

T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731


def _ev(kind, t):
    return {"type": kind, "time": T(t)}


def test_cut_since_runs_the_policy_rule_over_the_events_before_a_time():
    events = [_ev("watch", "2026-07-30 09:00"), _ev("alarm", "2026-07-30 10:18"), _ev("squall", "2026-07-30 10:30"),
              _ev("alarm", "2026-07-30 10:40"), _ev("all_clear", "2026-07-30 11:44"), _ev("alarm", "2026-07-30 13:37")]
    assert cut_since(events, T("2026-07-30 10:18")) is None            # the alarm bar itself is in the window
    assert cut_since(events, T("2026-07-30 10:29")) == T("2026-07-30 10:18")
    assert cut_since(events, T("2026-07-30 11:44")) == T("2026-07-30 10:18")
    assert cut_since(events, T("2026-07-30 11:45")) is None            # restored after the all-clear
    assert cut_since(events, T("2026-07-30 13:38")) == T("2026-07-30 13:37")
    assert cut_since([_ev("all_clear", "2026-07-30 09:00")], T("2026-07-30 12:00")) is None   # nothing to restore
    assert cut_since([_ev("squall", "2026-07-30 10:00")], T("2026-07-30 12:00")) is None      # a squall never cuts


def _early_alarm_bundle():
    """A 300 bp fall, and 5 minutes before its 3-hour window opens a 36 bp drop: the first
    alarm is still in force (20 calm minutes pending) at the default window's first bar."""
    rng = np.random.default_rng(0)
    rets = rng.normal(0, 1e-4, 3000)
    rets[2000:2030] = -10e-4

    def labelled(r):
        feat = pair_features(_toy_spot(150 * np.cumprod(1 + r)), "USDJPY").assign(comove=0)
        return feat, label_all({"USDJPY": feat}, EMPTY)

    feat, storms = labelled(rets)
    onset = feat.index.get_loc(next(storms.itertuples()).onset_utc)
    rets[onset - 185:onset - 182] = -12e-4
    feat, storms = labelled(rets)
    st = next(storms.itertuples())
    assert len(storms) == 1                                    # one storm: the drop is its first onset
    ctx = export.Context({"USDJPY": feat}, storms, EMPTY, CFG)
    res = run_detector(feat, EMPTY, CFG, exposure=leg_exposure("USDJPY"))
    return ctx, st, feat, res


def test_the_default_window_widens_to_show_an_alarm_that_began_before_it():
    ctx, st, feat, res = _early_alarm_bundle()
    plain, end = export.default_window(feat, st)                       # onset - 3 h, as before
    assert cut_since(res.events, plain) is not None                    # the toy really opens inside an alarm
    with pytest.raises(ValueError, match="inside the danger alarm"):
        export.build_bundle(ctx, st, plain, end)                       # the old window is refused

    start, end2 = export.storm_window(ctx, st)
    since = cut_since(res.events, plain)
    assert end2 == end and start < since and since - start <= export.WINDOW_LEAD + pd.Timedelta(minutes=1)
    assert cut_since(res.events, start) is None

    b, _ = export.build_bundle(ctx, st, start, end2)
    assert validate_bundle(b) == []
    prep, unprep = b["series"]["prepared_equity"], b["series"]["unprepared_equity"]
    assert prep[0] == unprep[0] == b["ships"]["prepared"]["start_equity_usd"]   # both start at full size
    assert b["series"]["state"][0] == 0                                          # on calm water

    alarm = next(e for e in b["events"] if e["type"] == "alarm")
    ship = b["ships"]["prepared"]
    assert alarm["i"] == int((since - start) / pd.Timedelta(minutes=1))
    assert ship["cut_i"] == alarm["i"] + 1                                       # fills at the next bar
    clear = next(e for e in b["events"] if e["type"] == "all_clear")
    assert ship["restore_i"] == clear["i"] + 1 and ship["restore_i"] < b["storm"]["onset_i"]
    assert b["storm"]["first_onset_i"] <= b["storm"]["onset_i"]


def test_no_frame_shows_an_active_alarm_over_a_ship_the_policy_would_have_cut():
    """The rule, frame by frame: from the frame after each danger alarm to its all-clear, the
    latest cut or restore the prepared ship has made is a cut (the alarm's own frame is the
    one-bar signal lag: the fill is at the next bar's open)."""
    ctx, st, feat, res = _early_alarm_bundle()
    b, _ = export.build_bundle(ctx, st, *export.storm_window(ctx, st))
    events = b["events"]
    alarms = [e["i"] for e in events if e["type"] == "alarm"]
    assert alarms
    checked = 0
    for a in alarms:
        closes = [e["i"] for e in events if e["type"] == "all_clear" and e["i"] > a]
        for i in range(a + 1, (closes[0] if closes else b["n"] - 1) + 1):
            held = [e["type"] for e in events if e["type"] in ("cut", "restore") and e["i"] <= i]
            assert held and held[-1] == "cut", (a, i)
            checked += 1
    assert checked > 20


def test_the_report_states_the_linked_alarm_not_an_earlier_moves():
    """The widened window now holds the earlier alarm too: the report's first alarm must be the
    one the evaluator links to the storm, not the earlier drop's (which is 'before the move')."""
    ctx, st, feat, res = _early_alarm_bundle()
    b, _ = export.build_bundle(ctx, st, *export.storm_window(ctx, st))
    alarms = [e for e in b["events"] if e["type"] == "alarm"]
    assert len(alarms) >= 2 and alarms[0]["move_ahead_pct"] is None            # the earlier, unlinked alarm
    facts = export.report_facts(b)
    shown = [e for e in facts["alarm_events"] if e["type"] == "alarm"]
    assert shown and shown[0]["minutes_from_onset"] == b["storm"]["alarm_minutes"]
    assert shown[0]["move_ahead_pct"] == b["storm"]["move_ahead_pct"]
