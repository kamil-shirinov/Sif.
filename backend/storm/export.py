"""Write replay bundles per contracts/replay_bundle.md, and index.json.

    python -m storm.export --all
    python -m storm.export --storm usdjpy-2026-07-30 [--from "2026-07-30 10:00" --to "2026-07-30 17:00"]
    python -m storm.export --all --live [--model ID --provider meta]   (real model gateway)

Runs ingest first if data/processed is missing, then features -> labels (rewrites
storms.csv) -> detector v1 (data/processed/detector_config.json) -> policy v1 ships ->
bundles. --all writes one bundle per storm in storms.csv, each from 3 hours before onset
to 3 hours after (trimmed to the bars that exist), and an index.json listing exactly
those bundles plus any Yahoo equity bundle already in the folder (storm.equity), whose
report is rewritten by the same writer. Times are UTC; the window is inclusive.

Each bundle's ship trades the storm's pair: a SYNTHETIC book long USD 20,000,000 against
the pair's other currency (short EUR for EURUSD), $1,000,000 equity, 2.5% maintenance.
The prepared ship follows policy v1 (storm.exposure); the unprepared ship holds.

Each bundle carries a storm report from storm.ai.report (facts_from_bundle, then
write_report): the deterministic mock by default (LLM_MODE is forced to mock), the real
gateway with --live (the budget guard applies). A scheduled storm's facts add the
calendar event's name and time, so the report can state the timing, never a cause.

Additions documented in contracts/replay_bundle.md (still schema_version 1, all optional):
  ships.<name>.restore_i   first restore after the first cut (int or null)
  event types              squall, fair_wind, cut, restore (cut_i stays the first cut)
  watch events             add `event` (the calendar event's name)
  storm.event, event_i     for a scheduled storm: the calendar event and its frame
  report.inspector         {verdict: ok | flag, issues: [...]}
  index storms[].source    the bundle's source (sgx, yahoo, scenario), so a reader can tell
                           market replays from navigator what-ifs; scenario bundles already in
                           the folder are listed but never rewritten
"""
from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import ingest
from .ai.report import facts_from_bundle, write_report
from .backtest import index_metrics
from .detector import load_calendar, load_config, run_detector
from .evaluate import LINK_BEFORE, move_ahead_pct
from .exposure import book_for, exposure_snapshot, leg_exposure, policy_actions, ships, stress_test
from .features import PAIRS, build_features
from .labels import label_all, print_storms, write_storms
from .paths import BUNDLES_DIR, CALENDAR_CSV, PROCESSED_DIR, RAW_DIR

SCHEMA_VERSION = 1
STEP_S = 60
MAX_FILL_MINUTES = 5          # a longer hole inside the window is an error, not a fill
WINDOW_BEFORE = pd.Timedelta(hours=3)
WINDOW_AFTER = pd.Timedelta(hours=3)
SHIP_LABELS = {"prepared": "Followed the alarm", "unprepared": "Ignored it"}
EVENT_ORDER = {t: k for k, t in enumerate(
    ["watch", "squall", "alarm", "fair_wind", "cut", "margin_call", "all_clear", "restore"])}


def _r(x: float, nd: int) -> float:
    v = round(float(x), nd)
    if not math.isfinite(v):
        raise ValueError(f"non-finite value {x!r} in bundle")
    return v + 0.0  # no -0.0


def _ensure_processed(processed: Path, raw: Path) -> None:
    if all((processed / f"{p}_SPOT.parquet").exists() for p in PAIRS):
        return
    print(f"{processed} incomplete; running ingest from {raw}")
    ingest.print_report(ingest.ingest(raw, processed))


@dataclass
class Context:
    feats: dict[str, pd.DataFrame]
    storms: pd.DataFrame
    calendar: pd.DataFrame
    cfg: dict


def load_context(processed: Path = PROCESSED_DIR, raw: Path = RAW_DIR,
                 calendar_path: Path = CALENDAR_CSV, cfg: dict | None = None,
                 write_labels: bool = True) -> Context:
    _ensure_processed(processed, raw)
    feats = build_features(processed, PAIRS)
    calendar = load_calendar(calendar_path)
    storms = label_all(feats, calendar)
    if write_labels:
        write_storms(storms, processed / "storms.csv")
    cfg = load_config(processed / "detector_config.json") if cfg is None else cfg
    return Context(feats, storms, calendar, cfg)


