"""Synthetic trader books, the two ships, policy v1 and the stress test.

THE BOOKS ARE SYNTHETIC. No real trader, account or position is represented.

A book is USD equity plus spot legs, each long USD against one currency (USDJPY and
USDSGD: long the pair; EURUSD: short EUR). Legs open at the first mid. Cash is kept per
currency and marked at spot mid, so a cut's realised P&L stays in the currency it was
made in. Maintenance margin is a share of the open notional, in USD; when equity falls
below it, every leg is closed at that minute's mid, all cash is converted to USD, and
equity stays flat afterwards (one margin call ends the book). No spread, no slippage.

Policy v1 (the prepared ship), per leg:
  storm-level danger alarm   cut the leg by `cut_fraction` (75%) at that minute's mid
  all-clear after a cut      restore the leg to its full size (skipped if restoring would
                             put the book straight into a margin call)
  squall                     no trade (the lighthouse goes amber)
  fair wind                  no trade
The unprepared ship holds throughout.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .detector import load_calendar, run_detector
from .features import usd_sign

EQUITY_USD = 1_000_000.0
MAINTENANCE = 0.025
CUT_FRACTION = 0.75
BOOK_NOTIONAL_USD = 20_000_000.0
POLICY_PAIRS = ("USDJPY", "EURUSD", "USDSGD")


def book_for(pairs, notional_usd: float = BOOK_NOTIONAL_USD) -> dict:
    """Long USD `notional_usd` in total, split equally across `pairs`."""
    pairs = (pairs,) if isinstance(pairs, str) else tuple(pairs)
    return {
        "synthetic": True,
        "equity_usd": EQUITY_USD,
        "maintenance_margin": MAINTENANCE,
        "cut_fraction": CUT_FRACTION,
        "legs": [{"pair": p, "usd_notional": notional_usd / len(pairs)} for p in pairs],
    }


POLICY_BOOK = book_for(POLICY_PAIRS)


def leg_exposure(pair: str) -> int:
    """Sign of a long-USD leg's position in the pair's base currency (+1 long, -1 short)."""
    return usd_sign(pair)


def _ccys(pair: str) -> tuple[str, str]:
    return pair[:3], pair[3:]


@dataclass
class BookPath:
    equity: np.ndarray                     # USD equity per minute
    gross_usd: np.ndarray                  # open notional per minute, USD
    qty: dict[str, np.ndarray]             # base-currency position per leg per minute
    cash: dict[str, np.ndarray]            # cash per currency per minute
    margin_call_i: int | None
    cuts: list[tuple[int, str]] = field(default_factory=list)
    restores: list[tuple[int, str]] = field(default_factory=list)
    cut_fraction: float = 0.0

    @property
    def cut_i(self) -> int | None:
        return self.cuts[0][0] if self.cuts else None

    @property
    def restore_i(self) -> int | None:
        first = self.cut_i
        later = [i for i, _ in self.restores if first is not None and i >= first]
        return later[0] if later else None


def simulate_book(mids: dict[str, np.ndarray], book: dict, actions: list[tuple[int, str, str]] = ()) -> BookPath:
    """Equity per minute of `book` on aligned mids. actions: (frame, pair, "cut" | "restore")."""
    n = None
    for p, m in mids.items():
        m = np.asarray(m, dtype=float)
        if not np.all(np.isfinite(m)) or np.any(m <= 0):
            raise ValueError(f"{p}: mid must be finite and positive")
        if n is not None and len(m) != n:
            raise ValueError("mids must be aligned")
        n = len(m)
    mids = {p: np.asarray(m, dtype=float) for p, m in mids.items()}
    legs = [leg["pair"] for leg in book["legs"]]
    ccys = sorted({"USD"} | {c for p in legs for c in _ccys(p)})

    def usd_rate(ccy: str, i: int) -> float:
        if ccy == "USD":
            return 1.0
        for p in legs:
            base, quote = _ccys(p)
            if base == ccy and quote == "USD":
                return mids[p][i]
            if base == "USD" and quote == ccy:
                return 1.0 / mids[p][i]
        raise ValueError(f"no USD rate for {ccy}")

    cash = {c: 0.0 for c in ccys}
    cash["USD"] = book["equity_usd"]
    full, qty = {}, {}
    for leg in book["legs"]:
        p = leg["pair"]
        base, quote = _ccys(p)
        q = leg["usd_notional"] * leg_exposure(p) / usd_rate(base, 0)
        full[p], qty[p] = q, 0.0

    def trade(p: str, target: float, i: int) -> None:
        base, quote = _ccys(p)
        dq = target - qty[p]
        cash[base] += dq
        cash[quote] -= dq * mids[p][i]
        qty[p] = target

    for p in legs:
        trade(p, full[p], 0)

    mm = book["maintenance_margin"]
    frac = book["cut_fraction"]
    by_i: dict[int, list[tuple[str, str]]] = {}
    for i, p, kind in actions:
        by_i.setdefault(int(i), []).append((p, kind))

    eq_out, gross_out = np.empty(n), np.empty(n)
    qty_out = {p: np.empty(n) for p in legs}
    cash_out = {c: np.empty(n) for c in ccys}
    margin_call_i = None
    cuts, restores = [], []

    def equity(i: int) -> float:
        return sum(cash[c] * usd_rate(c, i) for c in ccys)

    def gross(i: int, q: dict) -> float:
        return sum(abs(q[p]) * usd_rate(_ccys(p)[0], i) for p in legs)

    for i in range(n):
        if margin_call_i is None:
            for p, kind in by_i.get(i, []):
                if kind == "cut" and qty[p] == full[p] and frac > 0:
                    trade(p, full[p] * (1.0 - frac), i)
                    cuts.append((i, p))
                elif kind == "restore" and qty[p] != full[p]:
                    if equity(i) >= mm * gross(i, {**qty, p: full[p]}):
                        trade(p, full[p], i)
                        restores.append((i, p))
        eq = equity(i)
        g = gross(i, qty)
        if margin_call_i is None and g > 0 and eq < mm * g:
            for p in legs:
                trade(p, 0.0, i)
            for c in ccys:
                cash[c] = 0.0
            cash["USD"] = eq
            margin_call_i = i
            g = 0.0
        eq_out[i], gross_out[i] = eq, g
        for p in legs:
            qty_out[p][i] = qty[p]
        for c in ccys:
            cash_out[c][i] = cash[c]
    return BookPath(eq_out, gross_out, qty_out, cash_out, margin_call_i, cuts, restores,
                    frac if cuts else 0.0)


def policy_actions(events: dict[str, list[dict]], frame_of) -> list[tuple[int, str, str]]:
    """Policy v1 trades from book-aware detector events per pair (time -> frame via frame_of)."""
    out = []
    for p, evs in events.items():
        cut = False
        for e in evs:
            if e["type"] == "alarm" and not cut:
                out.append((frame_of(e["time"]), p, "cut"))
                cut = True
            elif e["type"] == "all_clear" and cut:
                out.append((frame_of(e["time"]), p, "restore"))
                cut = False
    return sorted(out)


def ships(mids: dict[str, np.ndarray], book: dict, actions) -> dict[str, BookPath]:
    return {"prepared": simulate_book(mids, book, actions), "unprepared": simulate_book(mids, book, [])}


def exposure_snapshot(path: BookPath, mids: dict[str, np.ndarray], book: dict, i: int) -> dict:
    """The book as it stands at minute i (contract `exposure` object)."""
    positions = []
    net: dict[str, float] = {}
    for leg in book["legs"]:
        p = leg["pair"]
        base, quote = _ccys(p)
        q = float(path.qty[p][i])
        if q == 0:
            continue
        usd = abs(q) if base == "USD" else abs(q) * float(mids[p][i])
        side = f"long {base}, short {quote}" if q > 0 else f"short {base}, long {quote}"
        positions.append({"instrument": f"{p} spot", "side": side, "notional_usd": round(usd)})
    rates = {}
    for leg in book["legs"]:
        base, quote = _ccys(leg["pair"])
        m = float(mids[leg["pair"]][i])
        rates[quote if base == "USD" else base] = 1.0 / m if base == "USD" else m
    for c, arr in path.cash.items():
        if c != "USD":
            net[c] = round(float(arr[i]) * rates[c])
    net = {"USD": -sum(net.values()), **net}
    eq = float(path.equity[i])
    g = float(path.gross_usd[i])
    mm = book["maintenance_margin"] * g
    return {
        "as_of_i": int(i),
        "positions": positions,
        "net_usd_by_ccy": {k: int(v) for k, v in net.items()},
        "leverage": round(g / eq, 2) if eq > 0 else None,
        "margin_buffer_pct": round((eq - mm) / eq * 100.0, 1) if eq > 0 else None,
    }


def stress_test(storms: pd.DataFrame, book_mid: pd.Series, book: dict) -> list[dict]:
    """Apply each labelled storm's onset-to-trough USD move to the book as of just before onset.

    Every leg is long USD, so a USD move of u (bp) earns N x (1 - 1 / (1 + u)) on total
    notional N, whatever the pair. A storm on a pair outside the book is applied as the
    same move in USD (EURUSD inverted). Onset-to-trough is the worst point of the storm.
    """
    n_usd = sum(leg["usd_notional"] for leg in book["legs"])
    symbols = {leg["pair"] for leg in book["legs"]}
    out = []
    for s in storms.itertuples():
        if book_mid[book_mid.index < s.onset_utc].empty:
            continue
        u = s.usd_move_bp / 1e4
        pnl = n_usd * (1.0 - 1.0 / (1.0 + u))
        margin_call = book["equity_usd"] + pnl < book["maintenance_margin"] * n_usd
        when = f"{s.onset_utc:%d %b %H:%M} UTC"
        if s.pair in symbols and usd_sign(s.pair) > 0:
            scenario = f"{s.pair} storm {when}: {s.move_bp:+.0f} bp"
        else:
            scenario = f"{s.pair} storm {when}: {s.move_bp:+.0f} bp, applied as USD {s.usd_move_bp:+.0f} bp"
        out.append({"scenario": scenario, "pnl_usd": round(pnl), "margin_call": bool(margin_call)})
    return out


def max_drawdown(equity: np.ndarray) -> tuple[float, float]:
    """Largest peak-to-trough fall of equity: (USD, % of the peak)."""
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    j = int(dd.argmax())
    return float(dd[j]), float(dd[j] / peak[j] * 100.0) if peak[j] > 0 else 0.0


def aligned_mids(feats: dict[str, pd.DataFrame], pairs, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Mid per pair on the union of their minute bars in [start, end), forward-filled,
    starting at the first minute where every pair has a price."""
    cols = {p: feats[p]["mid"][(feats[p].index >= start) & (feats[p].index < end)] for p in pairs}
    df = pd.DataFrame(cols).sort_index().ffill().dropna()
    if df.empty:
        raise ValueError(f"no common prices for {pairs} in {start} .. {end}")
    return df


