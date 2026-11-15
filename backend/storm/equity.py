"""Nvidia storm, 9 to 13 November 2026: US chip stocks from Yahoo Finance.

    python -m storm.equity             features, detector, policy and the NVDA summary
    python -m storm.equity --export    also writes web/public/bundles/nvda-2026-11-12.json
                                       and refreshes index.json
    python -m storm.equity --refresh   fetches from Yahoo again even if the parquet exists
    python -m storm.equity --export --live [--model ID --provider meta]   real report writer

Data: one-minute bars from Yahoo Finance (yfinance, prepost=True: pre-market 04:00-09:30
ET, regular 09:30-16:00 ET, after-hours 16:00-20:00 ET) for NVDA, AMD, AVGO, TSM, INTC, MU
and SMH, sessions 9 to 13 November 2026, saved once to data/processed/equity/<SYM>_1m.parquet
(gitignored). Yahoo serves one-minute bars for the last 30 days only, so the parquet is
the record; re-fetching later will fail. Yahoo has trades, not quotes: there is no bid or
ask, so spread_bp in the bundle is 0 and is not a measured spread.

Bad prints: a bar whose close is at least 2% from the previous close while the very next
bar opens back within a quarter of that jump (both neighbours within 5 minutes) is a
one-minute print the market did not trade through. It is flagged (`bad_print`), never
dropped or replaced, and handled causally (storm.features, storm.detector): at its own
minute it is visible like any bar, so it can alarm; from the next minute on, once the
reversal has been seen, it is excluded from every return, window and baseline. The
flagged bars are printed. (On 10 Nov 18:00 UTC NVDA, AVGO, INTC, MU and SMH all show one:
NVDA closes 6.5% up and the next bar opens at the old price. Left in the baselines, that
single print would hold the trailing volatility of the next 1,440 trading minutes several
times too high.) The storm's close and low are measured on unflagged bars.

Features are storm.features.bar_features on the close: the rolling windows count bars,
so volatility is measured over trading minutes only, and every bar carries its session
(the ET trading date), so no return and no detector move window ever spans the closed
market (or any hole longer than 5 minutes). Comove counts how many of the six chip names
(NVDA, AMD, AVGO, TSM, INTC, MU; SMH is the ETF holding them, so it is left out) have
|z| >= 3 the same way in the same minute: a sector storm. The detector and policy are
storm.detector v1 (data/processed/detector_config.json, tuned on SGX July FX) and policy
v1 (storm.exposure.policy_actions), unchanged. No calendar: this storm is unscheduled.

THE BOOK IS SYNTHETIC: $1,000,000 equity, long $4,000,000 of NVDA at the first price of the
replay (4x, as a portfolio-margin account allows), maintenance 15% of the open position.
Execution and margin follow storm.exposure: a signal at bar t's close fills at the open of
the next bar that traded (after a closed night, the next session's first bar); the book is
marked and tested against maintenance at each bar's open before any trade, and at its
close. A breach closes the position at that price and equity stays flat afterwards. The
prepared ship cuts 75% on a storm-level danger alarm and restores on the all-clear; the
unprepared ship holds. Yahoo has trades, not quotes, so fills are at the bar's open with no
spread (cost 0, not a measured cost), no slippage, no fees.

Stress is point in time, as for FX: only moves whose low came before the exposure snapshot
(the bar before onset). Every candidate here (each chip name's 11 Nov close to 12 Nov low)
is in the snapshot's future, so the bundle's stress menu is empty.

The storm: onset at the 11 Nov close (the last regular-session minute, 15:59 ET), trough
at the lowest one-minute low on 12 Nov up to the end of the replay; move_bp = that low /
that close - 1. The bundle covers 11 Nov 15:00 to 12 Nov 21:00 UTC. While the market is
closed (20:00 to 04:00 ET) the frames hold the last trading minute's values and
market_open is 0. Every field states market facts only, never a cause.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .detector import load_calendar, load_config, run_detector
from .evaluate import alarm_matches, move_ahead_pct
from .exposure import BookPath, cut_since, fill_frame, max_drawdown, policy_actions
from .export import (SCHEMA_VERSION, SHIP_LABELS, EVENT_ORDER, STEP_S, StaleMetrics, _event_text, _grid, _r,
                     _visible_events, attach_report, load_index_metrics, storm_alarm_fields, trade_events,
                     write_bundle, write_index)
from .features import add_comove, as_ns, bar_features
from .paths import BUNDLES_DIR, PROCESSED_DIR

SYMBOLS = ("NVDA", "AMD", "AVGO", "TSM", "INTC", "MU", "SMH")
CHIP_NAMES = ("NVDA", "AMD", "AVGO", "TSM", "INTC", "MU")
SHIP_SYMBOL = "NVDA"
EQUITY_DIR = PROCESSED_DIR / "equity"
ET = ZoneInfo("America/New_York")
FETCH_START, FETCH_END = "2026-11-09", "2026-11-14"         # yfinance: end exclusive
SESSIONS = tuple(20261100 + d for d in range(9, 14))         # ET trading dates 9..13 Nov
EXT_OPEN_MIN, REG_CLOSE_MIN, EXT_CLOSE_MIN = 4 * 60, 16 * 60, 20 * 60
SPIKE_MIN = 0.02            # a bad print jumps at least 2% ...
SPIKE_RETRACE = 0.25        # ... and the next open is back within a quarter of the jump
SPIKE_NEIGHBOUR = pd.Timedelta(minutes=5)

STORM_ID = "nvda-2026-11-12"
TITLE = "NVDA, 11 to 12 November 2026"
WINDOW_START = pd.Timestamp("2026-11-11 15:00", tz="UTC")
WINDOW_END = pd.Timestamp("2026-11-12 21:00", tz="UTC")     # inclusive
CLOSE_SESSION, LOW_SESSION = 20261111, 20261112

BOOK = {"synthetic": True, "symbol": SHIP_SYMBOL, "equity_usd": 1_000_000.0,
        "position_usd": 4_000_000.0, "maintenance_margin": 0.15, "cut_fraction": 0.75}


# ---------------------------------------------------------------- data

def fetch(symbol: str, out_dir: Path = EQUITY_DIR) -> Path:
    """One-minute bars with pre- and after-hours from Yahoo, saved as parquet (network)."""
    import yfinance as yf

    df = yf.Ticker(symbol).history(start=FETCH_START, end=FETCH_END, interval="1m",
                                   prepost=True, auto_adjust=False, actions=False)
    if df.empty:
        raise RuntimeError(f"Yahoo returned no one-minute bars for {symbol} "
                           f"({FETCH_START} .. {FETCH_END}); it keeps only the last 30 days")
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
    df.index = df.index.tz_convert("UTC")
    df = df.rename_axis("timestamp").reset_index()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{symbol}_1m.parquet"
    df.to_parquet(path, index=False)
    return path


def session_ids(index: pd.DatetimeIndex) -> np.ndarray:
    """ET trading date as yyyymmdd for minutes inside 04:00-20:00 ET on a weekday, else -1."""
    et = index.tz_convert(ET)
    minute = et.hour * 60 + et.minute
    inside = (et.weekday < 5) & (minute >= EXT_OPEN_MIN) & (minute < EXT_CLOSE_MIN)
    ids = et.year * 10000 + et.month * 100 + et.day
    return np.where(inside, ids, -1).astype("int64")


def bad_prints(df: pd.DataFrame) -> pd.DatetimeIndex:
    """Bars (open, close; sorted UTC index) whose close is a one-minute spike (module doc)."""
    prev_close, next_open = df["close"].shift(1), df["open"].shift(-1)
    jump = np.log(df["close"] / prev_close)
    back = np.log(next_open / prev_close)
    t = df.index.to_series()
    near = (t.diff() <= SPIKE_NEIGHBOUR) & (-t.diff(-1) <= SPIKE_NEIGHBOUR)
    flag = (jump.abs() >= np.log1p(SPIKE_MIN)) & (back.abs() <= SPIKE_RETRACE * jump.abs()) & near
    return df.index[flag.to_numpy()]


def bars_from_raw(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Yahoo bars -> bar_features input (open, high, low, mid = close, session, bad_print),
    9..13 Nov. Bad prints stay in, flagged (listed in bars.attrs["bad_prints"])."""
    df = raw.sort_values("timestamp").drop_duplicates("timestamp").set_index("timestamp")
    df.index = as_ns(pd.DatetimeIndex(df.index).tz_convert("UTC"))
    flagged = bad_prints(df)
    sess = session_ids(df.index)
    if (sess < 0).any():
        raise ValueError(f"{symbol}: {int((sess < 0).sum())} bars outside 04:00-20:00 ET")
    bars = pd.DataFrame({"open": df["open"], "high": df["high"], "low": df["low"], "mid": df["close"],
                         "session": sess, "bad_print": df.index.isin(flagged).astype(int)}, index=df.index)
    bars = bars[bars["session"].isin(SESSIONS)].copy()
    bars.attrs["bad_prints"] = list(bars.index[bars["bad_print"] == 1])
    return bars


