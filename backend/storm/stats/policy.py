"""Action/quote adapters; oracle is always the unchanged production simulator."""
from __future__ import annotations

import ctypes
from dataclasses import dataclass, replace
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

from storm.equity import simulate_stock
from storm.exposure import (Quotes, aligned_quotes, book_for, simulate_book, max_drawdown,
                            policy_actions, leg_exposure, cut_since)
from .randomization import MINUTE, shifted

SUMMARY_FIELDS = ("final_equity_usd", "max_drawdown_usd", "max_drawdown_pct", "margin_calls",
                  "cuts", "restores", "spread_cost_usd", "fills")


@dataclass
class PolicyInput:
    name: str
    pairs: list[str]
    index: pd.DatetimeIndex
    quotes: dict
    book: dict
    stock: bool
    start: pd.Timestamp
    end: pd.Timestamp
    carry_in: bool = False


def inputs_for(unit, window, spread=1, leverage=None, cut_fraction=0.75):
    pairs = sorted(window["pairs"])
    idx, quotes = aligned_quotes(unit.feats, pairs, window["start"], window["end"])
    if spread != 1:
        if unit.stock:
            raise ValueError("Stock acquisition contains no bid/ask quotes")
        quotes = {p: replace(q,
            open_bid=q.open_mid + (q.open_bid - q.open_mid) * spread,
            open_ask=q.open_mid + (q.open_ask - q.open_mid) * spread,
            close_bid=q.mid + (q.close_bid - q.mid) * spread,
            close_ask=q.mid + (q.close_ask - q.mid) * spread) for p, q in quotes.items()}
        if any(np.any(q.open_bid <= 0) or np.any(q.close_bid <= 0) for q in quotes.values()):
            raise ValueError("Spread expansion produces nonpositive quote")
    if unit.stock:
        book = {"synthetic": True, "symbol": pairs[0], "equity_usd": 1_000_000.0,
                "position_usd": 1_000_000.0 * (4 if leverage is None else leverage),
                "maintenance_margin": 0.15, "cut_fraction": cut_fraction}
    else:
        book = book_for(pairs, 1_000_000 * (20 if leverage is None else leverage))
        book["cut_fraction"] = cut_fraction
    return PolicyInput(window["name"], pairs, idx, quotes, book, unit.stock,
                       window["start"], window["end"], window.get("carry_in", False))


def real_actions(inp, detections, delay=1):
    events = {}
    for p in inp.pairs:
        events[p] = [dict(e) for e in detections[p].events if inp.index[0] <= e["time"] <= inp.index[-1]]
        if inp.carry_in:
            since = cut_since(detections[p].events, inp.index[0] + pd.Timedelta(nanoseconds=1))
            if since is not None and since < inp.index[0]:
                events[p].insert(0, {"type": "alarm", "time": inp.index[0], "carry_in": True})
    actions = policy_actions(events, lambda t: int(inp.index.searchsorted(t, side="left")))
    if delay == 1:
        return actions
    # k-th observed traded bar after the signal, applied to cuts AND restores.
    out = []
    for earliest, p, kind in actions:
        candidates = np.flatnonzero(inp.quotes[p].traded[earliest:])
        if len(candidates) >= delay:
            out.append((int(earliest + candidates[delay - 1]), p, kind))
    return sorted(out)


def oracle(inp, actions):
    if inp.stock:
        q = inp.quotes[inp.pairs[0]]
        path = simulate_stock(q.mid, inp.book, actions, q.open_mid, q.traded)
    else:
        path = simulate_book(inp.quotes, inp.book, actions)
    dd, pct = max_drawdown(path.equity)
    return {"final_equity_usd": float(path.equity[-1]), "max_drawdown_usd": dd, "max_drawdown_pct": pct,
            "margin_calls": int(path.margin_call_i is not None), "cuts": len(path.cuts),
            "restores": len(path.restores), "spread_cost_usd": path.spread_cost_usd, "fills": len(path.fills)}


