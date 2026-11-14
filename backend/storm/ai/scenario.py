"""Resize a replay's onset-to-trough path; simulate the synthetic book at mid.

Alarm timings and sea conditions are inherited assumptions, not a new detector run.
No spread or slippage is charged, matching storm.exposure's policy simulator.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re

import numpy as np
import pandas as pd

from storm import exposure
from storm.paths import BUNDLES_DIR
from storm.validate import validate_bundle

DEFAULT_STORM = "usdjpy-2026-07-30"
SYMBOLS = ("USDJPY", "EURUSD", "USDSGD")


def validate_shape(bundle: dict) -> list[str]:
    """Validate every field while CC-L adds the scenario source enum.

    The real bundle always retains source='scenario'. Only the validator's
    input copy uses its existing synthetic enum; never mutate storm.validate.
    """
    candidate = dict(bundle)
    if candidate.get("source") == "scenario":
        candidate["source"] = "synthetic"
    return validate_bundle(candidate)


def parameters(symbol: str, move_pct: float, minutes: int) -> tuple[str, float, int]:
    if not isinstance(symbol, str) or symbol.upper() not in SYMBOLS:
        raise ValueError("symbol must be USDJPY, EURUSD or USDSGD")
    if (isinstance(move_pct, bool) or not isinstance(move_pct, (int, float))
            or not math.isfinite(move_pct) or not -100 < move_pct <= 1000):
        raise ValueError("move_pct must be finite, greater than -100 and at most 1000")
    if type(minutes) is not int or not 1 <= minutes <= 1440:
        raise ValueError("minutes must be a whole number from 1 to 1440")
    return symbol.upper(), float(move_pct), minutes


def load_bundle(storm_id: str, *, bundles_dir: Path | None = None) -> dict:
    if not isinstance(storm_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,159}", storm_id):
        raise ValueError("Invalid storm_id")
    directory = BUNDLES_DIR if bundles_dir is None else Path(bundles_dir)
    path = directory / f"{storm_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Bundle {storm_id!r} is unavailable; export it with python -m storm.export first")
    bundle = json.loads(path.read_text())
    errors = validate_shape(bundle)
    if errors:
        raise ValueError("Invalid base bundle: " + "; ".join(errors))
    return bundle


def book_paths(bundle: dict) -> tuple[dict, dict, dict]:
    """Use the exporter's synthetic book and policy, never a second P&L formula."""
    book = exposure.book_for(bundle["symbol"])
    book["equity_usd"] = bundle["ships"]["prepared"]["start_equity_usd"]
    mids = {bundle["symbol"]: np.asarray(bundle["series"]["mid"], dtype=float)}
    events = {bundle["symbol"]: [dict(e, time=e["i"]) for e in bundle["events"]]}
    actions = exposure.policy_actions(events, int)
    return book, mids, exposure.ships(mids, book, actions)


def stress_test(symbol: str, move_pct: float, minutes: int) -> dict:
    """Endpoint stress on the default synthetic book, before liquidation/policy cuts."""
    symbol, move_pct, minutes = parameters(symbol, move_pct, minutes)
    book = exposure.book_for(symbol)
    ratio = 1 + move_pct / 100
    # exposure.stress_test expects a USD move: invert EURUSD exactly.
    usd_move_bp = (ratio - 1 if symbol.startswith("USD") else 1 / ratio - 1) * 10_000
    onset = pd.Timestamp("1970-01-01T00:01:00Z")
    storms = pd.DataFrame([{"pair": symbol, "onset_utc": onset,
                            "move_bp": move_pct * 100, "usd_move_bp": usd_move_bp}])
    before = pd.Series([1.0], index=[onset - pd.Timedelta(minutes=1)])
    result = exposure.stress_test(storms, before, book)[0]
    result["scenario"] = f"{symbol} {move_pct:+g}% in {minutes} min"
    return {"symbol": symbol, "move_pct": move_pct, "minutes": minutes,
            "book_is_synthetic": True, "start_equity_usd": book["equity_usd"],
            "notional_usd": sum(leg["usd_notional"] for leg in book["legs"]),
            "assumptions": "Endpoint stress before liquidation; no spread or slippage; duration does not change endpoint P&L",
            **result}


