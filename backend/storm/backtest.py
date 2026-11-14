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

Scheduled vs unscheduled (storm.labels: onset within 15 minutes of a calendar event)
  scheduled    watched: v1 showed the watch state (1) on the storm's pair between
               event - watch_lead_minutes and the onset; warning = onset - first watch
               minute, in minutes
  unscheduled  the alarm metrics above, restricted to unscheduled storms (false alarms
               are counted once, over all storms, so they are not split)
  combined     storms with a watch before onset or a caught alarm (>= 50% of the move
               still ahead)
Reported on August (the test split), and over July + August for reference (July is
the tuning month for the alarm, so its alarm results are in-sample; the watch is
set by the calendar alone and has no tuned parameter).

Watch precision (the honest side of the watch: how often a watch was for nothing)
  per scheduled release in contracts/calendar.csv, its watch window is
  [release - watch_lead_minutes, release + watch_after_minutes); the release produced a
  storm when a labelled storm on any pair has its onset inside that window, else the
  watch was quiet. watch_precision = releases with a storm / releases, for July, August
  and both. The calendar is the full list of verified releases and is never filtered
  to improve this number.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import detector_v0
from .detector import CONFIG_PATH, WATCH, load_calendar, load_config, run_detector
from .evaluate import CAUGHT_PCT, _median, market_days, score, v1_alarms_and_squalls
from .exposure import policy_backtest
from .features import PAIRS, build_features
from .labels import label_all, window_moves
from .paths import PROCESSED_DIR

TEST_START = pd.Timestamp("2026-08-01", tz="UTC")
TEST_END = pd.Timestamp("2026-09-01", tz="UTC")   # exclusive
ALL_START = pd.Timestamp("2026-07-01", tz="UTC")
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


def watch_before_onset(storm, frame: pd.DataFrame, lead_minutes: int) -> dict:
    """First v1 watch minute on the storm's pair from event - lead up to (not incl.) onset."""
    if storm.kind != "scheduled":
        return {"watch_start_utc": None, "watch_before_onset": None, "warning_minutes": None}
    lo = storm.event_utc - pd.Timedelta(minutes=lead_minutes)
    st = frame["state"]
    watched = st.index[(st.index >= lo) & (st.index < storm.onset_utc) & (st.to_numpy() == WATCH)]
    if len(watched) == 0:
        return {"watch_start_utc": None, "watch_before_onset": False, "warning_minutes": None}
    w = watched[0]
    return {"watch_start_utc": f"{w:%Y-%m-%d %H:%M}", "watch_before_onset": True,
            "warning_minutes": int((storm.onset_utc - w) / pd.Timedelta(minutes=1))}


def per_storm_coverage(storms: pd.DataFrame, v1: dict, alarm_rows: list[dict], lead_minutes: int) -> list[dict]:
    """One row per storm: kind, event, watch warning and the v1 alarm (rows aligned with storms)."""
    out = []
    for s, a in zip(storms.itertuples(), alarm_rows):
        assert a["storm_id"] == s.storm_id
        w = watch_before_onset(s, v1[s.pair].frame, lead_minutes)
        out.append({
            "storm_id": s.storm_id, "pair": s.pair,
            "split": "test" if TEST_START <= s.onset_utc < TEST_END else "tuning",
            "onset_utc": f"{s.onset_utc:%Y-%m-%d %H:%M}", "move_bp": float(s.move_bp),
            "kind": s.kind, "event": s.event or None,
            "event_utc": None if pd.isna(s.event_utc) else f"{s.event_utc:%Y-%m-%d %H:%M}",
            **w,
            "alarm_utc": a["alarm_utc"], "alarm_minutes": a["minutes"],
            "move_ahead_pct": a["move_ahead_pct"], "caught": a["caught"],
            "covered": bool(w["watch_before_onset"]) or a["caught"],
        })
    return out


WATCH_PERIODS = {"july": (ALL_START, TEST_START), "august": (TEST_START, TEST_END),
                 "all_months": (ALL_START, TEST_END)}
WATCH_PERIOD_LABELS = {"july": "July", "august": "August", "all_months": "July + August"}