_LIBRARY = None


def native_library():
    global _LIBRARY
    if _LIBRARY is not None:
        return _LIBRARY
    source = Path(__file__).with_name("policy_native.cpp")
    compiler = shutil.which("c++")
    if compiler is None:
        return None
    tag = hashlib.sha256(source.read_bytes()).hexdigest()[:20]
    folder = Path(tempfile.gettempdir()) / ("stormscore-stats-native-" + tag)
    folder.mkdir(exist_ok=True)
    library = folder / "policy.so"
    if not library.exists():
        flags = []
        if sys.platform == "darwin" and shutil.which("xcrun"):
            sdk = subprocess.check_output(["xcrun", "--show-sdk-path"], text=True).strip()
            headers = Path(sdk) / "usr/include/c++/v1"
            if headers.exists():
                flags = ["-isystem", str(headers)]
        try:
            subprocess.run([compiler, "-O3", "-std=c++17", "-shared", "-fPIC", *flags, str(source), "-o", str(library)], check=True,
                           capture_output=True, text=True)
        except subprocess.CalledProcessError:
            return None  # The unchanged Python simulator remains a complete fallback.
    lib = ctypes.CDLL(str(library))
    ints = np.ctypeslib.ndpointer(dtype=np.int32, flags="C_CONTIGUOUS")
    floats = np.ctypeslib.ndpointer(dtype=np.float64, flags="C_CONTIGUOUS")
    lib.simulate_stats.argtypes = [ctypes.c_int] * 4 + [ints, floats] + [floats] * 6 + [ints] * 4 + [ctypes.c_double] * 3 + [floats]
    lib.simulate_stats.restype = ctypes.c_int
    _LIBRARY = lib
    return lib


def batch(inp, schedules):
    """Exact path arithmetic in optional C++; portable fallback calls the oracle."""
    lib = native_library()
    if lib is None:
        return [oracle(inp, actions) for actions in schedules]
    n, p, r = len(inp.index), len(inp.pairs), len(schedules)
    # Different schedules can have a different number of actions (weekly carry-in).
    # Encode pair/kind per slot by extending a shared union of typed slots.
    typed = [(pair, kind) for pair in inp.pairs for kind in ("cut", "restore")]
    max_counts = {t: max((sum((p, k) == t for _, p, k in s) for s in schedules), default=0) for t in typed}
    slots = [t for t in typed for _ in range(max_counts[t])]
    a = len(slots)
    frames = np.full((r, a), -1, np.int32)
    earliest = np.full((r, a), -1, np.int32)
    starts = {}
    cursor = 0
    for t in typed:
        starts[t] = cursor
        cursor += max_counts[t]
    next_traded = {}
    for pair in inp.pairs:
        values = np.where(inp.quotes[pair].traded, np.arange(n), n)
        next_traded[pair] = np.append(np.minimum.accumulate(values[::-1])[::-1], n)
    for trial, actions in enumerate(schedules):
        counters = dict(starts)
        for e, pair, kind in sorted(actions):
            slot = counters[pair, kind]
            counters[pair, kind] += 1
            e = int(e)
            fill = next_traded[pair][min(e, n)]
            if fill < n:
                frames[trial, slot] = fill
                earliest[trial, slot] = e
    action_pairs = np.asarray([inp.pairs.index(pair) for pair, _ in slots], np.int32)
    kinds = np.asarray([int(kind == "restore") for _, kind in slots], np.int32)
    usd_base = np.asarray([int(not inp.stock and pair.startswith("USD")) for pair in inp.pairs], np.int32)
    if inp.stock:
        full = np.asarray([inp.book["position_usd"] / inp.quotes[inp.pairs[0]].mid[0]], float)
    else:
        legs = {leg["pair"]: leg["usd_notional"] for leg in inp.book["legs"]}
        full = np.asarray([legs[pair] * leg_exposure(pair) / (1 if pair.startswith("USD") else inp.quotes[pair].mid[0])
                           for pair in inp.pairs], float)
    arrays = [np.ascontiguousarray([getattr(inp.quotes[pair], name) for pair in inp.pairs], dtype=float)
              for name in ("mid", "open_mid", "open_bid", "open_ask", "close_bid", "close_ask")]
    out = np.empty((r, 9), float)
    status = lib.simulate_stats(n, p, r, a, usd_base, full, *arrays, frames, earliest, action_pairs, kinds,
                               inp.book["equity_usd"], inp.book["maintenance_margin"], inp.book["cut_fraction"], out)
    if status:
        raise RuntimeError("Native policy simulator failed")
    return [{key: float(values[j]) if key not in ("margin_calls", "cuts", "restores", "fills") else int(values[j])
             for j, key in enumerate(SUMMARY_FIELDS)} for values in out]


