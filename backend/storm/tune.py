"""Tune detector v1 on July only.

    python -m storm.tune     -> data/processed/detector_config.json and the top five settings

Only July spot rows are read: the parquet read itself filters on timestamp, so no August
row is loaded, and none can reach the features, the labels or the score.

Objective: maximise July storms caught (alarmed with at least half the move still
ahead), subject to at most one false storm alarm per day across the three pairs.
Ties go to fewer false alarms, then a larger median share of the move ahead, then an
earlier median alarm, then grid order.

squall_on does not change which storm alarms fire (episodes close on the calm run alone),
so it is set afterwards, also on July: the lowest level in SQUALL_LEVELS, from calm_off
up to but below storm_on, with at most MAX_SQUALLS_PER_DAY squall-only episodes per day
across the three pairs (if none qualifies, the highest level below storm_on). During the grid search it sits at calm_off.

The constraint and the ranking use unrounded metrics (storm.evaluate.score); rounding is
applied only to what is printed and written (storm.evaluate.for_display).
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import pandas as pd

from .detector import DEFAULT_CONFIG, load_calendar, risk_frame, run_detector
from .evaluate import for_display, market_days, score, v1_alarms_and_squalls
from .features import PAIRS, add_comove, pair_features
from .labels import label_all
from .paths import PROCESSED_DIR

TUNE_START = pd.Timestamp("2026-07-01", tz="UTC")
TUNE_END = pd.Timestamp("2026-08-01", tz="UTC")   # exclusive
MAX_FALSE_PER_DAY = 1.0
MAX_SQUALLS_PER_DAY = 2.5
SQUALL_LEVELS = [round(0.25 + 0.05 * j, 2) for j in range(16)]   # 0.25 .. 1.0

GRID = {
    "move_windows": [[1], [1, 3, 5]],
    "w_comove": [0.0, 0.15, 0.3],
    "storm_on": [0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    "storm_minutes": [1, 2, 3],
    "calm_off": [0.25, 0.35],
}


def load_split_features(
    processed: Path, start: pd.Timestamp, end: pd.Timestamp, pairs: tuple[str, ...] = PAIRS
) -> dict[str, pd.DataFrame]:
    """Features computed only from spot rows with start <= timestamp < end (filtered on read)."""
    feats = {}
    for p in pairs:
        path = processed / f"{p}_SPOT.parquet"
        if not path.exists():
            raise FileNotFoundError(f"{path} missing; run `python -m storm.ingest` first")
        spot = pd.read_parquet(path, filters=[("timestamp", ">=", start), ("timestamp", "<", end)])
        if len(spot) and not (spot["timestamp"].min() >= start and spot["timestamp"].max() < end):
            raise AssertionError(f"{p}: rows outside {start} .. {end} were read")
        feats[p] = pair_features(spot, p)
    return add_comove(feats)


def grid_configs(grid: dict = GRID, base: dict = DEFAULT_CONFIG) -> list[dict]:
    keys = list(grid)
    out = []
    for values in itertools.product(*(grid[k] for k in keys)):
        cfg = {**base, **dict(zip(keys, values))}
        cfg["squall_on"] = cfg["calm_off"]
        out.append(cfg)
    return out


def rank_key(m: dict) -> tuple:
    return (
        -m["caught"],
        m["false_alarms_per_day"],
        -(m["median_move_ahead_pct"] if m["median_move_ahead_pct"] is not None else -1.0),
        m["median_minutes_to_alarm"] if m["median_minutes_to_alarm"] is not None else 1e9,
    )


def tune(processed: Path = PROCESSED_DIR, grid: dict = GRID, calendar: pd.DataFrame | None = None) -> dict:
    feats = load_split_features(processed, TUNE_START, TUNE_END)
    storms = label_all(feats)
    calendar = load_calendar() if calendar is None else calendar
    days = market_days(feats, TUNE_START, TUNE_END)
    mids = {p: f["mid"] for p, f in feats.items()}

    risk_cache: dict[tuple, dict[str, pd.DataFrame]] = {}
    results = []
    for order, cfg in enumerate(grid_configs(grid)):
        key = (tuple(cfg["move_windows"]), cfg["w_comove"], cfg["comove_min"], cfg["strength_full"])
        if key not in risk_cache:
            risk_cache[key] = {p: risk_frame(f, cfg) for p, f in feats.items()}
        res = {p: run_detector(f, calendar, cfg, rf=risk_cache[key][p]) for p, f in feats.items()}
        alarms, squalls = v1_alarms_and_squalls(res, TUNE_START, TUNE_END)
        m = score(alarms, storms, mids, days, squalls)
        results.append({"order": order, "config": cfg, "metrics": m})

    feasible = [r for r in results if r["metrics"]["false_alarms_per_day"] <= MAX_FALSE_PER_DAY]
    if not feasible:
        raise RuntimeError("no setting in the grid meets the false-alarm limit")
    feasible.sort(key=lambda r: (rank_key(r["metrics"]), r["order"]))
    best = feasible[0]
    cfg = best["config"]
    key = (tuple(cfg["move_windows"]), cfg["w_comove"], cfg["comove_min"], cfg["strength_full"])
    levels = [lv for lv in SQUALL_LEVELS if cfg["calm_off"] <= lv < cfg["storm_on"]] or [cfg["calm_off"]]
    for j, level in enumerate(levels):
        trial = {**cfg, "squall_on": level}
        res = {p: run_detector(f, calendar, trial, rf=risk_cache[key][p]) for p, f in feats.items()}
        alarms, squalls = v1_alarms_and_squalls(res, TUNE_START, TUNE_END)
        if squalls / days <= MAX_SQUALLS_PER_DAY or j == len(levels) - 1:
            m = score(alarms, storms, mids, days, squalls)
            if m["per_storm"] != best["metrics"]["per_storm"] or m["false_alarms"] != best["metrics"]["false_alarms"]:
                raise AssertionError("squall_on changed the storm alarms")
            best = {**best, "config": trial, "metrics": m}
            break
    return {
        "best": best,
        "ranked": feasible,
        "n_settings": len(results),
        "storms": storms,
        "feature_range": {p: (f.index.min(), f.index.max()) for p, f in feats.items()},
        "days": days,
    }


def _row(rank: int, r: dict) -> str:
    c, m = r["config"], r["metrics"]
    ahead = "-" if m["median_move_ahead_pct"] is None else f"{m['median_move_ahead_pct']:.0f}%"
    return (f"{rank:>2}  {str(c['move_windows']):9} {c['w_comove']:5.2f} {c['storm_on']:5.2f} "
            f"{c['storm_minutes']:3d} {c['calm_off']:5.2f}   "
            f"{m['caught']}/{m['storms']}    {m['alarmed']}/{m['storms']}   {ahead:>5}  "
            f"{m['false_alarms_per_day']:6.2f}")


def main() -> None:
    out = tune()
    best = out["best"]
    print(f"tuned on July only: {TUNE_START:%Y-%m-%d} to {TUNE_END - pd.Timedelta(days=1):%Y-%m-%d}, "
          f"{len(out['storms'])} labelled storms, {out['days']:.1f} market days, "
          f"{len(out['ranked'])} of {out['n_settings']} settings within {MAX_FALSE_PER_DAY:g} false alarm/day")
    print("     windows   w_co  storm  k  calm   caught alarmed  ahead  false/d")
    for rank, r in enumerate(out["ranked"][:5], 1):
        print(_row(rank, r))
    print(f"(squall_on sits at calm_off during the search; then the lowest level below storm_on with <= "
          f"{MAX_SQUALLS_PER_DAY:g} squalls/day in July: {best['config']['squall_on']:.2f}, "
          f"{best['metrics']['squalls_per_day']:.2f}/day)")
    print("\nchosen (July):")
    for p in best["metrics"]["per_storm"]:
        when = p["alarm_utc"] or "no alarm"
        ahead = "" if p["move_ahead_pct"] is None else f", {p['move_ahead_pct']:.0f}% ahead, {p['minutes']:+d} min"
        print(f"  {p['storm_id']:22} {when}{ahead}{'  CAUGHT' if p['caught'] else ''}")

    path = PROCESSED_DIR / "detector_config.json"
    shown = for_display(best["metrics"])
    m = {k: v for k, v in shown.items() if k != "per_storm"}
    path.write_text(json.dumps({
        "config": best["config"],
        "tuned_on": f"{TUNE_START:%Y-%m-%d} .. {TUNE_END - pd.Timedelta(days=1):%Y-%m-%d} (July only)",
        "objective": "max storms caught (>= 50% of the move ahead) s.t. <= 1 false storm alarm/day",
        "july_metrics": m,
        "july_per_storm": shown["per_storm"],
    }, indent=2, default=str) + "\n")
    print(f"\nthresholds: {json.dumps(best['config'])}")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
