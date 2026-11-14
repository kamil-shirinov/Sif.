import numpy as np
import pandas as pd
import pytest

from storm.detector import run_detector
from storm.exposure import (
    POLICY_BOOK, book_for, max_drawdown, policy_actions, policy_backtest, ships, simulate_book, stress_test,
)
from tests.test_detector import CFG, EMPTY, toy

JPY = book_for("USDJPY")


def test_book_is_synthetic_and_split_equally():
    assert POLICY_BOOK["synthetic"] is True
    assert [leg["pair"] for leg in POLICY_BOOK["legs"]] == ["USDJPY", "EURUSD", "USDSGD"]
    assert sum(leg["usd_notional"] for leg in POLICY_BOOK["legs"]) == pytest.approx(20e6)


def test_equity_marks_to_market():
    mid = np.array([100.0, 101.0, 99.0])
    p = simulate_book({"USDJPY": mid}, JPY)
    assert p.equity == pytest.approx(1e6 + 20e6 * (1 - 100.0 / mid))
    assert p.margin_call_i is None


def test_short_eur_leg_is_long_usd():
    mid = np.array([1.15, 1.16, 1.14])
    p = simulate_book({"EURUSD": mid}, book_for("EURUSD"))
    assert p.equity == pytest.approx(1e6 + 20e6 * (1 - mid / 1.15))
    assert p.qty["EURUSD"][0] == pytest.approx(-20e6 / 1.15)


def test_margin_call_closes_and_freezes():
    # 1M equity, 20M long USD, maintenance 500k: equity < 500k once S < 100/1.025 = 97.561.
    mid = np.array([100.0, 99.0, 98.0, 97.6, 97.5, 95.0, 90.0])
    p = simulate_book({"USDJPY": mid}, JPY)
    assert p.margin_call_i == 4
    closed = 1e6 + 20e6 * (1 - 100.0 / 97.5)
    assert p.equity[4:] == pytest.approx([closed] * 3)
    assert p.qty["USDJPY"][4:] == pytest.approx([0, 0, 0])


def test_cut_avoids_margin_call_and_restore_reopens():
    # Mid-only data: bar i opens at bar i-1's close with no spread. The cut is scheduled for
    # frame 2, so it fills at frame 2's open = 99.5 (frame 1's close).
    mid = np.array([100.0, 99.5, 99.0, 97.5, 96.0, 95.0, 95.0, 95.0])
    s = ships({"USDJPY": mid}, JPY, [(2, "USDJPY", "cut"), (7, "USDJPY", "restore")])
    assert s["unprepared"].margin_call_i == 3
    prep = s["prepared"]
    assert prep.margin_call_i is None and prep.cut_i == 2 and prep.cut_fraction == 0.75
    # After the cut: 6M USD and -2,000M + 15M x 99.5 = -507.5M JPY (realised loss stays in JPY).
    assert prep.equity[5] == pytest.approx(6e6 - 507.5e6 / 95.0)
    assert prep.qty["USDJPY"][2:7] == pytest.approx([5e6] * 5)
    assert prep.restore_i == 7 and prep.qty["USDJPY"][7] == pytest.approx(20e6)
    assert prep.equity[7] == pytest.approx(prep.equity[6])     # trading at mid moves no equity
    assert [f["price"] for f in prep.fills] == [99.5, 95.0] and prep.spread_cost_usd == 0


def test_policy_cuts_at_storm_alarm_and_restores_after_all_clear():
    f = toy([0] * 30 + [-10] * 4 + [0] * 40)        # the fall goes on after the alarm at minute 31
    res = run_detector(f, EMPTY, CFG, exposure=1)
    i_of = {e["type"]: f.index.get_loc(e["time"]) for e in res.events}
    actions = policy_actions({"USDJPY": res.events}, f.index.get_loc)
    # A signal at bar t's close is scheduled for bar t + 1.
    assert actions == [(i_of["alarm"] + 1, "USDJPY", "cut"), (i_of["all_clear"] + 1, "USDJPY", "restore")]
    assert i_of["all_clear"] - i_of["alarm"] >= CFG["calm_minutes"]

    s = ships({"USDJPY": f["mid"].to_numpy()}, JPY, actions)
    q = s["prepared"].qty["USDJPY"]
    assert i_of["alarm"] == 31
    assert s["prepared"].cut_i == 32 and s["prepared"].restore_i == i_of["all_clear"] + 1
    assert q[31] == pytest.approx(20e6) and q[32] == pytest.approx(5e6)
    assert q[i_of["all_clear"]] == pytest.approx(5e6) and q[i_of["all_clear"] + 1] == pytest.approx(20e6)
    assert (s["unprepared"].qty["USDJPY"] == 20e6).all()
    assert s["prepared"].equity[-1] > s["unprepared"].equity[-1]


def test_squall_and_fair_wind_do_not_trade():
    spike = run_detector(toy([0] * 30 + [-8.5] + [0] * 40), EMPTY, CFG, exposure=1)
    rise = run_detector(toy([0] * 30 + [10, 10] + [0] * 40), EMPTY, CFG, exposure=1)
    assert "squall" in [e["type"] for e in spike.events]
    assert "fair_wind" in [e["type"] for e in rise.events]
    assert policy_actions({"USDJPY": spike.events, "USDSGD": rise.events}, lambda t: 0) == []


def test_policy_backtest_on_toy_book():
    feats = {}
    for k, p in enumerate(["USDJPY", "EURUSD", "USDSGD"]):
        f = toy([0] * 30 + ([-10] * 4 if p != "EURUSD" else [10] * 4) + [0] * 40)
        f["mid"] *= {"USDJPY": 1.6, "EURUSD": 0.0115, "USDSGD": 0.0129}[p]
        feats[p] = f
    out = policy_backtest(feats, CFG, feats["USDJPY"].index[0], feats["USDJPY"].index[-1] + pd.Timedelta(minutes=1), EMPTY)
    assert out["book"]["synthetic"] is True
    assert out["alerts"]["danger_alarms"] == 3                   # USD falls: every leg is hit
    assert out["prepared"]["cuts"] == 3 and out["prepared"]["restores"] == 3
    assert out["prepared"]["max_drawdown_usd"] < out["unprepared"]["max_drawdown_usd"]


def test_max_drawdown():
    assert max_drawdown(np.array([100.0, 120.0, 90.0, 130.0, 125.0])) == pytest.approx((30.0, 25.0))


def test_max_drawdown_dollars_and_percent_are_maximised_independently():
    # 100 -> 50 is the largest % fall (50%); 1,000 -> 600 the largest $ fall (400, only 40%).
    assert max_drawdown(np.array([100.0, 50.0, 1000.0, 600.0])) == pytest.approx((400.0, 50.0))


def test_stress_test_signs_and_margin_call():
    t = pd.Timestamp("2026-07-30 13:29", tz="UTC")
    mid = pd.Series([160.0, 162.0], index=[t - pd.Timedelta(minutes=2), t - pd.Timedelta(minutes=1)])
    storms = pd.DataFrame([
        {"pair": "USDJPY", "onset_utc": t, "move_bp": -290.4, "usd_move_bp": -290.4},
        {"pair": "EURUSD", "onset_utc": t, "move_bp": 50.0, "usd_move_bp": -49.8},
    ])
    out = stress_test(storms, mid, JPY)
    assert out[0]["margin_call"] is True
    assert out[0]["pnl_usd"] == round(20e6 * (1 - 1 / (1 - 0.02904)))
    assert out[1]["pnl_usd"] < 0 and out[1]["margin_call"] is False
    assert "applied as USD" in out[1]["scenario"]
