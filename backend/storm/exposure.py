"""Synthetic trader books, the two ships, policy v1 and the stress test.

THE BOOKS ARE SYNTHETIC. No real trader, account or position is represented.

A book is USD equity plus spot legs, each long USD against one currency (USDJPY and
USDSGD: long the pair; EURUSD: short EUR). The book already holds its legs at the
replay's first frame, booked at that frame's mid (a starting position, not a trade).
Cash is kept per currency and marked at mid, so a trade's realised P&L stays in the
currency it was made in.

Execution (every trade after the start)
  A signal is read from bar t's close, so its trade fills at the open of the next bar
  that has a real quote (t+1 unless that minute is missing or the market is closed).
  An action's frame is the earliest bar it may fill on: policy_actions schedules each
  signal for the bar after it, and simulate_book fills it on the first traded bar from
  that frame on.
  Fills are side-correct: buying the base currency pays the ask, selling it gets the bid.
  A cut of a long-USD leg sells USD (USDJPY, USDSGD: sells the pair at the open bid;
  EURUSD: buys EUR back at the open ask); a restore does the opposite. Every fill records
  its price, the mid of the same quote and its cost versus mid in USD
  (|qty| x |price - mid|, converted at mid). Data without quotes (plain mid arrays, Yahoo
  bars) fill at the next open with no spread: cost 0, which is not a measured cost.

Margin (minute i, in this order)
  1. mark the book at bar i's open mid and test maintenance, before any trade in that
     minute: a breach is a margin call at the open
  2. fill the voluntary trades scheduled for this minute (policy cuts and restores)
  3. mark at bar i's close mid and test maintenance again
  A breach at the alarm bar's close is therefore a margin call even if a cut was
  scheduled for the next bar. Maintenance is a share of the open notional (gross, marked
  at mid, in USD). A margin call closes every leg side-correct at that point's bid or ask
  (a leg with no bar that minute closes at its last quotes), converts every currency
  balance to USD at mid, and holds equity flat afterwards (one margin call ends the book).

Policy v1 (the prepared ship), per leg:
  storm-level danger alarm   cut the leg by `cut_fraction` (75%)
  all-clear after a cut      restore the leg to its full size (skipped if, spread
                             included, restoring would put the book straight into a
                             margin call)
  squall                     no trade (the lighthouse goes amber)
  fair wind                  no trade
The unprepared ship holds throughout.

Stress (stress_menu, stress_scenarios): the replay's own book as it stands at the exposure
snapshot (the unprepared ship's cash and legs at as_of_i), shocked by each storm whose
trough came before the snapshot, with the storms labelled on the history available at the
snapshot (storm.labels.label_as_of: bars stamped at or before it). Point in time on both
counts: a later price can neither add a scenario nor remove one, even where the full-history
labels would merge an earlier move into a later storm (6-hour merge). An empty menu when
none qualifies. A storm's USD move u (unrounded, from its onset and
trough mids) is applied to every leg (USDxxx mid x (1 + u), EURUSD mid / (1 + u)), and
the book is revalued with the simulator's own valuation: equity at the shocked mids and
the margin test against maintenance x gross at the shocked mids (marked notional, so a
EURUSD leg's notional moves with the price). It applies no cuts and no path.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .detector import load_calendar, run_detector
from .features import usd_sign
from .labels import label_as_of

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


# ---------------------------------------------------------------- quotes

@dataclass
class Quotes:
    """One pair's prices per frame. The book is marked at mid; trades fill at bid or ask."""
    mid: np.ndarray           # close mid: the mark
    open_mid: np.ndarray
    open_bid: np.ndarray
    open_ask: np.ndarray
    close_bid: np.ndarray
    close_ask: np.ndarray
    traded: np.ndarray        # bool: the frame has a real bar (fills only happen on one)

    def __len__(self) -> int:
        return len(self.mid)

    @classmethod
    def from_mid(cls, mid) -> "Quotes":
        """Mid closes only: each bar opens at the previous close, with no spread."""
        mid = np.asarray(mid, dtype=float)
        prev = np.concatenate([mid[:1], mid[:-1]])
        return cls(mid, prev, prev, prev, mid, mid, np.ones(len(mid), dtype=bool))

    @classmethod
    def from_frame(cls, g: pd.DataFrame, traded=None) -> "Quotes":
        """From a frame with `mid` and, when present, `open` and the bid/ask quote columns.
        On a frame that is not traded every open price is that frame's (held) close."""
        mid = g["mid"].to_numpy(dtype=float)
        traded = np.ones(len(mid), dtype=bool) if traded is None else np.asarray(traded, dtype=bool)
        prev = np.concatenate([mid[:1], mid[:-1]])
        open_mid = g["open"].to_numpy(dtype=float) if "open" in g else prev

        def col(name, fallback):
            return g[name].to_numpy(dtype=float) if name in g else fallback

        close_bid, close_ask = col("close_bid", mid), col("close_ask", mid)
        open_bid, open_ask = col("open_bid", open_mid), col("open_ask", open_mid)
        open_mid = np.where(traded, open_mid, mid)
        open_bid = np.where(traded, open_bid, close_bid)
        open_ask = np.where(traded, open_ask, close_ask)
        return cls(mid, open_mid, open_bid, open_ask, close_bid, close_ask, traded)