def load_bars(symbols=SYMBOLS, data_dir: Path = EQUITY_DIR, refresh: bool = False) -> dict[str, pd.DataFrame]:
    out = {}
    for sym in symbols:
        path = data_dir / f"{sym}_1m.parquet"
        if refresh or not path.exists():
            print(f"fetching {sym} from Yahoo -> {fetch(sym, data_dir)}")
        out[sym] = bars_from_raw(pd.read_parquet(path), sym)
    return out


def equity_features(bars: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    feats = {s: bar_features(b) for s, b in bars.items()}
    return add_comove(feats, col="z", among=tuple(s for s in CHIP_NAMES if s in feats))


def market_open(idx: pd.DatetimeIndex, bars: pd.DataFrame) -> np.ndarray:
    """1 inside 04:00-20:00 ET on a session that has bars (a holiday has none), else 0."""
    sess = session_ids(idx)
    traded = set(int(x) for x in np.unique(bars["session"]))
    return np.array([s >= 0 and int(s) in traded for s in sess], dtype=int)


# ---------------------------------------------------------------- storm and book

def regular_close(bars: pd.DataFrame, session: int) -> tuple[pd.Timestamp, float]:
    """The last regular-session minute (before 16:00 ET) of `session` and its close."""
    part = bars[bars["session"] == session]
    et = part.index.tz_convert(ET)
    reg = part[(et.hour * 60 + et.minute) < REG_CLOSE_MIN]
    if reg.empty:
        raise ValueError(f"no regular-session bars on {session}")
    return reg.index[-1], float(reg["mid"].iloc[-1])


def session_low(bars: pd.DataFrame, session: int, until: pd.Timestamp) -> tuple[pd.Timestamp, float]:
    part = bars[(bars["session"] == session) & (bars.index <= until)]
    if part.empty:
        raise ValueError(f"no bars on {session}")
    t = part["low"].idxmin()
    return t, float(part.loc[t, "low"])


def close_to_low(bars: pd.DataFrame, until: pd.Timestamp = WINDOW_END) -> dict:
    if "bad_print" in bars:
        bars = bars[bars["bad_print"] == 0]
    t0, close = regular_close(bars, CLOSE_SESSION)
    t1, low = session_low(bars, LOW_SESSION, until)
    return {"close_utc": t0, "close": close, "low_utc": t1, "low": low,
            "move_bp": (low / close - 1.0) * 1e4}


def simulate_stock(price: np.ndarray, book: dict, actions=(), open_price=None, traded=None) -> BookPath:
    """Equity per minute of a long single-stock book (execution and margin as in the module
    doc). `price`: each frame's close (the mark); `open_price`: each bar's open (default
    the previous close); `traded`: frames with a real bar (default all). actions:
    (earliest fill frame, symbol, "cut" | "restore"; storm.exposure.policy_actions puts a
    signal on bar t at t + 1), each filled at the open of the first traded frame from there."""
    price = np.asarray(price, dtype=float)
    n, sym = len(price), book["symbol"]
    open_price = np.concatenate([price[:1], price[:-1]]) if open_price is None else np.asarray(open_price, float)
    traded = np.ones(n, dtype=bool) if traded is None else np.asarray(traded, dtype=bool)
    for name, arr in (("price", price), ("open_price", open_price)):
        if len(arr) != n or not np.all(np.isfinite(arr)) or np.any(arr <= 0):
            raise ValueError(f"{name} must be finite, positive and aligned")
    full = book["position_usd"] / price[0]
    qty, cash = full, book["equity_usd"] - full * price[0]
    mm, frac = book["maintenance_margin"], book["cut_fraction"]
    by_fill: dict[int, list[tuple[int, str]]] = {}
    for s, _, kind in sorted(actions):
        f = fill_frame(traded, int(s))
        if f is not None:
            by_fill.setdefault(f, []).append((int(s) - 1, kind))
    eq_out, gross_out, qty_out, cash_out = (np.empty(n) for _ in range(4))
    margin_call_i, cuts, restores, fills = None, [], [], []

    def trade(target: float, p: float, i: int, at: str, s: int, action: str) -> None:
        nonlocal qty, cash
        dq = target - qty
        cash -= dq * p
        qty = target
        fills.append({"i": i, "signal_i": s, "pair": sym, "action": action, "at": at,
                      "side": "buy" if dq > 0 else "sell", "qty": abs(dq), "price": p, "mid": p,
                      "cost_usd": 0.0})

    def breach(p: float) -> bool:
        return qty != 0 and cash + qty * p < mm * abs(qty) * p

    for i in range(n):
        if margin_call_i is None and i > 0:
            po = open_price[i]
            if breach(po):
                trade(0.0, po, i, "open", i, "margin_call")
                margin_call_i = i
            else:
                for s, kind in by_fill.get(i, []):
                    if kind == "cut" and qty == full and frac > 0:
                        trade(full * (1.0 - frac), po, i, "open", s, "cut")
                        cuts.append((i, sym))
                    elif kind == "restore" and qty != full and cash + qty * po >= mm * full * po:
                        trade(full, po, i, "open", s, "restore")
                        restores.append((i, sym))
        p = price[i]
        if margin_call_i is None and breach(p):
            trade(0.0, p, i, "close", i, "margin_call")
            margin_call_i = i
        eq, g = cash + qty * p, abs(qty) * p
        eq_out[i], gross_out[i], qty_out[i], cash_out[i] = eq, g, qty, cash
    return BookPath(eq_out, gross_out, {sym: qty_out}, {"USD": cash_out}, margin_call_i, cuts, restores,
                    frac if cuts else 0.0, fills)


def exposure_snapshot(path: BookPath, price: np.ndarray, book: dict, i: int) -> dict:
    sym = book["symbol"]
    q = float(path.qty[sym][i])
    eq, g = float(path.equity[i]), float(path.gross_usd[i])
    positions = [] if q == 0 else [{"instrument": f"{sym} shares", "side": "long" if q > 0 else "short",
                                    "notional_usd": round(abs(q) * float(price[i]))}]
    return {"as_of_i": int(i), "positions": positions,
            "net_usd_by_ccy": {"USD": int(round(q * float(price[i])))},
            "leverage": round(g / eq, 2) if eq > 0 else None,
            "margin_buffer_pct": round((eq - book["maintenance_margin"] * g) / eq * 100.0, 1) if eq > 0 else None}


def stress_test(bars: dict[str, pd.DataFrame], path: BookPath, price: np.ndarray, book: dict, i: int,
                as_of: pd.Timestamp) -> list[dict]:
    """Point-in-time stress menu: each chip name's 11 Nov close to 12 Nov low move whose low
    came before `as_of`, applied (unrounded) to the holdings of `path` at frame i, revalued
    as simulate_stock does: equity cash + qty x shocked price, margin call when that is
    below maintenance x |qty| x shocked price."""
    sym, mm = book["symbol"], book["maintenance_margin"]
    q, cash, p = float(path.qty[sym][i]), float(path.cash["USD"][i]), float(price[i])
    out = []
    for name in SYMBOLS:
        if name not in bars:
            continue
        m = close_to_low(bars[name])
        if not m["low_utc"] < as_of:
            continue
        r = m["low"] / m["close"] - 1.0
        p1 = p * (1.0 + r)
        eq1 = cash + q * p1
        applied = "" if name == sym else f", applied to {sym}"
        out.append({"scenario": f"{name} 11 Nov close to 12 Nov low: {r * 100:+.1f}%{applied}",
                    "pnl_usd": round(q * (p1 - p)), "margin_call": bool(q != 0 and eq1 < mm * abs(q) * p1)})
    return out


# ---------------------------------------------------------------- bundle

@dataclass
class EquityRun:
    bars: dict[str, pd.DataFrame]
    feats: dict[str, pd.DataFrame]
    cfg: dict


def build_bundle(run: EquityRun, start: pd.Timestamp = WINDOW_START,
                 end: pd.Timestamp = WINDOW_END) -> tuple[dict, dict]:
    """Returns (bundle, summary facts for printing)."""
    sym = SHIP_SYMBOL
    bars, feat, cfg = run.bars[sym], run.feats[sym], run.cfg
    empty_calendar = load_calendar(Path("/nonexistent"))
    res = run_detector(feat, empty_calendar, cfg, exposure=1.0)
    idx = pd.date_range(start, end, freq=f"{STEP_S}s")
    is_open = market_open(idx, bars)
    g, filled, traded = _grid(feat.join(res.frame[["risk", "state"]]), start, end, is_open)
    n = len(idx)

    def frame_of(t: pd.Timestamp) -> int:
        return int((t.floor("min") - idx[0]) / pd.Timedelta(seconds=STEP_S))

    m = close_to_low(bars, end)
    # One move, from the close to the low: no merged windows, so first_onset is the onset.
    storm = SimpleNamespace(storm_id=STORM_ID, onset_utc=m["close_utc"], trough_utc=m["low_utc"],
                            onset_mid=m["close"], trough_mid=m["low"],
                            first_onset_utc=m["close_utc"], first_onset_mid=m["close"])
    onset_i, trough_i = frame_of(storm.onset_utc), frame_of(storm.trough_utc)
    if not (0 <= onset_i < trough_i < n):
        raise ValueError("onset or trough outside the window")

    if (since := cut_since(res.events, idx[0])) is not None:
        raise ValueError(f"the replay starts at {idx[0]:%d %b %H:%M} UTC inside the danger alarm raised at "
                         f"{since:%d %b %H:%M} UTC; the prepared ship would hold shares the policy cut. "
                         "Start WINDOW_START before the alarm")
    win = _visible_events([e for e in res.events if idx[0] <= e["time"] <= idx[-1]], g["state"], frame_of)
    mid = g["mid"].to_numpy(dtype=float)
    actions = policy_actions({sym: win}, frame_of)
    opens = g["open"].to_numpy(dtype=float)
    paths = {"prepared": simulate_stock(mid, BOOK, actions, opens, traded),
             "unprepared": simulate_stock(mid, BOOK, (), opens, traded)}
    prep = paths["prepared"]

    def ahead(e: dict) -> float | None:
        if not alarm_matches(e["time"], e.get("clear"), storm):
            return None
        a = move_ahead_pct(e["time"], storm, feat["mid"])
        return None if a is None else _r(a, 1)

    events = []
    for e in win:
        ev = {"i": frame_of(e["time"]), "type": e["type"],
              "text": _event_text(e, sym, cfg, ahead(e) is not None)}
        if e["type"] == "alarm":
            ev["move_ahead_pct"] = ahead(e)
        events.append(ev)
    events += trade_events(prep, sym, BOOK["cut_fraction"])
    for name, p in paths.items():
        if p.margin_call_i is not None:
            events.append({"i": p.margin_call_i, "type": "margin_call", "ship": name,
                           "text": "Margin call: position closed"})
    events.sort(key=lambda ev: (ev["i"], EVENT_ORDER[ev["type"]]))

    as_of_i = max(0, onset_i - 1)
    unprep = paths["unprepared"]
    move_pct = m["move_bp"] / 100
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "storm_id": STORM_ID,
        "title": TITLE,
        "symbol": sym,
        "asset_class": "equity",
        "source": "yahoo",
        "book_is_synthetic": True,
        "t0": int(idx[0].timestamp()),
        "step_s": STEP_S,
        "n": n,
        "storm": {
            "onset_i": onset_i,
            "trough_i": trough_i,
            "move_bp": _r(m["move_bp"], 1),
            "kind": "unscheduled",
            "label": f"{move_pct:+.1f}% from the 11 Nov close to the 12 Nov low",
            "first_onset_i": onset_i,
            **storm_alarm_fields(storm, res.storm_alarms(), feat["mid"], frame_of),
        },
        "series": {
            "open": [_r(v, 5) for v in g["open"]],
            "high": [_r(v, 5) for v in g["high"]],
            "low": [_r(v, 5) for v in g["low"]],
            "mid": [_r(v, 5) for v in g["mid"]],
            "spread_bp": [0.0] * n,
            "vol_ratio": [_r(v, 2) for v in g["vol_ratio"]],
            "risk": [_r(v, 2) for v in g["risk"]],
            "state": [int(v) for v in g["state"]],
            "jump": [int(v) for v in g["jump"]],
            "prepared_equity": [int(round(v)) for v in prep.equity],
            "unprepared_equity": [int(round(v)) for v in unprep.equity],
            "market_open": [int(v) for v in is_open],
        },
        "ships": {
            name: {"label": SHIP_LABELS[name], "start_equity_usd": int(BOOK["equity_usd"]),
                   "margin_call_i": p.margin_call_i, "cut_i": p.cut_i,
                   "cut_fraction": _r(p.cut_fraction, 2), "restore_i": p.restore_i}
            for name, p in paths.items()
        },
        "events": events,
        "exposure": exposure_snapshot(unprep, mid, BOOK, as_of_i),
        "stress": stress_test(run.bars, unprep, mid, BOOK, as_of_i, idx[as_of_i]),
        "report": None,
    }

    chips = [s for s in CHIP_NAMES if s in run.feats]
    comove = feat["comove"][(feat.index >= start) & (feat.index <= end)]
    summary = {
        **m,
        "filled_minutes": filled,
        "closed_minutes": int((is_open == 0).sum()),
        "alarms": [(idx[ev["i"]], ev["move_ahead_pct"]) for ev in events if ev["type"] == "alarm"],
        "cut": [idx[i] for i, _ in prep.cuts],
        "restore": [idx[i] for i, _ in prep.restores],
        "ships": {k: {"final": float(p.equity[-1]), "min": float(p.equity.min()),
                      "drawdown": max_drawdown(p.equity),
                      "margin_call": idx[p.margin_call_i] if p.margin_call_i is not None else None}
                  for k, p in paths.items()},
        "comove_max": int(comove.max()) if len(comove) else 0,
        "comove_max_utc": comove.idxmax() if len(comove) else None,
        "comove_at_alarms": [int(feat["comove"].get(idx[ev["i"]], 0)) for ev in events if ev["type"] == "alarm"],
        "chips": len(chips),
        "names": {s: close_to_low(run.bars[s], end) for s in SYMBOLS if s in run.bars},
        "week_alarms": [e["time"] for e in res.events if e["type"] == "alarm"],
        "nov10_events": [(e["time"], e["type"]) for e in res.events
                         if e["time"].tz_convert(ET).day == 10 and e["type"] != "watch"],
        "nov10_storm_level": [a for a, _ in res.storm_alarms() if a.tz_convert(ET).day == 10],
        "nov10_bad_print_risk": [(t, float(res.frame.loc[t, "risk"])) for t in bars.attrs.get("bad_prints", [])
                                 if t.tz_convert(ET).day == 10],
        "bad_prints": {s: b.attrs.get("bad_prints", []) for s, b in run.bars.items()},
        "fills": [{**f, "utc": idx[f["i"]]} for f in prep.fills],
        "stress_n": len(bundle["stress"]),
    }
    return bundle, summary