def watch_outcomes(calendar: pd.DataFrame, storms: pd.DataFrame, lead_minutes: int, after_minutes: int,
                   start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """Scheduled releases in [start, end): which watch windows held a storm, which were quiet."""
    lead, after = pd.Timedelta(minutes=lead_minutes), pd.Timedelta(minutes=after_minutes)
    rows = []
    for r in calendar.itertuples():
        t = r.time_utc
        if not start <= t < end:
            continue
        inside = storms[(storms["onset_utc"] >= t - lead) & (storms["onset_utc"] < t + after)]
        rows.append({"release_utc": f"{t:%Y-%m-%d %H:%M}", "event": str(r.event),
                     "storms": [str(x) for x in inside["storm_id"]]})
    n = len(rows)
    quiet = [r for r in rows if not r["storms"]]
    return {
        "releases": n,
        "with_storm": n - len(quiet),
        "quiet": len(quiet),
        "quiet_share_pct": round(len(quiet) / n * 100, 1) if n else None,
        "watch_precision": round((n - len(quiet)) / n, 2) if n else None,
        "quiet_releases": [f"{r['event']} ({r['release_utc']} UTC)" for r in quiet],
        "per_release": rows,
    }


def _alarm_summary(rows: list[dict]) -> dict:
    alarmed = [r for r in rows if r["alarm_utc"] is not None]
    return {"storms": len(rows), "alarmed": len(alarmed), "caught": sum(r["caught"] for r in rows),
            "median_move_ahead_pct": _median([r["move_ahead_pct"] for r in alarmed]),
            "median_minutes_to_alarm": _median([r["minutes"] for r in alarmed])}


def kind_summary(coverage: list[dict], methods_per_storm: dict[str, list[dict]] | None = None) -> dict:
    """Scheduled (watch), unscheduled (alarms) and combined coverage over `coverage` rows."""
    sched = [r for r in coverage if r["kind"] == "scheduled"]
    warned = [r for r in sched if r["watch_before_onset"]]
    unsched_ids = {r["storm_id"] for r in coverage if r["kind"] == "unscheduled"}
    out = {
        "scheduled": {
            "storms": len(sched),
            "watched_before_onset": len(warned),
            "median_warning_minutes": _median([r["warning_minutes"] for r in warned]),
            "min_warning_minutes": min((r["warning_minutes"] for r in warned), default=None),
            "alarmed": sum(r["alarm_utc"] is not None for r in sched),
            "caught": sum(r["caught"] for r in sched),
        },
        "unscheduled": {},
        "combined": {"storms": len(coverage), "covered": sum(r["covered"] for r in coverage)},
    }
    c = out["combined"]
    c["covered_pct"] = round(c["covered"] / c["storms"] * 100, 1) if c["storms"] else None
    for name, rows in (methods_per_storm or {}).items():
        out["unscheduled"][name] = _alarm_summary([r for r in rows if r["storm_id"] in unsched_ids])
    if not methods_per_storm:
        out["unscheduled"]["v1"] = _alarm_summary(
            [{**r, "minutes": r["alarm_minutes"]} for r in coverage if r["storm_id"] in unsched_ids])
    return out


def run_backtest(processed: Path = PROCESSED_DIR, calendar: pd.DataFrame | None = None) -> dict:
    cfg = load_config()
    calendar = load_calendar() if calendar is None else calendar
    feats = build_features(processed, PAIRS)
    storms_all = label_all(feats, calendar)
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

    # Scheduled vs unscheduled. Alarms for every storm (July in-sample) come from one
    # score over the whole span; the August rows match methods["v1"]["per_storm"].
    all_alarms, _ = v1_alarms_and_squalls(v1, ALL_START, TEST_END)
    days_all = market_days(feats, ALL_START, TEST_END)
    coverage = per_storm_coverage(storms_all, v1, score(all_alarms, storms_all, mids, days_all)["per_storm"],
                                  cfg["watch_lead_minutes"])
    test_cov = [r for r in coverage if r["split"] == "test"]
    by_kind = {
        "test": kind_summary(test_cov, {n: methods[n]["per_storm"] for n in methods}),
        "all_months": kind_summary(coverage),
    }

    watch = {k: watch_outcomes(calendar, storms_all, cfg["watch_lead_minutes"], cfg["watch_after_minutes"], a, b)
             for k, (a, b) in WATCH_PERIODS.items()}

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
            "false_alarm_episode": "false alarms on any pairs, sorted by time, each within 15 min "
                                   "of the previous one: counted once",
            "direction": "detection metrics ignore direction; policy uses the book's exposure",
            "scheduled": "onset within 15 min of a contracts/calendar.csv event (either side)",
            "watched": "v1 watch state on the storm's pair between event - 30 min and onset",
            "warning_minutes": "onset - first watch minute",
            "covered": f"watched before onset, or alarm with >= {CAUGHT_PCT:.0f}% of the move ahead",
            "all_months": "July + August; July alarm results are in-sample (tuning month)",
            "quiet_watch": "a calendar release whose watch window (event - 30 min to event + 15 min) "
                           "holds no labelled storm onset on any pair",
            "watch_precision": "releases whose watch window holds a storm onset / all releases "
                               "(top level: August, the test split)",
        },
        "methods": methods,
        "by_kind": by_kind,
        "watch_precision": watch["august"]["watch_precision"],
        "watch": watch,
        "storms": coverage,
        "policy": policy,
    }


