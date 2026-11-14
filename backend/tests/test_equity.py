"""storm.equity on synthetic Yahoo-shaped bars (no real prices, no network)."""
import numpy as np
import pandas as pd
import pytest

from storm import equity as eq
from storm.detector import DEFAULT_CONFIG, risk_frame
from storm.export import attach_report
from storm.features import bar_features
from storm.validate import validate_bundle

ET = "America/New_York"


def _session_index(days=range(9, 14)) -> pd.DatetimeIndex:
    """Every minute of 04:00-20:00 ET on the given November 2026 days, in UTC."""
    parts = [pd.date_range(f"2026-11-{d:02d} 04:00", f"2026-11-{d:02d} 19:59", freq="min", tz=ET)
             for d in days]
    return parts[0].append(parts[1:]).tz_convert("UTC")


def _raw(idx: pd.DatetimeIndex, seed: int, start: float = 100.0, gap_jump: float = 0.0,
         moves: tuple[tuple[str, float], ...] = (), sd_bp: float = 5.0) -> pd.DataFrame:
    """Yahoo-shaped frame: a random walk, `gap_jump` (log) added at the first bar of each
    session after the first, and each (UTC time, move_bp) spread over 3 minutes."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0, sd_bp, len(idx)) / 1e4
    sess = eq.session_ids(idx)
    r[1:][np.diff(sess) != 0] += gap_jump
    for when, move in moves:
        k = idx.get_loc(pd.Timestamp(when, tz="UTC"))
        r[k:k + 3] += move / 3 / 1e4
    close = start * np.exp(np.cumsum(r))
    open_ = np.concatenate([[close[0]], close[:-1]])
    return pd.DataFrame({"timestamp": idx, "open": open_, "high": np.maximum(open_, close),
                         "low": np.minimum(open_, close), "close": close, "volume": 0})


def test_session_ids_cover_extended_hours_only():
    t = pd.DatetimeIndex(["2026-11-11 08:59", "2026-11-11 09:00", "2026-11-12 00:59",
                          "2026-11-12 01:00", "2026-11-14 15:00"], tz="UTC")
    assert eq.session_ids(t).tolist() == [-1, 20261111, 20261111, -1, -1]


def test_no_return_is_ever_computed_across_a_market_gap():
    idx = _session_index()
    calm = bar_features(eq.bars_from_raw(_raw(idx, 1, gap_jump=0.0), "X"))
    gapped = bar_features(eq.bars_from_raw(_raw(idx, 1, gap_jump=np.log(1.2)), "X"))
    first = np.r_[True, np.diff(gapped["session"].to_numpy()) != 0]
    assert gapped["ret_bp"][first].isna().all()
    # A 20% overnight gap changes nothing: every return, volatility and detector strength
    # is the same as with no gap at all.
    for col in ("ret_bp", "sd_24h", "z", "vol_ratio", "jump"):
        pd.testing.assert_series_equal(calm[col], gapped[col], rtol=1e-9, check_names=False)
    rc, rg = risk_frame(calm.assign(comove=0)), risk_frame(gapped.assign(comove=0))
    np.testing.assert_allclose(rc["strength"], rg["strength"], rtol=1e-9)
    assert gapped["jump"].sum() == 0


def test_session_change_breaks_returns_even_without_a_clock_gap():
    idx = pd.date_range("2026-11-11 12:00", periods=10, freq="min", tz="UTC")
    bars = pd.DataFrame({"open": 100.0, "high": 100.0, "low": 100.0,
                         "mid": [100.0] * 5 + [150.0] * 5, "session": [1] * 5 + [2] * 5}, index=idx)
    f = bar_features(bars)
    assert np.isnan(f["ret_bp"].iloc[5])
    f["sd_24h"], f["comove"] = 1.0, 0
    s = risk_frame(f)["strength"]
    assert np.isnan(s.iloc[5])               # every window ending there crosses the change
    assert s.drop(s.index[[0, 5]]).eq(0).all()   # the 50% jump is never measured


def test_bad_print_is_dropped_but_a_real_step_is_kept():
    idx = _session_index([10])
    raw = _raw(idx, 2, sd_bp=1.0)
    k = 300
    raw.loc[k, ["close", "high"]] = raw.loc[k - 1, "close"] * 1.065      # spike, next open back
    raw.loc[600:, ["open", "high", "low", "close"]] *= 0.9                # a real -10% step
    bars = eq.bars_from_raw(raw, "X")
    assert bars.attrs["dropped"] == [idx[k]]
    assert idx[600] in bars.index and idx[k] not in bars.index


def test_stock_book_margin_call_and_cut():
    book = {**eq.BOOK}
    # $1m equity, $4m long, 15% maintenance: the call comes once the price is below 3 / 3.4 of entry
    hold = eq.simulate_stock(np.array([100.0, 88.3, 88.2, 80.0]), book)
    assert hold.margin_call_i == 2 and hold.equity[3] == hold.equity[2]
    prepared = eq.simulate_stock(np.array([100.0, 95.0, 88.2, 80.0]), book, [(1, "NVDA", "cut")])
    assert prepared.margin_call_i is None and prepared.cut_i == 1
    assert prepared.equity[-1] == pytest.approx(1_000_000 - 40_000 * 5 - 10_000 * 15)


def _run(tmp_moves=(("2026-11-11 21:56", -900.0), ("2026-11-12 14:30", -400.0))) -> eq.EquityRun:
    idx = _session_index()
    bars = {}
    for k, sym in enumerate(eq.SYMBOLS):
        moves = tmp_moves if sym == "NVDA" else ()
        bars[sym] = eq.bars_from_raw(_raw(idx, 10 + k, start=50.0 + 10 * k, moves=moves), sym)
    return eq.EquityRun(bars, eq.equity_features(bars), dict(DEFAULT_CONFIG))


def test_equity_bundle_validates_and_shows_the_closed_night():
    run = _run()
    bundle, summary = eq.build_bundle(run)
    attach_report(bundle)
    assert validate_bundle(bundle) == []
    assert bundle["source"] == "yahoo" and bundle["asset_class"] == "equity"
    assert bundle["storm"]["kind"] == "unscheduled" and "event" not in bundle["storm"]
    s = bundle["series"]
    t = pd.to_datetime([bundle["t0"] + i * 60 for i in range(bundle["n"])], unit="s", utc=True)
    closed = np.array(s["market_open"]) == 0
    assert closed.sum() == 8 * 60                      # 20:00 to 04:00 ET
    assert t[closed].min() == pd.Timestamp("2026-11-12 01:00", tz="UTC")
    mids = np.array(s["mid"])[closed]
    assert np.all(mids == mids[0])                     # flat while closed
    assert bundle["storm"]["onset_i"] == int(np.flatnonzero(t == pd.Timestamp("2026-11-11 20:59", tz="UTC"))[0])
    assert summary["alarms"], "a 9% fall in three minutes must raise the alarm"
    assert bundle["ships"]["prepared"]["cut_i"] is not None