def null_schedules(inp, trains, offsets, trials=1000):
    schedules = [[] for _ in range(trials)]
    for pair in inp.pairs:
        train = trains[pair]
        starts, clears = shifted(train, offsets[pair][:trials], danger=True)
        starts_ns = train.start.value + starts * MINUTE.value
        clears_ns = train.start.value + clears * MINUTE.value
        idx = inp.index.asi8
        for trial in range(trials):
            events = []
            for a, c, censored in zip(starts_ns[trial], clears_ns[trial], train.danger_censored):
                if inp.carry_in and a < idx[0] <= c:
                    # Carry-in after a real clear exactly at the open follows cut_since's
                    # < before convention: all_clear at the open has already ended it.
                    if c > idx[0]:
                        events.append((0, "cut"))
                elif idx[0] <= a <= idx[-1]:
                    events.append((int(idx.searchsorted(a, side="left")), "cut"))
                if not censored and idx[0] <= c <= idx[-1]:
                    events.append((int(idx.searchsorted(c, side="left")), "restore"))
            # policy_actions is a state machine: an orphan clear never restores.
            cut = False
            for signal, kind in sorted(events, key=lambda row: (row[0], row[1])):
                if kind == "cut" and not cut:
                    schedules[trial].append((signal + 1, pair, kind))
                    cut = True
                elif kind == "restore" and cut:
                    schedules[trial].append((signal + 1, pair, kind))
                    cut = False
    return [sorted(actions) for actions in schedules]


def check_batch(inp, schedules, results):
    """Mandatory real plus representative randomized path checks before inference."""
    checked = []
    for i in sorted(set([0, min(1, len(schedules)-1), len(schedules)//2, len(schedules)-1])):
        expected = oracle(inp, schedules[i])
        for field in SUMMARY_FIELDS:
            if not np.isclose(expected[field], results[i][field], rtol=1e-9, atol=1e-5):
                raise ValueError(f"Native/oracle mismatch {inp.name}/{i}/{field}: {results[i][field]} vs {expected[field]}")
        checked.append(i)
    return {"book": inp.name, "checked_trials": checked, "rtol": 1e-9, "atol_usd": 1e-5, "passed": True}


def totals(books):
    result = {"independent_reset_books": len(books), "synthetic": True,
              "prepared_minus_unprepared_usd": sum(b["prepared"]["final_equity_usd"] - b["unprepared"]["final_equity_usd"] for b in books)}
    for ship in ("prepared", "unprepared"):
        result[ship] = {field: sum(b[ship][field] for b in books) for field in
                        ("margin_calls", "cuts", "restores", "fills", "spread_cost_usd")}
        result[ship]["pnl_usd"] = sum(b[ship]["final_equity_usd"] - 1_000_000 for b in books)
        result[ship]["max_book_drawdown_usd"] = max((b[ship]["max_drawdown_usd"] for b in books), default=None)
        result[ship]["median_book_drawdown_usd"] = float(np.median([b[ship]["max_drawdown_usd"] for b in books])) if books else None
    return result