def _grid(feat: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp,
          open_mask=None) -> tuple[pd.DataFrame, int]:
    """Reindex onto the one-minute frame grid; short holes are forward-filled as flat bars.

    `open_mask` (bool per grid minute, default all open) marks when the market trades: a
    closed stretch of any length is filled flat at the last price; a hole longer than
    MAX_FILL_MINUTES while open is an error. Returns (grid, holes filled while open)."""
    idx = pd.date_range(start, end, freq=f"{STEP_S}s")
    g = feat.reindex(idx)
    missing = g["mid"].isna()
    if missing.iloc[0]:
        raise ValueError(f"no bar at the window start {start}")
    hole = missing if open_mask is None else missing & pd.Series(open_mask, index=idx).astype(bool)
    runs = hole.groupby((~hole).cumsum()).sum()
    if runs.max() > MAX_FILL_MINUTES:
        raise ValueError(f"window has a hole of {int(runs.max())} minutes; pick another window")
    g = g.ffill()
    for col in ("open", "high", "low"):
        g.loc[missing, col] = g.loc[missing, "mid"]
    g.loc[missing, "jump"] = 0
    return g, int(hole.sum())


def default_window(feat: pd.DataFrame, storm) -> tuple[pd.Timestamp, pd.Timestamp]:
    """onset - 3 h .. onset + 3 h, trimmed to the first and last bars inside it."""
    lo, hi = storm.onset_utc - WINDOW_BEFORE, storm.onset_utc + WINDOW_AFTER
    bars = feat.index[(feat.index >= lo) & (feat.index <= hi)]
    return bars[0], bars[-1]


def _label(move_bp: float, minutes: int) -> str:
    return f"{'+' if move_bp > 0 else ''}{move_bp / 100:.1f}% in {minutes} min"


def _title(storm) -> str:
    t = storm.onset_utc
    title = f"{storm.pair}, {t.day} {t:%B %Y}"
    return title if storm.storm_id.count("-") <= 3 else f"{title}, {t:%H:%M} UTC"


def _event_text(e: dict, pair: str, cfg: dict, linked: bool) -> str:
    way = "drop" if e.get("direction", 0) < 0 else "rise"
    if e["type"] == "alarm":
        return f"Storm alarm: sharp {pair} {way} against the book" + ("" if linked else " (turbulence)")
    if e["type"] == "squall":
        return f"Squall: {pair} {way} against the book"
    if e["type"] == "fair_wind":
        return f"Fair wind: sharp {pair} {way} in the book's favour, no trade"
    if e["type"] == "all_clear":
        return f"All clear: {cfg['calm_minutes']} calm minutes"
    raise ValueError(e["type"])


def _visible_events(events: list[dict], state: pd.Series, frame_of) -> list[dict]:
    """Drop an all-clear that closes an episode the window never shows (no alert since the
    previous all-clear and no storm state just before it)."""
    out, open_alert = [], False
    st = state.to_numpy()
    for e in events:
        if e["type"] in ("squall", "alarm", "fair_wind"):
            open_alert = True
        elif e["type"] == "all_clear":
            i = frame_of(e["time"])
            if not open_alert and not (i > 0 and st[i - 1] == 2):
                continue
            open_alert = False
        out.append(e)
    return out


