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
one-minute print the market did not trade through; it is dropped, never replaced, and the
dropped bars are printed. (On 10 Nov 18:00 UTC NVDA, AVGO, INTC, MU and SMH all show one:
NVDA closes 6.5% up and the next bar opens at the old price. Kept, that single print
holds the trailing volatility of the next 1,440 trading minutes several times too high.)

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
When equity falls below maintenance, the position is closed at that minute's price and
equity stays flat afterwards. The prepared ship cuts 75% on a storm-level danger alarm and
restores on the all-clear; the unprepared ship holds. No spread, no slippage, no fees.

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
from .evaluate import LINK_BEFORE, move_ahead_pct
from .exposure import BookPath, max_drawdown, policy_actions
from .export import (SCHEMA_VERSION, SHIP_LABELS, EVENT_ORDER, STEP_S, _event_text, _grid, _r,
                     _visible_events, attach_report, load_index_metrics, write_bundle, write_index)
from .features import add_comove, bar_features
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
    """Yahoo bars -> bar_features input (open, high, low, mid = close, session), 9..13 Nov,
    without bad prints (listed in bars.attrs["dropped"])."""
    df = raw.sort_values("timestamp").drop_duplicates("timestamp").set_index("timestamp")
    df.index = pd.DatetimeIndex(df.index).tz_convert("UTC")
    dropped = bad_prints(df)
    df = df.drop(dropped)
    sess = session_ids(df.index)
    if (sess < 0).any():
        raise ValueError(f"{symbol}: {int((sess < 0).sum())} bars outside 04:00-20:00 ET")
    bars = pd.DataFrame({"open": df["open"], "high": df["high"], "low": df["low"], "mid": df["close"],
                         "session": sess}, index=df.index)
    bars = bars[bars["session"].isin(SESSIONS)].copy()
    bars.attrs["dropped"] = [t for t in dropped if session_ids(pd.DatetimeIndex([t]))[0] in SESSIONS]
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
    t0, close = regular_close(bars, CLOSE_SESSION)
    t1, low = session_low(bars, LOW_SESSION, until)
    return {"close_utc": t0, "close": close, "low_utc": t1, "low": low,
            "move_bp": (low / close - 1.0) * 1e4}


def simulate_stock(price: np.ndarray, book: dict, actions=()) -> BookPath:
    """Equity per minute of a long single-stock book; actions: (frame, symbol, "cut" | "restore")."""
    price = np.asarray(price, dtype=float)
    if not np.all(np.isfinite(price)) or np.any(price <= 0):
        raise ValueError("price must be finite and positive")
    n, sym = len(price), book["symbol"]
    full = book["position_usd"] / price[0]
    qty, cash = full, book["equity_usd"] - full * price[0]
    mm, frac = book["maintenance_margin"], book["cut_fraction"]
    by_i: dict[int, list[str]] = {}
    for i, _, kind in actions:
        by_i.setdefault(int(i), []).append(kind)
    eq_out, gross_out, qty_out, cash_out = (np.empty(n) for _ in range(4))
    margin_call_i, cuts, restores = None, [], []
    for i in range(n):
        p = price[i]
        if margin_call_i is None:
            for kind in by_i.get(i, []):
                if kind == "cut" and qty == full and frac > 0:
                    target = full * (1.0 - frac)
                    cash += (qty - target) * p
                    qty = target
                    cuts.append((i, sym))
                elif kind == "restore" and qty != full and cash + qty * p >= mm * full * p:
                    cash -= (full - qty) * p
                    qty = full
                    restores.append((i, sym))
        eq, g = cash + qty * p, abs(qty) * p
        if margin_call_i is None and g > 0 and eq < mm * g:
            cash, qty, g, margin_call_i = eq, 0.0, 0.0, i
        eq_out[i], gross_out[i], qty_out[i], cash_out[i] = eq, g, qty, cash
    return BookPath(eq_out, gross_out, {sym: qty_out}, {"USD": cash_out}, margin_call_i, cuts, restores,
                    frac if cuts else 0.0)


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