def as_quotes(x) -> Quotes:
    return x if isinstance(x, Quotes) else Quotes.from_mid(x)


def _usd_rate(ccy: str, legs: list[str], px: dict[str, float]) -> float:
    """USD per unit of `ccy` at the leg prices `px` (pair -> mid)."""
    if ccy == "USD":
        return 1.0
    for p in legs:
        base, quote = _ccys(p)
        if base == ccy and quote == "USD":
            return px[p]
        if base == "USD" and quote == ccy:
            return 1.0 / px[p]
    raise ValueError(f"no USD rate for {ccy}")


def book_value(cash: dict[str, float], qty: dict[str, float], px: dict[str, float]) -> tuple[float, float]:
    """(equity, gross) in USD at the leg mids `px`: the one valuation every caller uses."""
    legs = list(qty)
    eq = sum(v * _usd_rate(c, legs, px) for c, v in cash.items())
    gross = sum(abs(q) * _usd_rate(_ccys(p)[0], legs, px) for p, q in qty.items())
    return eq, gross


def shocked_prices(px: dict[str, float], usd_move: float) -> dict[str, float]:
    """Every leg's mid after USD moves by `usd_move` (a fraction) against its other currency."""
    return {p: m * (1.0 + usd_move) if _ccys(p)[0] == "USD" else m / (1.0 + usd_move) for p, m in px.items()}


# ---------------------------------------------------------------- the simulator

@dataclass
class BookPath:
    equity: np.ndarray                     # USD equity per minute (marked at the close mid)
    gross_usd: np.ndarray                  # open notional per minute, USD
    qty: dict[str, np.ndarray]             # base-currency position per leg per minute
    cash: dict[str, np.ndarray]            # cash per currency per minute
    margin_call_i: int | None
    cuts: list[tuple[int, str]] = field(default_factory=list)       # (fill frame, pair)
    restores: list[tuple[int, str]] = field(default_factory=list)   # (fill frame, pair)
    cut_fraction: float = 0.0
    fills: list[dict] = field(default_factory=list)   # every trade after the start (module doc)

    @property
    def cut_i(self) -> int | None:
        return self.cuts[0][0] if self.cuts else None

    @property
    def restore_i(self) -> int | None:
        first = self.cut_i
        later = [i for i, _ in self.restores if first is not None and i >= first]
        return later[0] if later else None

    @property
    def spread_cost_usd(self) -> float:
        return float(sum(f["cost_usd"] for f in self.fills))


