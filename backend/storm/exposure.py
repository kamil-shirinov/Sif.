"""Synthetic trader book, the two ships, and the stress test.

THE BOOK IS SYNTHETIC. No real trader, account or position is represented.

Book: $1,000,000 equity, long USD 20,000,000 against JPY (20x leverage). Maintenance
margin is 2.5% of the open USD notional; when equity falls below it the position is
closed at that minute's mid and equity stays flat afterwards. Prices are spot mid, no
spread or slippage on the cut or the close-out.

Ships: the unprepared ship holds. The prepared ship cuts the position by 75% at the
first storm alarm.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .features import usd_sign

BOOK = {
    "synthetic": True,
    "symbol": "USDJPY",
    "equity_usd": 1_000_000.0,
    "notional_usd": 20_000_000.0,
    "maintenance_margin": 0.025,
    "cut_fraction": 0.75,
}


@dataclass
class ShipPath:
    equity: np.ndarray          # USD equity per minute
    position_usd: np.ndarray    # open long-USD notional per minute (after any action that minute)
    quote_cash: np.ndarray      # quote-currency leg (e.g. JPY) per minute
    margin_call_i: int | None
    cut_i: int | None
    cut_fraction: float


def simulate(mid: np.ndarray, cut_i: int | None = None, cut_fraction: float = 0.0, book: dict = BOOK) -> ShipPath:
    """Equity per minute of a long-USD book against the quote currency of a USDxxx pair.

    Opens at mid[0]. At minute cut_i (if given) sells cut_fraction of the USD position
    at mid[cut_i]. Then, each minute, if equity < maintenance x open notional, closes
    everything at that mid.
    """
    mid = np.asarray(mid, dtype=float)
    if not np.all(np.isfinite(mid)) or np.any(mid <= 0):
        raise ValueError("mid must be finite and positive")
    n = len(mid)
    pos = book["notional_usd"]
    usd = book["equity_usd"] + pos
    quote = -pos * mid[0]
    mm = book["maintenance_margin"]
    equity = np.empty(n)
    pos_out = np.empty(n)
    quote_out = np.empty(n)
    margin_call_i = None
    did_cut = None
    for i in range(n):
        if pos > 0 and cut_i is not None and i == cut_i and cut_fraction > 0:
            sold = pos * cut_fraction
            usd -= sold
            quote += sold * mid[i]
            pos -= sold
            did_cut = i
        eq = usd + quote / mid[i]
        if pos > 0 and eq < mm * pos:
            usd, quote, pos = eq, 0.0, 0.0
            margin_call_i = i
        equity[i] = eq
        pos_out[i] = pos
        quote_out[i] = quote
    return ShipPath(equity, pos_out, quote_out, margin_call_i, did_cut, cut_fraction if did_cut is not None else 0.0)


def ships(mid: np.ndarray, alarm_i: int | None, book: dict = BOOK) -> dict[str, ShipPath]:
    return {
        "prepared": simulate(mid, alarm_i, book["cut_fraction"], book),
        "unprepared": simulate(mid, None, 0.0, book),
    }


def exposure_snapshot(path: ShipPath, mid: np.ndarray, i: int, book: dict = BOOK) -> dict:
    """The book as it stands at minute i (contract `exposure` object)."""
    sym = book["symbol"]
    base, quote_ccy = sym[:3], sym[3:]
    eq = float(path.equity[i])
    pos = float(path.position_usd[i])
    quote_usd = float(path.quote_cash[i] / mid[i])
    mm = book["maintenance_margin"] * pos
    return {
        "as_of_i": int(i),
        "positions": [
            {"instrument": f"{sym} spot", "side": f"long {base}, short {quote_ccy}", "notional_usd": round(pos)}
        ] if pos > 0 else [],
        "net_usd_by_ccy": {base: round(pos), quote_ccy: round(quote_usd)},
        "leverage": round(pos / eq, 2) if eq > 0 else None,
        "margin_buffer_pct": round((eq - mm) / eq * 100.0, 1) if eq > 0 else None,
    }


def stress_test(storms: pd.DataFrame, book_mid: pd.Series, book: dict = BOOK) -> list[dict]:
    """Apply each labelled storm to the book as it stood just before onset.

    The book is long USD against JPY. A storm on USDJPY applies its own onset-to-trough
    move. A storm on another pair is applied as the same move in USD (EURUSD inverted)
    on USDJPY. Uses the onset-to-trough move, which is the worst point of the storm.
    """
    if usd_sign(book["symbol"]) != 1:
        raise ValueError("stress_test assumes a USD-base book")
    n_usd = book["notional_usd"]
    out = []
    for s in storms.itertuples():
        before = book_mid[book_mid.index < s.onset_utc]
        if before.empty:
            continue
        s0 = float(before.iloc[-1])
        s1 = s0 * (1.0 + s.usd_move_bp / 1e4)
        pnl = n_usd * (1.0 - s0 / s1)
        margin_call = book["equity_usd"] + pnl < book["maintenance_margin"] * n_usd
        when = f"{s.onset_utc:%d %b %H:%M} UTC"
        if s.pair == book["symbol"]:
            scenario = f"{s.pair} storm {when}: {s.move_bp:+.0f} bp"
        else:
            scenario = f"{s.pair} storm {when}: {s.move_bp:+.0f} bp, applied as USD {s.usd_move_bp:+.0f} bp"
        out.append({"scenario": scenario, "pnl_usd": round(pnl), "margin_call": bool(margin_call)})
    return out