def stress_test(bars: dict[str, pd.DataFrame], position_usd: float, equity_usd: float, book: dict) -> list[dict]:
    """Each chip name's own 11 Nov close to 12 Nov low move, applied to the NVDA position
    (`position_usd` and `equity_usd`: the book just before onset)."""
    out = []
    for sym in SYMBOLS:
        if sym not in bars:
            continue
        m = close_to_low(bars[sym])
        r = m["move_bp"] / 1e4
        pnl = position_usd * r
        mc = equity_usd + pnl < book["maintenance_margin"] * position_usd * (1 + r)
        applied = "" if sym == book["symbol"] else f", applied to {book['symbol']}"
        out.append({"scenario": f"{sym} 11 Nov close to 12 Nov low: {m['move_bp'] / 100:+.1f}%{applied}",
                    "pnl_usd": round(pnl), "margin_call": bool(mc)})
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
    g, filled = _grid(feat.join(res.frame[["risk", "state"]]), start, end, is_open)
    n = len(idx)

    def frame_of(t: pd.Timestamp) -> int:
        return int((t.floor("min") - idx[0]) / pd.Timedelta(seconds=STEP_S))

    m = close_to_low(bars, end)
    storm = SimpleNamespace(onset_utc=m["close_utc"], trough_utc=m["low_utc"],
                            onset_mid=m["close"], trough_mid=m["low"])
    onset_i, trough_i = frame_of(storm.onset_utc), frame_of(storm.trough_utc)
    if not (0 <= onset_i < trough_i < n):
        raise ValueError("onset or trough outside the window")

    win = _visible_events([e for e in res.events if idx[0] <= e["time"] <= idx[-1]], g["state"], frame_of)
    mid = g["mid"].to_numpy(dtype=float)
    actions = policy_actions({sym: win}, frame_of)
    paths = {"prepared": simulate_stock(mid, BOOK, actions), "unprepared": simulate_stock(mid, BOOK)}
    prep = paths["prepared"]

    def ahead(t: pd.Timestamp) -> float | None:
        if not (storm.onset_utc - LINK_BEFORE <= t <= storm.trough_utc):
            return None
        return _r(move_ahead_pct(t, storm, feat["mid"]), 1)

    events = []
    for e in win:
        ev = {"i": frame_of(e["time"]), "type": e["type"],
              "text": _event_text(e, sym, cfg, ahead(e["time"]) is not None)}
        if e["type"] == "alarm":
            ev["move_ahead_pct"] = ahead(e["time"])
        events.append(ev)
    pct = round(BOOK["cut_fraction"] * 100)
    for i, _ in prep.cuts:
        events.append({"i": i, "type": "cut", "text": f"Prepared ship cuts its {sym} position by {pct}%"})
    for i, _ in prep.restores:
        events.append({"i": i, "type": "restore", "text": f"Prepared ship restores its full {sym} position"})
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
        "stress": stress_test(run.bars, float(unprep.gross_usd[as_of_i]), float(unprep.equity[as_of_i]), BOOK),
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
        "dropped": {s: b.attrs.get("dropped", []) for s, b in run.bars.items()},
    }
    return bundle, summary


def print_summary(s: dict) -> None:
    for sym, ts in s["dropped"].items():
        if ts:
            print(f"{sym}: dropped {len(ts)} bad print(s): {', '.join(f'{t:%d %b %H:%M}' for t in ts)} UTC")
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
    for t in s["cut"]:
        print(f"prepared ship cut 75% at {t:%d %b %H:%M} UTC")
    for t in s["restore"]:
        print(f"prepared ship restored at {t:%d %b %H:%M} UTC")
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
        index = write_index(args.out, None, load_index_metrics())
        r = bundle["report"]
        print(f"report ({r['model']}, verified={r['verified']}, inspector={r['inspector']['verdict']}): {r['text']}")
        print(f"wrote {path}")
        print(f"wrote {index}")


if __name__ == "__main__":
    main()