def scenario(symbol: str = "USDJPY", move_pct: float = -3, minutes: int = 30,
             base_storm_id: str = DEFAULT_STORM, *, base_bundle: dict | None = None) -> dict:
    """Return a validated scenario bundle without changing or writing the base.

    The new replay starts at the base onset and ends at its trough. Interpolating
    cumulative log returns is equivalent to scaling and resampling log increments.
    A supplied synthetic fixture stays explicitly synthetic in the title.
    """
    symbol, move_pct, minutes = parameters(symbol, move_pct, minutes)
    base = deepcopy(base_bundle) if base_bundle is not None else load_bundle(base_storm_id)
    errors = validate_bundle(base)
    if errors:
        raise ValueError("Invalid base bundle: " + "; ".join(errors))
    if base["source"] not in {"sgx", "synthetic"}:
        raise ValueError("Use a real replay or an explicitly synthetic fixture as the base")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,100}", base["storm_id"]):
        raise ValueError("Base storm_id cannot be used as a scenario filename")
    if base["symbol"] != symbol:
        raise ValueError("Scenario symbol must match the base bundle symbol")
    onset, trough = base["storm"]["onset_i"], base["storm"]["trough_i"]
    if not 0 <= onset < trough < base["n"]:
        raise ValueError("Base must have onset before trough")
    source = np.asarray(base["series"]["mid"][onset:trough + 1], dtype=float)
    if not np.all(np.isfinite(source)) or np.any(source <= 0):
        raise ValueError("Base prices must be positive and finite")
    log_path = np.log(source / source[0])
    if abs(log_path[-1]) < 1e-12:
        raise ValueError("Base onset-to-trough move cannot be zero")
    old_grid = np.arange(len(source))
    new_grid = np.linspace(0, len(source) - 1, minutes + 1)
    scaled = np.interp(new_grid, old_grid, log_path) * (math.log1p(move_pct / 100) / log_path[-1])
    mid = np.round(source[0] * np.exp(scaled), 5)
    if np.any(mid <= 0):
        raise ValueError("Scenario prices are too small at replay precision")
    actual_move_bp = (mid[-1] / mid[0] - 1) * 10_000
    if abs(actual_move_bp - move_pct * 100) > 1:
        raise ValueError("Scenario move loses too much precision at replay price rounding")
    opening = np.r_[mid[0], mid[:-1]]
    n = minutes + 1

    def frame(i):
        return max(0, min(minutes, int(math.floor((i - onset) * minutes / (trough - onset) + .5))))

    # Retain policy history so a cut before onset becomes an assumed cut at the
    # scenario start. Strip all old text/MCs: those describe the historical path.
    events = []
    for event in base["events"]:
        kind = event["type"]
        if event["i"] > trough or kind not in {"alarm", "all_clear"}:
            continue
        i = frame(event["i"])
        ev = {"i": i, "type": kind, "text": f"Assumed {kind.replace('_', ' ')} timing from the base replay"}
        if kind == "alarm":
            ev["move_ahead_pct"] = (round(float((mid[-1] - mid[i]) / (mid[-1] - mid[0]) * 100), 1)
                                     if mid[-1] != mid[0] else None)
        events.append(ev)
    events.sort(key=lambda e: e["i"])
    date = datetime.fromtimestamp(base["t0"] + onset * 60, timezone.utc)
    shape = f"{date.day} {date:%B}" if base["source"] == "sgx" else "synthetic replay"
    move_tag = f"{move_pct:+g}".replace("+", "up").replace("-", "down").replace(".", "p")
    bundle = {
        "schema_version": 1, "storm_id": f"scenario-{base['storm_id']}-{move_tag}-{minutes}m",
        "title": f"What if: {symbol} {move_pct:+g}% in {minutes} min (shaped like {shape})",
        "symbol": symbol, "asset_class": "fx", "source": "scenario", "book_is_synthetic": True,
        "t0": int(date.timestamp()), "step_s": 60, "n": n,
        "storm": {"onset_i": 0, "trough_i": minutes, "move_bp": round(float(actual_move_bp), 4),
                  "kind": base["storm"]["kind"], "label": f"{move_pct:+g}% in {minutes} min"},
        "series": {"mid": mid.tolist(), "open": opening.tolist(),
                   "high": np.maximum(opening, mid).tolist(), "low": np.minimum(opening, mid).tolist()},
        "ships": deepcopy(base["ships"]), "events": events, "exposure": {}, "stress": [], "report": None,
    }
    # Sea conditions are resampled base assumptions; no predictive risk signal.
    for key in ("spread_bp", "vol_ratio", "risk", "state", "jump"):
        values = base["series"][key][onset:trough + 1]
        if key in {"state", "jump"}:
            bundle["series"][key] = [int(values[int(math.floor(i + .5))]) for i in new_grid]
        else:
            bundle["series"][key] = np.round(np.interp(new_grid, old_grid, values), 2).tolist()
    book, mids, paths = book_paths(bundle)
    for name, path in paths.items():
        bundle["series"][f"{name}_equity"] = [round(float(v)) for v in path.equity]
        bundle["ships"][name] = {
            "label": "Followed the assumed alarm" if name == "prepared" else "Held the position",
            "start_equity_usd": book["equity_usd"], "margin_call_i": path.margin_call_i,
            "cut_i": path.cut_i, "cut_fraction": path.cut_fraction, "restore_i": path.restore_i,
        }
        if path.margin_call_i is not None:
            events.append({"i": path.margin_call_i, "type": "margin_call", "ship": name,
                           "text": "Scenario margin call: position closed"})
    for i, _ in paths["prepared"].cuts:
        events.append({"i": i, "type": "cut", "text": "Prepared ship reduces exposure at the assumed alarm"})
    for i, _ in paths["prepared"].restores:
        events.append({"i": i, "type": "restore", "text": "Prepared ship restores exposure at the assumed all clear"})
    events.sort(key=lambda e: e["i"])
    bundle["exposure"] = exposure.exposure_snapshot(paths["unprepared"], mids, book, 0)
    stress = stress_test(symbol, move_pct, minutes)
    bundle["stress"] = [{key: stress[key] for key in ("scenario", "pnl_usd", "margin_call")}]
    errors = validate_shape(bundle)
    if errors:
        raise ValueError("Scenario failed storm.validate: " + "; ".join(errors))
    return bundle
