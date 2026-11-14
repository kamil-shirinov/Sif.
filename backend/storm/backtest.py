"""Backtest on August only: detector v1 (tuned on July) vs v0 vs a naive baseline,
and policy v1 on the synthetic three-pair book.

    python -m storm.backtest     -> data/processed/metrics.json and printed tables

Features use trailing windows only, so July bars serve as warm-up history for the
24-hour volatility; every storm, alarm and trade scored here is in August.

Methods (all direction-agnostic: a storm is a storm on either side)
  v1     storm.detector with data/processed/detector_config.json (tuned on July)
  v0     storm.detector_v0 with its hand-set thresholds
  naive  alarms on the first minute the 15-minute move already exceeds the storm
         threshold (the labelling rule); re-arms after 20 minutes without a trigger
Scoring: storm.evaluate. Squalls per day are v1's squall-only episodes on any pair.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import detector_v0
from .detector import CONFIG_PATH, load_calendar, load_config, run_detector
from .evaluate import market_days, score, v1_alarms_and_squalls
from .exposure import policy_backtest
from .features import PAIRS, build_features
from .labels import label_all, window_moves
from .paths import PROCESSED_DIR

TEST_START = pd.Timestamp("2026-08-01", tz="UTC")
TEST_END = pd.Timestamp("2026-09-01", tz="UTC")   # exclusive
SPLIT = "test: August 2026"
NAIVE_REARM_MINUTES = 20


def naive_alarms(feat: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.Timestamp | None]]:
    trig = window_moves(feat)["trigger"].to_numpy()
    idx = feat.index
    out, active, quiet, start = [], False, 0, None
    for i, hit in enumerate(trig):
        if hit:
            quiet = 0
            if not active:
                active, start = True, idx[i]
        elif active:
            quiet += 1
            if quiet >= NAIVE_REARM_MINUTES:
                out.append((start, idx[i]))
                active = False
    if active:
        out.append((start, None))
    return out


def v0_alarms(feat: pd.DataFrame, calendar: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.Timestamp | None]]:
    _, events = detector_v0.run_detector(feat, calendar)
    out, start = [], None
    for e in events:
        if e["type"] == "alarm":
            start = e["time"]
        elif e["type"] == "all_clear" and start is not None:
            out.append((start, e["time"]))
            start = None
    if start is not None:
        out.append((start, None))
    return out


def in_split(alarms: list, start=TEST_START, end=TEST_END) -> list:
    return [(a, c) for a, c in alarms if start <= a < end]


def run_backtest(processed: Path = PROCESSED_DIR, calendar: pd.DataFrame | None = None) -> dict:
    cfg = load_config()
    calendar = load_calendar() if calendar is None else calendar
    feats = build_features(processed, PAIRS)
    storms_all = label_all(feats)
    storms = storms_all[(storms_all["onset_utc"] >= TEST_START) & (storms_all["onset_utc"] < TEST_END)]
    days = market_days(feats, TEST_START, TEST_END)
    mids = {p: f["mid"] for p, f in feats.items()}

    v1 = {p: run_detector(f, calendar, cfg) for p, f in feats.items()}
    v1_alarms, v1_squalls = v1_alarms_and_squalls(v1, TEST_START, TEST_END)
    methods = {
        "v1": score(v1_alarms, storms, mids, days, v1_squalls),
        "v0": score({p: in_split(v0_alarms(f, calendar)) for p, f in feats.items()}, storms, mids, days),
        "naive": score({p: in_split(naive_alarms(f)) for p, f in feats.items()}, storms, mids, days),
    }
    storm_minutes = sum(int((r.frame["state"].to_numpy() == 2)[(f.index >= TEST_START) & (f.index < TEST_END)].sum())
                        for r, f in zip(v1.values(), feats.values()))
    methods["v1"]["storm_state_share_pct"] = round(storm_minutes / (days * 1440 * len(PAIRS)) * 100, 2)

    policy = policy_backtest(feats, cfg, TEST_START, TEST_END, calendar)
    saved = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
    return {
        "split": SPLIT,
        "tuned_on": saved.get("tuned_on", "untuned DEFAULT_CONFIG"),
        "config": cfg,
        "definitions": {
            "caught": "storm alarmed with >= 50% of the onset-to-trough move still ahead",
            "alarmed": "an alarm on the storm's pair from onset - 60 min to the trough, in force at onset",
            "false_alarm": "storm alarm outside [onset - 60 min, end + 60 min] of every storm on its pair",
            "per_day": "per 1,440 minutes with a bar on any pair",
            "direction": "detection metrics ignore direction; policy uses the book's exposure",
        },
        "methods": methods,
        "policy": policy,
    }


def index_metrics(metrics: dict) -> dict:
    """The contract's index.json `metrics` object, from v1."""
    v1 = metrics["methods"]["v1"]
    return {"split": metrics["split"], "storms": v1["storms"], "caught": v1["caught"],
            "median_move_ahead_pct": v1["median_move_ahead_pct"],
            "false_alarms_per_day": v1["false_alarms_per_day"]}


