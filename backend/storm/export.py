"""Write a replay bundle per contracts/replay_bundle.md, and refresh index.json.

    python -m storm.export --storm usdjpy-2026-07-30 --from "2026-07-30 10:00" --to "2026-07-30 17:00"

Runs ingest first if data/processed is missing, then features -> labels (rewrites
storms.csv) -> detector -> ships -> bundle. Times are UTC; the window is inclusive.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from . import ingest
from .detector import load_calendar, run_detector
from .exposure import BOOK, exposure_snapshot, ships, stress_test
from .features import PAIRS, build_features
from .labels import label_all, print_storms, write_storms
from .paths import BUNDLES_DIR, CALENDAR_CSV, PROCESSED_DIR, RAW_DIR

SCHEMA_VERSION = 1
STEP_S = 60
MAX_FILL_MINUTES = 5          # a longer hole inside the window is an error, not a fill
SCHEDULED_BEFORE = pd.Timedelta(minutes=30)
SCHEDULED_AFTER = pd.Timedelta(minutes=15)
ALARM_LINK_BEFORE = pd.Timedelta(minutes=60)
SHIP_LABELS = {"prepared": "Followed the alarm", "unprepared": "Ignored it"}


def _r(x: float, nd: int) -> float:
    v = round(float(x), nd)
    if not math.isfinite(v):
        raise ValueError(f"non-finite value {x!r} in bundle")
    return v + 0.0  # no -0.0


def _parse_storm_id(storm_id: str) -> tuple[str, pd.Timestamp]:
    pair, _, day = storm_id.partition("-")
    return pair.upper(), pd.Timestamp(day[:10], tz="UTC")


def _ensure_processed(processed: Path, raw: Path) -> None:
    if all((processed / f"{p}_SPOT.parquet").exists() for p in PAIRS):
        return
    print(f"{processed} incomplete; running ingest from {raw}")
    ingest.print_report(ingest.ingest(raw, processed))


def _grid(feat: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.DataFrame, int]:
    """Reindex onto the one-minute frame grid; short holes are forward-filled as flat bars."""
    idx = pd.date_range(start, end, freq=f"{STEP_S}s")
    g = feat.reindex(idx)
    missing = g["mid"].isna()
    if missing.iloc[0]:
        raise ValueError(f"no bar at the window start {start}")
    runs = missing.groupby((~missing).cumsum()).sum()
    if runs.max() > MAX_FILL_MINUTES:
        raise ValueError(f"window has a hole of {int(runs.max())} minutes; pick another window")
    g = g.ffill()
    for col in ("open", "high", "low"):
        g.loc[missing, col] = g.loc[missing, "mid"]
    g.loc[missing, "jump"] = 0
    return g, int(missing.sum())


def _frame(idx: pd.DatetimeIndex, t: pd.Timestamp) -> int:
    """Frame of time t on the grid (t is snapped down to the minute)."""
    return int((t.floor("min") - idx[0]) / pd.Timedelta(seconds=STEP_S))


def _label(move_bp: float, minutes: int) -> str:
    return f"{'+' if move_bp > 0 else ''}{move_bp / 100:.1f}% in {minutes} min"


def build_bundle(
    storm_id: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    processed: Path = PROCESSED_DIR,
    raw: Path = RAW_DIR,
    calendar_path: Path = CALENDAR_CSV,
) -> tuple[dict, pd.DataFrame, dict]:
    """Returns (bundle, storms table, summary facts for printing)."""
    pair, day = _parse_storm_id(storm_id)
    if pair != BOOK["symbol"]:
        raise ValueError(f"the synthetic book trades {BOOK['symbol']}; storm {storm_id} is on {pair}")
    _ensure_processed(processed, raw)
    feats = build_features(processed, PAIRS)
    storms = label_all(feats)
    write_storms(storms, processed / "storms.csv")

    calendar = load_calendar(calendar_path)
    det, det_events = run_detector(feats[pair], calendar)
    full = feats[pair].join(det)
    g, filled = _grid(full, start, end)
    idx = g.index
    n = len(idx)
    in_window = lambda t: idx[0] <= t <= idx[-1]  # noqa: E731

    cands = storms[(storms["pair"] == pair) & storms["onset_utc"].map(in_window)]
    if cands.empty:
        raise ValueError(f"no labelled {pair} storm with onset in {start} .. {end}")
    st = cands.loc[cands["move_bp"].abs().idxmax()]
    onset_i, trough_i = _frame(idx, st.onset_utc), _frame(idx, st.trough_utc)
    scheduled = len(calendar) > 0 and bool(
        ((calendar["time_utc"] >= st.onset_utc - SCHEDULED_BEFORE)
         & (calendar["time_utc"] <= st.onset_utc + SCHEDULED_AFTER)).any()
    )

    mid = g["mid"].to_numpy(dtype=float)
    win_events = [e for e in det_events if in_window(e["time"])]
    alarms = [_frame(idx, e["time"]) for e in win_events if e["type"] == "alarm"]
    first_alarm = alarms[0] if alarms else None
    paths = ships(mid, first_alarm)

    onset_mid, trough_mid = float(st.onset_mid), float(st.trough_mid)

    def move_ahead_pct(i: int) -> float | None:
        t = idx[i]
        if not (st.onset_utc - ALARM_LINK_BEFORE <= t <= st.trough_utc):
            return None
        share = (mid[i] - trough_mid) / (onset_mid - trough_mid) * 100.0
        return _r(min(100.0, max(0.0, share)), 1)

    down = st.move_bp < 0
    events = []
    for e in win_events:
        i = _frame(idx, e["time"])
        if e["type"] == "alarm":
            linked = move_ahead_pct(i) is not None
            what = (f"sharp {pair} {'drop' if down else 'rise'} under way" if linked
                    else f"{pair} turbulence")
            events.append({"i": i, "type": "alarm", "text": f"Storm alarm: {what}",
                           "move_ahead_pct": move_ahead_pct(i)})
        elif e["type"] == "all_clear":
            events.append({"i": i, "type": "all_clear", "text": "Storm passing"})
        elif e["type"] == "watch":
            events.append({"i": i, "type": "watch", "text": f"Watch: {e['event']} at {e['at']:%H:%M} UTC",
                           "at_i": _frame(idx, e["at"])})
    for name, p in paths.items():
        if p.margin_call_i is not None:
            events.append({"i": p.margin_call_i, "type": "margin_call", "ship": name,
                           "text": "Margin call: position closed"})
    events.sort(key=lambda ev: ev["i"])

    as_of_i = max(0, onset_i - 1)
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "storm_id": storm_id,
        "title": f"{pair}, {day.day} {day:%B %Y}",
        "symbol": pair,
        "asset_class": "fx",
        "source": "sgx",
        "book_is_synthetic": True,
        "t0": int(idx[0].timestamp()),
        "step_s": STEP_S,
        "n": n,
        "storm": {
            "onset_i": onset_i,
            "trough_i": trough_i,
            "move_bp": _r(st.move_bp, 1),
            "kind": "scheduled" if scheduled else "unscheduled",
            "label": _label(float(st.move_bp), int(st.duration_min)),
        },
        "series": {
            "open": [_r(v, 5) for v in g["open"]],
            "high": [_r(v, 5) for v in g["high"]],
            "low": [_r(v, 5) for v in g["low"]],
            "mid": [_r(v, 5) for v in g["mid"]],
            "spread_bp": [_r(v, 3) for v in g["spread_bp"]],
            "vol_ratio": [_r(v, 2) for v in g["vol_ratio"]],
            "risk": [_r(v, 2) for v in g["risk"]],
            "state": [int(v) for v in g["state"]],
            "jump": [int(v) for v in g["jump"]],
            "prepared_equity": [int(round(v)) for v in paths["prepared"].equity],
            "unprepared_equity": [int(round(v)) for v in paths["unprepared"].equity],
        },
        "ships": {
            name: {
                "label": SHIP_LABELS[name],
                "start_equity_usd": int(BOOK["equity_usd"]),
                "margin_call_i": p.margin_call_i,
                "cut_i": p.cut_i,
                "cut_fraction": _r(p.cut_fraction, 2),
            }
            for name, p in paths.items()
        },
        "events": events,
        "exposure": exposure_snapshot(paths["unprepared"], mid, as_of_i),
        "stress": stress_test(storms, feats[BOOK["symbol"]]["mid"]),
        "report": None,
    }
    summary = {
        "pair": pair,
        "filled_minutes": filled,
        "onset": st.onset_utc,
        "trough": st.trough_utc,
        "move_bp": float(st.move_bp),
        "alarms": [(idx[i], move_ahead_pct(i)) for i in alarms],
        "cut_time": idx[first_alarm] if first_alarm is not None else None,
        "final_equity": {k: float(p.equity[-1]) for k, p in paths.items()},
        "margin_call": {k: (idx[p.margin_call_i] if p.margin_call_i is not None else None)
                        for k, p in paths.items()},
    }
    return bundle, storms, summary


def write_index(out_dir: Path) -> Path:
    """index.json lists every SGX bundle in out_dir (synthetic examples are left out)."""
    entries = []
    for f in sorted(out_dir.glob("*.json")):
        if f.name == "index.json":
            continue
        try:
            b = json.loads(f.read_text())
        except ValueError:
            continue
        if not isinstance(b, dict) or "series" not in b or b.get("source") == "synthetic":
            continue
        entries.append({
            "storm_id": b["storm_id"], "title": b["title"], "symbol": b["symbol"],
            "asset_class": b["asset_class"], "kind": b["storm"]["kind"],
            "move_bp": b["storm"]["move_bp"], "file": f.name,
        })
    index = {"schema_version": SCHEMA_VERSION, "storms": entries, "metrics": None}
    path = out_dir / "index.json"
    path.write_text(json.dumps(index, indent=2, allow_nan=False) + "\n")
    return path


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--storm", required=True, help="e.g. usdjpy-2026-07-30")
    ap.add_argument("--from", dest="start", required=True, help='UTC, e.g. "2026-07-30 10:00"')
    ap.add_argument("--to", dest="end", required=True, help='UTC, e.g. "2026-07-30 17:00"')
    ap.add_argument("--out", type=Path, default=BUNDLES_DIR)
    ap.add_argument("--processed", type=Path, default=PROCESSED_DIR)
    ap.add_argument("--raw", type=Path, default=RAW_DIR)
    args = ap.parse_args(argv)

    start = pd.Timestamp(args.start, tz="UTC")
    end = pd.Timestamp(args.end, tz="UTC")
    bundle, storms, s = build_bundle(args.storm, start, end, args.processed, args.raw)

    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{args.storm}.json"
    path.write_text(json.dumps(bundle, separators=(",", ":"), allow_nan=False) + "\n")
    index = write_index(args.out)

    print_storms(storms)
    print()
    print(f"{args.storm}: onset {s['onset']:%H:%M} UTC, trough {s['trough']:%H:%M} UTC, {s['move_bp']:+.1f} bp"
          f" (n={bundle['n']}, {s['filled_minutes']} minutes filled)")
    linked = [(t, a) for t, a in s["alarms"] if a is not None]
    if linked:
        t, a = linked[0]
        print(f"storm alarm: {t:%H:%M} UTC; share of the fall still ahead: {a:.1f}%")
    else:
        print("storm alarm: none (the detector missed this storm)")
    others = [f"{t:%H:%M}" for t, a in s["alarms"] if a is None]
    if others:
        print(f"other alarms in window (not this storm): {', '.join(others)} UTC")
    if s["cut_time"] is not None:
        print(f"prepared ship cut 75% at the first alarm, {s['cut_time']:%H:%M} UTC")
    for k in ("prepared", "unprepared"):
        mc = s["margin_call"][k]
        print(f"{k:10} final equity ${s['final_equity'][k]:,.0f}"
              f"{'' if mc is None else f' (margin call {mc:%H:%M} UTC)'}")
    print(f"wrote {path}")
    print(f"wrote {index}")


if __name__ == "__main__":
    main()