def fill_frame(traded: np.ndarray, earliest: int) -> int | None:
    """The first frame from `earliest` on with a real bar, or None (no fill in the replay)."""
    if earliest < 1:
        raise ValueError("a trade can fill at frame 1 at the earliest (frame 0 opens the book)")
    later = np.flatnonzero(np.asarray(traded[earliest:], dtype=bool))
    return int(earliest + later[0]) if len(later) else None


def simulate_book(mids: dict, book: dict, actions: list[tuple[int, str, str]] = ()) -> BookPath:
    """Equity per minute of `book`. `mids`: pair -> Quotes, or an array of close mids (no
    spread). actions: (earliest fill frame, pair, "cut" | "restore"); each fills on the
    first traded frame from there (fill_frame). A fill's signal_i is that frame - 1."""
    quotes = {p: as_quotes(v) for p, v in mids.items()}
    n = None
    for p, q in quotes.items():
        for name in ("mid", "open_mid", "open_bid", "open_ask", "close_bid", "close_ask"):
            arr = getattr(q, name)
            if not np.all(np.isfinite(arr)) or np.any(arr <= 0):
                raise ValueError(f"{p}: {name} must be finite and positive")
        if n is not None and len(q) != n:
            raise ValueError("mids must be aligned")
        n = len(q)
    legs = [leg["pair"] for leg in book["legs"]]
    ccys = sorted({"USD"} | {c for p in legs for c in _ccys(p)})

    def px(i: int, where: str) -> dict[str, float]:
        return {p: float(quotes[p].open_mid[i] if where == "open" else quotes[p].mid[i]) for p in legs}

    cash = {c: 0.0 for c in ccys}
    cash["USD"] = book["equity_usd"]
    full, qty = {}, {}
    start = px(0, "close")
    for leg in book["legs"]:
        p = leg["pair"]
        base, quote = _ccys(p)
        full[p] = leg["usd_notional"] * leg_exposure(p) / _usd_rate(base, legs, start)
        cash[base] += full[p]
        cash[quote] -= full[p] * start[p]
        qty[p] = full[p]

    mm, frac = book["maintenance_margin"], book["cut_fraction"]
    by_fill: dict[int, list[tuple[int, str, str]]] = {}
    for s, p, kind in sorted(actions):
        f = fill_frame(quotes[p].traded, int(s))
        if f is not None:
            by_fill.setdefault(f, []).append((int(s) - 1, p, kind))

    fills: list[dict] = []
    cuts, restores = [], []
    margin_call_i = None

    def quote(p: str, i: int, where: str) -> tuple[float, float, float]:
        q = quotes[p]
        if where == "open":
            return float(q.open_bid[i]), float(q.open_ask[i]), float(q.open_mid[i])
        return float(q.close_bid[i]), float(q.close_ask[i]), float(q.mid[i])

    def apply(c: dict, qy: dict, p: str, target: float, price: float) -> float:
        base, quote_ccy = _ccys(p)
        dq = target - qy[p]
        c[base] += dq
        c[quote_ccy] -= dq * price
        qy[p] = target
        return dq

    def trade(p: str, target: float, i: int, where: str, signal_i: int, action: str) -> None:
        bid, ask, mid = quote(p, i, where)
        dq = target - qty[p]
        if dq == 0:
            return
        price = ask if dq > 0 else bid
        apply(cash, qty, p, target, price)
        rate = _usd_rate(_ccys(p)[1], legs, px(i, where))
        fills.append({"i": i, "signal_i": signal_i, "pair": p, "action": action, "at": where,
                      "side": "buy" if dq > 0 else "sell", "qty": abs(dq), "price": price, "mid": mid,
                      "cost_usd": abs(dq) * abs(price - mid) * rate})

    def breached(where: str, i: int) -> bool:
        eq, g = book_value(cash, qty, px(i, where))
        return g > 0 and eq < mm * g

    def margin_call(i: int, where: str) -> None:
        nonlocal margin_call_i
        for p in legs:
            trade(p, 0.0, i, where, i, "margin_call")
        eq, _ = book_value(cash, qty, px(i, where))
        for c in ccys:
            cash[c] = 0.0
        cash["USD"] = eq
        margin_call_i = i

    eq_out, gross_out = np.empty(n), np.empty(n)
    qty_out = {p: np.empty(n) for p in legs}
    cash_out = {c: np.empty(n) for c in ccys}
    for i in range(n):
        if margin_call_i is None and i > 0:
            if breached("open", i):
                margin_call(i, "open")
            else:
                for s, p, kind in by_fill.get(i, []):
                    if kind == "cut" and qty[p] == full[p] and frac > 0:
                        trade(p, full[p] * (1.0 - frac), i, "open", s, "cut")
                        cuts.append((i, p))
                    elif kind == "restore" and qty[p] != full[p]:
                        bid, ask, _ = quote(p, i, "open")
                        c2, q2 = dict(cash), dict(qty)
                        apply(c2, q2, p, full[p], ask if full[p] > qty[p] else bid)
                        eq2, g2 = book_value(c2, q2, px(i, "open"))
                        if eq2 >= mm * g2:
                            trade(p, full[p], i, "open", s, "restore")
                            restores.append((i, p))
        if margin_call_i is None and breached("close", i):
            margin_call(i, "close")
        eq, g = book_value(cash, qty, px(i, "close"))
        eq_out[i], gross_out[i] = eq, g
        for p in legs:
            qty_out[p][i] = qty[p]
        for c in ccys:
            cash_out[c][i] = cash[c]
    return BookPath(eq_out, gross_out, qty_out, cash_out, margin_call_i, cuts, restores,
                    frac if cuts else 0.0, fills)