def _fmt(v, spec: str = "", suffix: str = "") -> str:
    return "-" if v is None else f"{v:{spec}}{suffix}"


def print_report(m: dict) -> None:
    print(f"August backtest ({m['split']}; v1 tuned on {m['tuned_on']})")
    rows = [
        ("storms in the test set", "storms", "d", ""),
        ("storms alarmed (by the trough)", "alarmed", "d", ""),
        ("caught (>= 50% of move ahead)", "caught", "d", ""),
        ("median share of move ahead", "median_move_ahead_pct", ".1f", "%"),
        ("median minutes onset -> alarm", "median_minutes_to_alarm", "+.1f", ""),
        ("storm alarms fired", "storm_alarms", "d", ""),
        ("false storm alarms per day", "false_alarms_per_day", ".2f", ""),
        ("squalls per day", "squalls_per_day", ".2f", ""),
    ]
    names = ("v1", "v0", "naive")
    print(f"{'':34}" + "".join(f"{n:>10}" for n in names))
    for label, key, spec, suf in rows:
        print(f"{label:34}" + "".join(f"{_fmt(m['methods'][n][key], spec, suf):>10}" for n in names))
    print(f"(market days in August: {m['methods']['v1']['days']}; "
          f"v1 in storm state {m['methods']['v1']['storm_state_share_pct']}% of pair-minutes)")

    print("\nper storm (alarm UTC, share ahead):")
    print(f"{'':22}" + "".join(f"{n:>24}" for n in names))
    for k, s in enumerate(m["methods"]["v1"]["per_storm"]):
        cells = []
        for n in names:
            p = m["methods"][n]["per_storm"][k]
            cells.append("missed" if p["alarm_utc"] is None
                         else f"{p['alarm_utc'][11:]} {p['move_ahead_pct']:.0f}%{'*' if p['caught'] else ''}")
        print(f"{s['storm_id']:22}" + "".join(f"{c:>24}" for c in cells))
    print("(* caught)")

    pol = m["policy"]
    b = pol["book"]
    print(f"\npolicy v1 backtest, SYNTHETIC book: {'; '.join(b['legs'])}; equity ${b['equity_usd']:,.0f}, "
          f"maintenance {b['maintenance_margin'] * 100:.1f}%, {b['from_utc']} .. {b['to_utc']} UTC")
    a = pol["alerts"]
    print(f"alerts for this book: {a['danger_alarms']} danger alarms, {a['squalls']} squalls, "
          f"{a['fair_winds']} fair winds")
    print(f"{'':22}{'prepared':>14}{'unprepared':>14}")
    for label, key, f in (("final equity", "final_equity_usd", lambda v: f"${v:,.0f}"),
                          ("max drawdown", "max_drawdown_usd", lambda v: f"${v:,.0f}"),
                          ("max drawdown %", "max_drawdown_pct", lambda v: f"{v:.1f}%"),
                          ("margin calls", "margin_calls", str),
                          ("cuts / restores", None, None)):
        if key is None:
            vals = [f"{pol[s]['cuts']} / {pol[s]['restores']}" for s in ("prepared", "unprepared")]
        else:
            vals = [f(pol[s][key]) for s in ("prepared", "unprepared")]
        print(f"{label:22}{vals[0]:>14}{vals[1]:>14}")
    for s in ("prepared", "unprepared"):
        if pol[s]["margin_call_utc"]:
            print(f"  {s} margin call at {pol[s]['margin_call_utc']} UTC")


def main() -> None:
    m = run_backtest()
    path = PROCESSED_DIR / "metrics.json"
    path.write_text(json.dumps(m, indent=2, allow_nan=False) + "\n")
    print_report(m)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