def build_bundle(ctx: Context, storm, start: pd.Timestamp, end: pd.Timestamp) -> tuple[dict, dict]:
    """Returns (bundle, summary facts for printing)."""
    pair = storm.pair
    feat = ctx.feats[pair]
    book = book_for(pair)
    res = run_detector(feat, ctx.calendar, ctx.cfg, exposure=leg_exposure(pair))
    g, filled = _grid(feat.join(res.frame[["risk", "state"]]), start, end)
    idx = g.index
    n = len(idx)

    def frame_of(t: pd.Timestamp) -> int:
        return int((t.floor("min") - idx[0]) / pd.Timedelta(seconds=STEP_S))

    onset_i, trough_i = frame_of(storm.onset_utc), frame_of(storm.trough_utc)
    if not (0 <= onset_i < n and 0 <= trough_i < n):
        raise ValueError(f"{storm.storm_id}: onset or trough outside the window")
    scheduled = storm.kind == "scheduled"
    event_i = frame_of(storm.event_utc) if scheduled else None
    if scheduled and not 0 <= event_i < n:
        raise ValueError(f"{storm.storm_id}: scheduled event outside the window")

    win = _visible_events([e for e in res.events if idx[0] <= e["time"] <= idx[-1]], g["state"], frame_of)
    mid = g["mid"].to_numpy(dtype=float)
    paths = ships({pair: mid}, book, policy_actions({pair: win}, frame_of))
    prep = paths["prepared"]

    def ahead(t: pd.Timestamp) -> float | None:
        if not (storm.onset_utc - LINK_BEFORE <= t <= storm.trough_utc):
            return None
        return _r(move_ahead_pct(t, storm, feat["mid"]), 1)

    events = []
    for e in win:
        i = frame_of(e["time"])
        if e["type"] == "watch":
            at_i = frame_of(e["at"])
            if not 0 <= at_i < n:
                continue   # release outside the replay: the state series still shows the watch
            events.append({"i": i, "type": "watch", "text": f"Watch: {e['event']} at {e['at']:%H:%M} UTC",
                           "at_i": at_i, "event": e["event"]})
            continue
        ev = {"i": i, "type": e["type"], "text": _event_text(e, pair, ctx.cfg, ahead(e["time"]) is not None)}
        if e["type"] == "alarm":
            ev["move_ahead_pct"] = ahead(e["time"])
        events.append(ev)
    pct = round(book["cut_fraction"] * 100)
    for i, _ in prep.cuts:
        events.append({"i": i, "type": "cut", "text": f"Prepared ship cuts its {pair} position by {pct}%"})
    for i, _ in prep.restores:
        events.append({"i": i, "type": "restore", "text": f"Prepared ship restores its full {pair} position"})
    for name, p in paths.items():
        if p.margin_call_i is not None:
            events.append({"i": p.margin_call_i, "type": "margin_call", "ship": name,
                           "text": "Margin call: position closed"})
    events.sort(key=lambda ev: (ev["i"], EVENT_ORDER[ev["type"]]))

    as_of_i = max(0, onset_i - 1)
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "storm_id": storm.storm_id,
        "title": _title(storm),
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
            "move_bp": _r(storm.move_bp, 1),
            "kind": "scheduled" if scheduled else "unscheduled",
            "label": _label(float(storm.move_bp), int(storm.duration_min)),
            **({"event": storm.event, "event_i": event_i} if scheduled else {}),
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
            "prepared_equity": [int(round(v)) for v in prep.equity],
            "unprepared_equity": [int(round(v)) for v in paths["unprepared"].equity],
        },
        "ships": {
            name: {
                "label": SHIP_LABELS[name],
                "start_equity_usd": int(book["equity_usd"]),
                "margin_call_i": p.margin_call_i,
                "cut_i": p.cut_i,
                "cut_fraction": _r(p.cut_fraction, 2),
                "restore_i": p.restore_i,
            }
            for name, p in paths.items()
        },
        "events": events,
        "exposure": exposure_snapshot(paths["unprepared"], {pair: mid}, book, as_of_i),
        "stress": stress_test(ctx.storms, feat["mid"], book),
        "report": None,
    }
    alarms = [(idx[ev["i"]], ev["move_ahead_pct"]) for ev in events if ev["type"] == "alarm"]
    summary = {
        "storm_id": storm.storm_id,
        "filled_minutes": filled,
        "onset": storm.onset_utc,
        "trough": storm.trough_utc,
        "move_bp": float(storm.move_bp),
        "alarms": alarms,
        "fair_winds": [idx[ev["i"]] for ev in events if ev["type"] == "fair_wind"],
        "squalls": sum(ev["type"] == "squall" for ev in events),
        "cut": idx[prep.cut_i] if prep.cut_i is not None else None,
        "restore": idx[prep.restore_i] if prep.restore_i is not None else None,
        "final_equity": {k: float(p.equity[-1]) for k, p in paths.items()},
        "margin_call": {k: (idx[p.margin_call_i] if p.margin_call_i is not None else None)
                        for k, p in paths.items()},
    }
    return bundle, summary


def _utc(bundle: dict, i: int) -> pd.Timestamp:
    return pd.Timestamp(bundle["t0"] + i * bundle["step_s"], unit="s", tz="UTC")