def index_metrics(metrics: dict) -> dict:
    """The contract's index.json `metrics` object, from v1, plus the optional evidence-card
    figures (alarmed, median minutes to alarm, de-duplicated false alarms, watch precision and
    the policy backtest's max drawdown per ship)."""
    v1 = metrics["methods"]["v1"]
    pol = metrics.get("policy") or {}
    out = {"split": metrics["split"], "storms": v1["storms"], "caught": v1["caught"],
           "median_move_ahead_pct": v1["median_move_ahead_pct"],
           "false_alarms_per_day": v1["false_alarms_per_day"],
           "alarmed": v1.get("alarmed"),
           "median_minutes_to_alarm": v1.get("median_minutes_to_alarm"),
           "false_alarm_episodes_per_day": v1.get("false_alarm_episodes_per_day"),
           "watch_precision": metrics.get("watch_precision")}
    for ship in ("prepared", "unprepared"):
        p = pol.get(ship) or {}
        out[f"{ship}_max_drawdown_usd"] = p.get("max_drawdown_usd")
        out[f"{ship}_max_drawdown_pct"] = p.get("max_drawdown_pct")
    return out


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
        ("  de-duplicated across pairs", "false_alarm_episodes_per_day", ".2f", ""),
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

    print_kinds(m)
    print_watch(m)

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


def coverage_line(k: dict, label: str) -> str:
    c, sc, un = k["combined"], k["scheduled"], k["unscheduled"]["v1"]
    return (f"{label}: {c['covered']} of {c['storms']} storms covered ({_fmt(c['covered_pct'], '.0f', '%')}): "
            f"{sc['watched_before_onset']} of {sc['storms']} scheduled watched before onset, "
            f"{un['caught']} of {un['storms']} unscheduled caught by the v1 alarm")


def print_kinds(m: dict) -> None:
    print("\nevery storm, scheduled vs unscheduled (tuning = July, in-sample for the alarm):")
    print(f"{'storm_id':22} {'split':7} {'kind':11} {'warning':>8} {'alarm':>6} {'ahead':>6}  event")
    for r in m["storms"]:
        warn = "-" if r["kind"] != "scheduled" else (
            "none" if not r["watch_before_onset"] else f"{r['warning_minutes']} min")
        alarm = "-" if r["alarm_utc"] is None else r["alarm_utc"][11:]
        ahead = "-" if r["move_ahead_pct"] is None else f"{r['move_ahead_pct']:.0f}%"
        ev = "" if r["event"] is None else f"{r['event']} ({r['event_utc'][11:]} UTC)"
        print(f"{r['storm_id']:22} {r['split']:7} {r['kind']:11} {warn:>8} {alarm:>6} {ahead:>6}  {ev}")
    t = m["by_kind"]["test"]
    sc = t["scheduled"]
    print(f"\nAugust, scheduled: {sc['storms']} storms, {sc['watched_before_onset']} watched before onset, "
          f"median warning {_fmt(sc['median_warning_minutes'], '.0f', ' min')} "
          f"(min {_fmt(sc['min_warning_minutes'], 'd', ' min')})")
    print("August, unscheduled (alarm metrics):")
    print(f"{'':34}" + "".join(f"{n:>10}" for n in t["unscheduled"]))
    for label, key, spec, suf in (("storms", "storms", "d", ""), ("alarmed", "alarmed", "d", ""),
                                  ("caught", "caught", "d", ""),
                                  ("median share of move ahead", "median_move_ahead_pct", ".1f", "%"),
                                  ("median minutes onset -> alarm", "median_minutes_to_alarm", "+.1f", "")):
        print(f"{label:34}" + "".join(f"{_fmt(v[key], spec, suf):>10}" for v in t["unscheduled"].values()))
    print(coverage_line(t, "COMBINED, August (test)"))
    print(coverage_line(m["by_kind"]["all_months"], "COMBINED, July + August"))


def watch_line(w: dict, label: str) -> str:
    return (f"{label}: {w['releases']} scheduled releases, {w['with_storm']} produced a storm, "
            f"{w['quiet']} were quiet (watch precision {_fmt(w['watch_precision'], '.2f')})")


def print_watch(m: dict) -> None:
    print("\nwatch precision (a quiet watch: no storm onset on any pair in the release's watch window):")
    for k, label in WATCH_PERIOD_LABELS.items():
        w = m["watch"][k]
        print(watch_line(w, label))
        if k != "all_months":
            for q in w["quiet_releases"]:
                print(f"    quiet: {q}")


def main() -> None:
    m = run_backtest()
    path = PROCESSED_DIR / "metrics.json"
    path.write_text(json.dumps(m, indent=2, allow_nan=False) + "\n")
    print_report(m)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
