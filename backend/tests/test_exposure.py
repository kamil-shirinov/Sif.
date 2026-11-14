import numpy as np
import pandas as pd
import pytest

from storm.exposure import BOOK, simulate, ships, stress_test


def test_equity_marks_to_market():
    mid = np.array([100.0, 101.0, 99.0])
    p = simulate(mid)
    expected = BOOK["equity_usd"] + BOOK["notional_usd"] * (1 - 100.0 / mid)
    assert p.equity == pytest.approx(expected)
    assert p.margin_call_i is None


def test_margin_call_closes_and_freezes():
    # 1M equity, 20M long USD, maintenance 500k: equity < 500k once 20M*(1-100/S) < -500k,
    # i.e. S < 100/1.025 = 97.561.
    mid = np.array([100.0, 99.0, 98.0, 97.6, 97.5, 95.0, 90.0])
    p = simulate(mid)
    assert p.margin_call_i == 4
    closed = BOOK["equity_usd"] + BOOK["notional_usd"] * (1 - 100.0 / 97.5)
    assert p.equity[4] == pytest.approx(closed)
    assert p.equity[5:] == pytest.approx([closed, closed])
    assert p.position_usd[4:] == pytest.approx([0, 0, 0])


def test_cut_at_alarm_avoids_margin_call():
    mid = np.array([100.0, 99.5, 99.0, 97.5, 96.0, 95.0])
    s = ships(mid, alarm_i=1)
    assert s["unprepared"].margin_call_i == 3
    prep = s["prepared"]
    assert prep.margin_call_i is None and prep.cut_i == 1 and prep.cut_fraction == 0.75
    # After the cut the book holds 6M USD and owes 2,000M - 15M x 99.5 = 507.5M JPY,
    # marked at the last price, 95 (the cut's realised loss stays in JPY).
    assert prep.equity[-1] == pytest.approx(6e6 - 507.5e6 / 95.0)
    assert prep.position_usd[-1] == pytest.approx(5e6)
    assert prep.equity[-1] > s["unprepared"].equity[-1]


def test_stress_test_signs_and_margin_call():
    t = pd.Timestamp("2026-07-30 13:29", tz="UTC")
    mid = pd.Series([160.0, 162.0], index=[t - pd.Timedelta(minutes=2), t - pd.Timedelta(minutes=1)])
    storms = pd.DataFrame([
        {"pair": "USDJPY", "onset_utc": t, "move_bp": -290.4, "usd_move_bp": -290.4},
        {"pair": "EURUSD", "onset_utc": t, "move_bp": 50.0, "usd_move_bp": -49.8},
    ])
    out = stress_test(storms, mid)
    assert out[0]["margin_call"] is True
    assert out[0]["pnl_usd"] == round(20e6 * (1 - 1 / (1 - 0.02904)))
    assert out[1]["pnl_usd"] < 0 and out[1]["margin_call"] is False
    assert "applied as USD" in out[1]["scenario"]