def policy_backtest(
    feats: dict[str, pd.DataFrame],
    cfg: dict,
    start: pd.Timestamp,
    end: pd.Timestamp,
    calendar: pd.DataFrame | None = None,
    book: dict = POLICY_BOOK,
) -> dict:
    """Run policy v1 on `book` over [start, end): prepared vs unprepared."""
    calendar = load_calendar() if calendar is None else calendar
    pairs = [leg["pair"] for leg in book["legs"]]
    grid = aligned_mids(feats, pairs, start, end)
    idx = grid.index

    def frame_of(t: pd.Timestamp) -> int:
        return int(idx.searchsorted(t, side="left"))

    events = {}
    for p in pairs:
        res = run_detector(feats[p], calendar, cfg, exposure=leg_exposure(p))
        events[p] = [e for e in res.events if idx[0] <= e["time"] <= idx[-1]]
    actions = policy_actions(events, frame_of)
    mids = {p: grid[p].to_numpy() for p in pairs}
    paths = ships(mids, book, actions)

    out = {"book": {
        "synthetic": True,
        "legs": [f"long USD {leg['usd_notional']:,.0f} via {leg['pair']}"
                 + (" (short EUR)" if leg["pair"] == "EURUSD" else "") for leg in book["legs"]],
        "equity_usd": book["equity_usd"], "maintenance_margin": book["maintenance_margin"],
        "cut_fraction": book["cut_fraction"],
        "from_utc": f"{idx[0]:%Y-%m-%d %H:%M}", "to_utc": f"{idx[-1]:%Y-%m-%d %H:%M}",
    }}
    counts = {t: sum(1 for evs in events.values() for e in evs if e["type"] == t)
              for t in ("alarm", "squall", "fair_wind", "all_clear")}
    out["alerts"] = {"danger_alarms": counts["alarm"], "squalls": counts["squall"],
                     "fair_winds": counts["fair_wind"], "all_clears": counts["all_clear"]}
    for name, path in paths.items():
        dd_usd, dd_pct = max_drawdown(path.equity)
        mc = path.margin_call_i
        out[name] = {
            "final_equity_usd": round(float(path.equity[-1])),
            "max_drawdown_usd": round(dd_usd),
            "max_drawdown_pct": round(dd_pct, 1),
            "margin_calls": 0 if mc is None else 1,
            "margin_call_utc": None if mc is None else f"{idx[mc]:%Y-%m-%d %H:%M}",
            "cuts": len(path.cuts),
            "restores": len(path.restores),
        }
    done = sorted([(i, p, "cut") for i, p in paths["prepared"].cuts]
                  + [(i, p, "restore") for i, p in paths["prepared"].restores])
    out["trades"] = [{"utc": f"{idx[i]:%Y-%m-%d %H:%M}", "pair": p, "action": k} for i, p, k in done]
    return out