def closed_stretches(bundle: dict) -> list[tuple[int, int]]:
    """(first closed frame, first open frame after it, or n) for each run of market_open == 0."""
    is_open = bundle["series"].get("market_open")
    if is_open is None:
        return []
    out, start = [], None
    for i, v in enumerate(is_open):
        if v == 0 and start is None:
            start = i
        elif v == 1 and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(is_open)))
    return out


def market_hours_facts(bundle: dict) -> dict | None:
    """For a bundle with market_open (equities): trading minutes from onset to trough and
    the closed stretches. Facts only: when the market traded, never why prices moved."""
    is_open = bundle["series"].get("market_open")
    if is_open is None:
        return None
    st = bundle["storm"]
    o, t = st["onset_i"], st["trough_i"]
    trading = int(sum(is_open[o + 1:t + 1]))
    clock = (t - o) * bundle["step_s"] // 60
    closed = []
    for a, b in closed_stretches(bundle):
        if b <= o or a > t:
            continue
        frm, to = _utc(bundle, a), _utc(bundle, b)
        closed.append({"from_utc": frm.isoformat().replace("+00:00", "Z"),
                       "to_utc": to.isoformat().replace("+00:00", "Z"),
                       "minutes": (b - a) * bundle["step_s"] // 60,
                       "text": f"market closed from {frm:%d %b %H:%M} UTC to {to:%d %b %H:%M} UTC"})
    note = ("duration_minutes counts trading minutes only (pre-market, regular and after-hours "
            f"sessions): {trading} trading minutes out of {clock} clock minutes from onset to trough. ")
    if closed:
        note += ("The market was closed overnight in between ("
                 + "; ".join(c["text"] for c in closed)
                 + "): no trades and no price change during that time. ")
    note += "The data show when the market traded and what prices did, not why."
    return {"trading_minutes": trading, "clock_minutes": clock,
            "closed_minutes": clock - trading, "closed": closed,
            "move": st["label"], "note": note}


def report_facts(bundle: dict) -> dict:
    """storm.ai.report facts, plus the scheduled event (name and time) when there is one,
    and, for a market with closed hours, trading minutes instead of clock minutes."""
    facts = facts_from_bundle(bundle)
    st = bundle["storm"]
    hours = market_hours_facts(bundle)
    if hours is not None:
        facts["storm"]["duration_minutes"] = hours["trading_minutes"]
        facts["storm"]["market_hours"] = hours
    if st["kind"] == "scheduled" and "event" in st:
        at = _utc(bundle, st["event_i"])
        facts["storm"]["scheduled_event"] = {
            "name": st["event"],
            "time_utc": at.isoformat().replace("+00:00", "Z"),
            "onset_minutes_after_event": (st["onset_i"] - st["event_i"]) * bundle["step_s"] / 60,
            "note": "Timing only: the move began near this scheduled release. "
                    "The data do not show what caused it.",
        }
    return facts


def attach_report(bundle: dict, live: bool = False, model: str | None = None,
                  provider: str = "meta") -> dict:
    """Write, verify and inspect the storm report; store the contract's fields in bundle.report."""
    if not live:
        os.environ["LLM_MODE"] = "mock"   # .env is loaded without override, so this wins
    r = write_report(report_facts(bundle), live=live, model=model, provider=provider)
    bundle["report"] = {
        "text": r["text"], "verified": bool(r["verified"]),
        "unverified_numbers": list(r["unverified_numbers"]), "model": r["model"],
        "inspector": {"verdict": r["inspector"]["verdict"], "issues": list(r["inspector"]["issues"])},
    }
    return r


def _index_entry(b: dict, file: str) -> dict:
    return {"storm_id": b["storm_id"], "title": b["title"], "symbol": b["symbol"],
            "asset_class": b["asset_class"], "kind": b["storm"]["kind"],
            "move_bp": b["storm"]["move_bp"], "file": file, "source": b["source"]}


def load_index_metrics(processed: Path = PROCESSED_DIR) -> dict | None:
    path = processed / "metrics.json"
    if not path.exists():
        return None
    return index_metrics(json.loads(path.read_text()))