def policy_actions(events: dict[str, list[dict]], frame_of) -> list[tuple[int, str, str]]:
    """Policy v1 actions from book-aware detector events per pair (time -> frame via
    frame_of). A signal on bar t (its close) is scheduled for bar t + 1: (t + 1, pair, kind)."""
    out = []
    for p, evs in events.items():
        cut = False
        for e in evs:
            if e["type"] == "alarm" and not cut:
                out.append((frame_of(e["time"]) + 1, p, "cut"))
                cut = True
            elif e["type"] == "all_clear" and cut:
                out.append((frame_of(e["time"]) + 1, p, "restore"))
                cut = False
    return sorted(out)


def ships(mids: dict, book: dict, actions) -> dict[str, BookPath]:
    return {"prepared": simulate_book(mids, book, actions), "unprepared": simulate_book(mids, book, [])}


def exposure_snapshot(path: BookPath, mids: dict, book: dict, i: int) -> dict:
    """The book as it stands at minute i (contract `exposure` object)."""
    mids = {p: as_quotes(v).mid for p, v in mids.items()}
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


# ---------------------------------------------------------------- stress

def usd_move(storm) -> float:
    """The storm's onset-to-trough USD move as a fraction, unrounded (EURUSD inverted)."""
    r = storm.trough_mid / storm.onset_mid
    return r - 1.0 if usd_sign(storm.pair) > 0 else 1.0 / r - 1.0


def _scenario_text(storm, symbols: set[str], u: float) -> str:
    when = f"{storm.onset_utc:%d %b %H:%M} UTC"
    move = (storm.trough_mid / storm.onset_mid - 1.0) * 1e4 if hasattr(storm, "trough_mid") else storm.move_bp
    if storm.pair in symbols and usd_sign(storm.pair) > 0:
        return f"{storm.pair} storm {when}: {move:+.0f} bp"
    return f"{storm.pair} storm {when}: {move:+.0f} bp, applied as USD {u * 1e4:+.0f} bp"


def _shock(cash: dict, qty: dict, px: dict, mm: float, u: float) -> tuple[float, bool]:
    """(P&L, margin call) of the holdings `cash`, `qty` when USD moves by u from mids `px`."""
    eq0, _ = book_value(cash, qty, px)
    eq1, g1 = book_value(cash, qty, shocked_prices(px, u))
    return eq1 - eq0, bool(g1 > 0 and eq1 < mm * g1)