def print_summary(s: dict) -> None:
    for sym, ts in s["bad_prints"].items():
        if ts:
            print(f"{sym}: {len(ts)} bad print(s) flagged (visible at the minute, excluded from the next "
                  f"minute on): {', '.join(f'{t:%d %b %H:%M}' for t in ts)} UTC")
    print(f"NVDA (Yahoo one-minute bars, SYNTHETIC book: long ${BOOK['position_usd']:,.0f} on "
          f"${BOOK['equity_usd']:,.0f} equity, maintenance {BOOK['maintenance_margin']:.0%} of the position)")
    print(f"11 Nov close {s['close']:.2f} ({s['close_utc']:%H:%M} UTC bar); 12 Nov low {s['low']:.2f} "
          f"at {s['low_utc']:%H:%M} UTC: {s['move_bp'] / 100:+.2f}% ({s['move_bp']:+.0f} bp)")
    print(f"replay {WINDOW_START:%d %b %H:%M} .. {WINDOW_END:%d %b %H:%M} UTC; market closed "
          f"{s['closed_minutes']} minutes; {s['filled_minutes']} open minutes filled")
    if s["alarms"]:
        for (t, a), c in zip(s["alarms"], s["comove_at_alarms"]):
            ahead = "not linked to the close-to-low move" if a is None else f"{a:.1f}% of the move still ahead"
            print(f"storm alarm {t:%d %b %H:%M} UTC: {ahead}; {c} of {s['chips']} chip names moving together")
    else:
        print("storm alarm: none in the replay")
    for f in s["fills"]:
        print(f"prepared ship {f['action']} fill {f['utc']:%d %b %H:%M} UTC: {f['side']} {f['qty']:,.0f} "
              f"shares at {f['price']:.2f} ({f['at']}, no quotes: no spread)")
    for k in ("prepared", "unprepared"):
        sh = s["ships"][k]
        mc = "no margin call" if sh["margin_call"] is None else f"MARGIN CALL {sh['margin_call']:%d %b %H:%M} UTC"
        print(f"  {k:10} final ${sh['final']:,.0f}, lowest ${sh['min']:,.0f}, "
              f"max drawdown {sh['drawdown'][1]:.1f}%, {mc}")
    gap = s["ships"]["prepared"]["final"] - s["ships"]["unprepared"]["final"]
    print(f"  the alarm made a difference of ${gap:,.0f} at the end of the replay")
    if s["comove_max_utc"] is not None:
        print(f"sector: at most {s['comove_max']} of {s['chips']} chip names moved together "
              f"(|z| >= 3, same way) in one minute, first at {s['comove_max_utc']:%d %b %H:%M} UTC")
    print("each name, 11 Nov close to 12 Nov low:")
    for sym, m in s["names"].items():
        print(f"  {sym:5} {m['close']:9.2f} -> {m['low']:9.2f} at {m['low_utc']:%H:%M} UTC  {m['move_bp'] / 100:+6.1f}%")
    print(f"NVDA storm-level danger alarms over 9-13 Nov: {len(s['week_alarms'])} "
          f"({', '.join(f'{t:%d %b %H:%M}' for t in s['week_alarms'])})")
    risk = ", ".join(f"{t:%H:%M} UTC risk {r:.2f}" for t, r in s["nov10_bad_print_risk"]) or "none"
    print(f"10 Nov (bad print visible at its minute: {risk}): storm-level detections "
          f"{[f'{t:%H:%M}' for t in s['nov10_storm_level']] or 'none'}; alerts "
          f"{[(f'{t:%H:%M}', k) for t, k in s['nov10_events']] or 'none'}")
    print(f"stress menu: {s['stress_n']} scenarios (point in time: only lows before the snapshot)")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--export", action="store_true", help=f"write {STORM_ID}.json and refresh index.json")
    ap.add_argument("--refresh", action="store_true", help="fetch from Yahoo again")
    ap.add_argument("--data", type=Path, default=EQUITY_DIR)
    ap.add_argument("--out", type=Path, default=BUNDLES_DIR)
    ap.add_argument("--live", action="store_true", help="write the report with the real model gateway")
    ap.add_argument("--model", help="report writer model (default: the gateway's META_MODEL)")
    ap.add_argument("--provider", default="meta", help="report writer provider (default meta)")
    args = ap.parse_args(argv)

    bars = load_bars(SYMBOLS, args.data, args.refresh)
    run = EquityRun(bars, equity_features(bars), load_config())
    bundle, s = build_bundle(run)
    print_summary(s)
    if args.export:
        attach_report(bundle, args.live, args.model, args.provider)
        path = write_bundle(bundle, args.out)
        try:
            metrics = load_index_metrics()
        except StaleMetrics as e:
            raise SystemExit(f"refusing to write index.json: {e}")
        index = write_index(args.out, None, metrics)
        r = bundle["report"]
        print(f"report ({r['model']}, verified={r['verified']}, inspector={r['inspector']['verdict']}): {r['text']}")
        print(f"wrote {path}")
        print(f"wrote {index}")


if __name__ == "__main__":
    main()