def scan_bundles(out_dir: Path) -> list[tuple[dict, str]]:
    """Every non-synthetic bundle in out_dir as (bundle, file name)."""
    found = []
    for f in sorted(out_dir.glob("*.json")):
        if f.name == "index.json":
            continue
        try:
            b = json.loads(f.read_text())
        except ValueError:
            continue
        if isinstance(b, dict) and "series" in b and b.get("source") != "synthetic":
            found.append((b, f.name))
    return found


def write_index(out_dir: Path, bundles: list[tuple[dict, str]] | None = None,
                metrics: dict | None = None) -> Path:
    """index.json lists `bundles` (bundle, file name), or else every non-synthetic bundle in out_dir."""
    if bundles is None:
        bundles = scan_bundles(out_dir)
    index = {"schema_version": SCHEMA_VERSION,
             "storms": [_index_entry(b, name) for b, name in bundles],
             "metrics": metrics}
    path = out_dir / "index.json"
    path.write_text(json.dumps(index, indent=2, allow_nan=False) + "\n")
    return path


def write_bundle(bundle: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{bundle['storm_id']}.json"
    path.write_text(json.dumps(bundle, separators=(",", ":"), allow_nan=False) + "\n")
    return path


def export_all(ctx: Context, out_dir: Path, metrics: dict | None, live: bool = False,
               model: str | None = None, provider: str = "meta") -> tuple[list[Path], Path, list[dict]]:
    written, summaries = [], []
    for st in ctx.storms.itertuples():
        start, end = default_window(ctx.feats[st.pair], st)
        bundle, s = build_bundle(ctx, st, start, end)
        r = attach_report(bundle, live, model, provider)
        path = write_bundle(bundle, out_dir)
        written.append((bundle, path.name))
        summaries.append({**s, "path": path, "n": bundle["n"], "report": bundle["report"],
                          "report_cost_usd": r["cost_usd"], "report_fallback": r["fallback"],
                          "kind": st.kind, "event": st.event})
    # Keep the Yahoo equity bundles (written by storm.equity) listed alongside the SGX storms,
    # and give them a fresh report from the same writer (their prices and ships are unchanged).
    mine = {name for _, name in written}
    others = [(b, name) for b, name in scan_bundles(out_dir) if b.get("source") == "yahoo" and name not in mine]
    for b, name in others:
        r = attach_report(b, live, model, provider)
        write_bundle(b, out_dir)
        summaries.append({"storm_id": b["storm_id"], "path": out_dir / name, "n": b["n"],
                          "report": b["report"], "report_cost_usd": r["cost_usd"],
                          "report_fallback": r["fallback"], "kind": b["storm"]["kind"], "event": "",
                          "sgx": False})
    # Navigator what-if bundles (source scenario) stay listed as they are: storm.ai owns them.
    scenarios = [(b, name) for b, name in scan_bundles(out_dir) if b.get("source") == "scenario"]
    index = write_index(out_dir, written + others + scenarios, metrics)
    return [out_dir / name for _, name in written + others], index, summaries


def _hm(t) -> str:
    return "-" if t is None else f"{t:%H:%M}"


def print_summaries(summaries: list[dict]) -> None:
    print(f"{'storm_id':22} {'move_bp':>8} {'alarm':>6} {'ahead':>6} {'fair':>6} {'cut':>6} {'restore':>7}"
          f" {'prepared $':>12} {'unprepared $':>13}")
    for s in summaries:
        if s.get("sgx") is False:
            continue
        a = s["alarms"][0] if s["alarms"] else (None, None)
        ahead = "-" if a[1] is None else f"{a[1]:.0f}%"
        fair = s["fair_winds"][0] if s["fair_winds"] else None
        mc = "  MC" if s["margin_call"]["unprepared"] else ""
        print(f"{s['storm_id']:22} {s['move_bp']:8.1f} {_hm(a[0]):>6} {ahead:>6} {_hm(fair):>6} "
              f"{_hm(s['cut']):>6} {_hm(s['restore']):>7} {s['final_equity']['prepared']:12,.0f} "
              f"{s['final_equity']['unprepared']:13,.0f}{mc}")
    print("(times UTC; alarm = first storm-level danger alarm in the window; MC = margin call)")


def print_report_line(s: dict) -> None:
    r = s["report"]
    print(f"{s['storm_id']:22} model={r['model']:28} verified={r['verified']!s:5} "
          f"inspector={r['inspector']['verdict']:4} fallback={s['report_fallback']!s:5} "
          f"cost=${s['report_cost_usd']:.4f}")


def print_detail(s: dict) -> None:
    print(f"{s['storm_id']}: onset {s['onset']:%H:%M} UTC, trough {s['trough']:%H:%M} UTC, "
          f"{s['move_bp']:+.1f} bp ({s['filled_minutes']} minutes filled)")
    linked = [(t, a) for t, a in s["alarms"] if a is not None]
    if linked:
        t, a = linked[0]
        print(f"storm alarm: {t:%H:%M} UTC; share of the fall still ahead: {a:.1f}%")
    else:
        print("storm alarm: none linked to this storm")
    if s["cut"] is not None:
        print(f"prepared ship cut 75% at {s['cut']:%H:%M} UTC; "
              + (f"restored at {s['restore']:%H:%M} UTC" if s["restore"] is not None else "not restored in window"))
    for k in ("prepared", "unprepared"):
        mc = s["margin_call"][k]
        print(f"{k:10} final equity ${s['final_equity'][k]:,.0f}"
              f"{'' if mc is None else f' (margin call {mc:%H:%M} UTC)'}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true", help="one bundle per storm in storms.csv")
    ap.add_argument("--storm", help="e.g. usdjpy-2026-07-30")
    ap.add_argument("--from", dest="start", help='UTC, e.g. "2026-07-30 10:00" (default onset - 3 h)')
    ap.add_argument("--to", dest="end", help='UTC, e.g. "2026-07-30 17:00" (default onset + 3 h)')
    ap.add_argument("--out", type=Path, default=BUNDLES_DIR)
    ap.add_argument("--processed", type=Path, default=PROCESSED_DIR)
    ap.add_argument("--raw", type=Path, default=RAW_DIR)
    ap.add_argument("--live", action="store_true", help="write reports with the real model gateway")
    ap.add_argument("--model", help="report writer model (default: the gateway's META_MODEL)")
    ap.add_argument("--provider", default="meta", help="report writer provider (default meta)")
    args = ap.parse_args(argv)
    if args.all == bool(args.storm):
        ap.error("pass exactly one of --all or --storm")

    ctx = load_context(args.processed, args.raw)
    metrics = load_index_metrics(args.processed)
    if metrics is None:
        print("note: no metrics.json yet (run `python -m storm.backtest`); index metrics = null")
    print_storms(ctx.storms)
    print()

    if args.all:
        paths, index, summaries = export_all(ctx, args.out, metrics, args.live, args.model, args.provider)
        print_summaries(summaries)
        print(f"\nstorm reports ({'live gateway' if args.live else 'mock'}):")
        for s in summaries:
            print_report_line(s)
        print(f"total report cost this run: ${sum(s['report_cost_usd'] for s in summaries):.4f}")
        demo = [s for s in summaries if s["storm_id"] == "usdjpy-2026-07-30"]
        if demo:
            print()
            print_detail(demo[0])
            r = demo[0]["report"]
            print(f"report ({r['model']}): {r['text']}")
            print(f"verified={r['verified']} unverified_numbers={r['unverified_numbers']} "
                  f"inspector={r['inspector']}")
        print(f"\nwrote {len(paths)} bundles to {args.out}")
        print(f"wrote {index}")
        return

    rows = ctx.storms[ctx.storms["storm_id"] == args.storm]
    if rows.empty:
        raise SystemExit(f"{args.storm} is not in storms.csv")
    st = next(rows.itertuples())
    start, end = default_window(ctx.feats[st.pair], st)
    if args.start:
        start = pd.Timestamp(args.start, tz="UTC")
    if args.end:
        end = pd.Timestamp(args.end, tz="UTC")
    bundle, s = build_bundle(ctx, st, start, end)
    r = attach_report(bundle, args.live, args.model, args.provider)
    path = write_bundle(bundle, args.out)
    index = write_index(args.out, None, metrics)
    print_detail(s)
    print(f"report ({r['model']}, verified={r['verified']}, inspector={r['inspector']['verdict']}): "
          f"{bundle['report']['text']}")
    print(f"wrote {path}")
    print(f"wrote {index}")


if __name__ == "__main__":
    main()