def stress_menu(feats: dict[str, pd.DataFrame], calendar: pd.DataFrame, path: BookPath, mids: dict,
                book: dict, i: int, as_of: pd.Timestamp) -> list[dict]:
    """The replay's stress menu (module doc): storms labelled on the bars up to `as_of`
    (label_as_of), then stress_scenarios. This is the point-in-time entry point."""
    return stress_scenarios(label_as_of(feats, as_of, calendar), path, mids, book, i, as_of)


def stress_scenarios(storms: pd.DataFrame, path: BookPath, mids: dict, book: dict, i: int,
                     as_of: pd.Timestamp) -> list[dict]:
    """Storms with trough < `as_of`, applied to the holdings of `path` at frame i through the
    simulator's valuation and margin test. `storms` must be labelled on the history up to
    `as_of` (stress_menu does that); full-history labels are not point in time."""
    legs = [leg["pair"] for leg in book["legs"]]
    px = {p: float(as_quotes(mids[p]).mid[i]) for p in legs}
    cash = {c: float(a[i]) for c, a in path.cash.items()}
    qty = {p: float(path.qty[p][i]) for p in legs}
    known = storms[storms["trough_utc"] < as_of]
    out = []
    for s in known.itertuples():
        u = usd_move(s)
        pnl, mc = _shock(cash, qty, px, book["maintenance_margin"], u)
        out.append({"scenario": _scenario_text(s, set(legs), u), "pnl_usd": round(pnl), "margin_call": mc})
    return out


def stress_test(storms: pd.DataFrame, book_mid: pd.Series, book: dict) -> list[dict]:
    """Endpoint stress of a freshly opened `book` (storm.ai's navigator uses this): each
    storm's USD move (`usd_move_bp`, as given) applied through the same valuation and margin
    test as stress_scenarios. A storm is used when `book_mid` has a price before its onset.
    The result does not depend on the price level, so every leg opens at 1.0."""
    legs = [leg["pair"] for leg in book["legs"]]
    fresh = simulate_book({p: np.array([1.0]) for p in legs}, book)
    cash = {c: float(a[0]) for c, a in fresh.cash.items()}
    qty = {p: float(fresh.qty[p][0]) for p in legs}
    out = []
    for s in storms.itertuples():
        if book_mid[book_mid.index < s.onset_utc].empty:
            continue
        u = s.usd_move_bp / 1e4
        pnl, mc = _shock(cash, qty, {p: 1.0 for p in legs}, book["maintenance_margin"], u)
        when = f"{s.onset_utc:%d %b %H:%M} UTC"
        if s.pair in set(legs) and usd_sign(s.pair) > 0:
            scenario = f"{s.pair} storm {when}: {s.move_bp:+.0f} bp"
        else:
            scenario = f"{s.pair} storm {when}: {s.move_bp:+.0f} bp, applied as USD {s.usd_move_bp:+.0f} bp"
        out.append({"scenario": scenario, "pnl_usd": round(pnl), "margin_call": mc})
    return out


# ---------------------------------------------------------------- policy backtest

def max_drawdown(equity: np.ndarray) -> tuple[float, float]:
    """(largest dollar fall from a running peak, largest percentage fall from a running
    peak), each maximised on its own: the two can come from different peaks."""
    equity = np.asarray(equity, dtype=float)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    pct = np.where(peak > 0, dd / np.where(peak > 0, peak, 1.0) * 100.0, 0.0)
    return float(dd.max()), float(pct.max())


def aligned_quotes(feats: dict[str, pd.DataFrame], pairs, start: pd.Timestamp,
                   end: pd.Timestamp) -> tuple[pd.DatetimeIndex, dict[str, Quotes]]:
    """Quotes per pair on the union of their minute bars in [start, end), from the first
    minute at which every pair has had a bar. A pair without a bar that minute holds its
    last quotes and cannot trade (Quotes.traded)."""
    parts = {p: feats[p][(feats[p].index >= start) & (feats[p].index < end)] for p in pairs}
    if any(f.empty for f in parts.values()):
        raise ValueError(f"no common prices for {tuple(pairs)} in {start} .. {end}")
    union = None
    for f in parts.values():
        union = f.index if union is None else union.union(f.index)
    first = max(f.index[0] for f in parts.values())
    keep = union >= first
    idx = union[keep]
    out = {}
    for p, f in parts.items():
        g = f.reindex(union)
        traded = g["mid"].notna().to_numpy()
        g = g.ffill()
        out[p] = Quotes.from_frame(g[keep], traded[keep])
    return idx, out


def aligned_mids(feats: dict[str, pd.DataFrame], pairs, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Close mid per pair on the aligned grid of aligned_quotes."""
    idx, q = aligned_quotes(feats, pairs, start, end)
    return pd.DataFrame({p: q[p].mid for p in pairs}, index=idx)


def policy_backtest(
    feats: dict[str, pd.DataFrame],
    cfg: dict,
    start: pd.Timestamp,
    end: pd.Timestamp,
    calendar: pd.DataFrame | None = None,
    book: dict = POLICY_BOOK,
) -> dict:
    """Run policy v1 on `book` over [start, end): prepared vs unprepared. Unrounded."""
    calendar = load_calendar() if calendar is None else calendar
    pairs = [leg["pair"] for leg in book["legs"]]
    idx, quotes = aligned_quotes(feats, pairs, start, end)

    def frame_of(t: pd.Timestamp) -> int:
        return int(idx.searchsorted(t, side="left"))

    events = {}
    for p in pairs:
        res = run_detector(feats[p], calendar, cfg, exposure=leg_exposure(p))
        events[p] = [e for e in res.events if idx[0] <= e["time"] <= idx[-1]]
    actions = policy_actions(events, frame_of)
    paths = ships(quotes, book, actions)

    out = {"book": {
        "synthetic": True,
        "legs": [f"long USD {leg['usd_notional']:,.0f} via {leg['pair']}"
                 + (" (short EUR)" if leg["pair"] == "EURUSD" else "") for leg in book["legs"]],
        "equity_usd": book["equity_usd"], "maintenance_margin": book["maintenance_margin"],
        "cut_fraction": book["cut_fraction"],
        "from_utc": f"{idx[0]:%Y-%m-%d %H:%M}", "to_utc": f"{idx[-1]:%Y-%m-%d %H:%M}",
        "execution": "signal at bar t's close, fill at the next bar's open, bid or ask (side-correct)",
    }}
    counts = {t: sum(1 for evs in events.values() for e in evs if e["type"] == t)
              for t in ("alarm", "squall", "fair_wind", "all_clear")}
    out["alerts"] = {"danger_alarms": counts["alarm"], "squalls": counts["squall"],
                     "fair_winds": counts["fair_wind"], "all_clears": counts["all_clear"]}
    for name, path in paths.items():
        dd_usd, dd_pct = max_drawdown(path.equity)
        mc = path.margin_call_i
        out[name] = {
            "final_equity_usd": float(path.equity[-1]),
            "max_drawdown_usd": dd_usd,
            "max_drawdown_pct": dd_pct,
            "margin_calls": 0 if mc is None else 1,
            "margin_call_utc": None if mc is None else f"{idx[mc]:%Y-%m-%d %H:%M}",
            "cuts": len(path.cuts),
            "restores": len(path.restores),
            "fills": len(path.fills),
            "spread_cost_usd": path.spread_cost_usd,
        }
    out["trades"] = [{"utc": f"{idx[f['i']]:%Y-%m-%d %H:%M}", "signal_utc": f"{idx[f['signal_i']]:%Y-%m-%d %H:%M}",
                      "pair": f["pair"], "action": f["action"], "side": f["side"], "at": f["at"],
                      "fill_price": f["price"], "mid_price": f["mid"], "cost_usd": f["cost_usd"]}
                     for f in paths["prepared"].fills]
    return out
