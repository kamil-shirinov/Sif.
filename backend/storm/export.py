"""Write replay bundles per contracts/replay_bundle.md, and index.json.

    python -m storm.export --all
    python -m storm.export --storm usdjpy-2026-07-30 [--from "2026-07-30 10:00" --to "2026-07-30 17:00"]
    python -m storm.export --all --live [--model ID --provider meta]   (real model gateway)

Runs ingest first if data/processed is missing, then features -> labels (rewrites
storms.csv) -> detector v1 (data/processed/detector_config.json) -> policy v1 ships ->
bundles. --all writes one bundle per storm in storms.csv, each from 3 hours before onset
to 3 hours after (trimmed to the bars that exist; see the next paragraph), and an index.json listing exactly
those bundles plus any Yahoo equity bundle already in the folder (storm.equity), whose
report is rewritten by the same writer. Times are UTC; the window is inclusive.

No replay opens inside an alarm. If a danger alarm raised before the 3-hour window is still in
force at its first bar, the policy would already have cut there, so the window starts 10
minutes before that alarm instead (storm_window, exposure.cut_since): the replay shows the
alarm, the cut and the restore at the all-clear, and both ships start at full size on calm
water. build_bundle refuses a window (for instance one set with --from) that opens inside an
alarm.

Each bundle's ship trades the storm's pair: a SYNTHETIC book long USD 20,000,000 against
the pair's other currency (short EUR for EURUSD), $1,000,000 equity, 2.5% maintenance.
The prepared ship follows policy v1 (storm.exposure); the unprepared ship holds. A cut or
restore fills at the open bid or ask of the bar after its signal (storm.exposure), so
`cut_i` is the fill frame, one after the alarm; the event text states the fill price.

An alarm event's move_ahead_pct is set only when storm.evaluate.alarm_matches (the same
matcher the evaluator uses) links it to the replay's storm: in [onset - 60 min, trough]
and its episode still in force at onset. The stress menu is point in time
(storm.exposure.stress_menu): storms labelled on the bars up to the exposure snapshot
(the bar before onset) whose trough came before it.

index.json metrics come from data/processed/metrics.json, and only when its provenance
(written by storm.backtest: SHA-256 of the spot parquets, contracts/calendar.csv and the
calendar content in effect, detector_config.json, and the calculation code's fingerprint)
matches the inputs and code now; otherwise export refuses to run.

Each bundle carries a storm report from storm.ai.report (facts_from_bundle, then
write_report): the deterministic mock by default (LLM_MODE is forced to mock), the real
gateway with --live (the budget guard applies). A scheduled storm's facts add the
calendar event's name and time, so the report can state the timing, never a cause.

Additions documented in contracts/replay_bundle.md (still schema_version 1, all optional):
  ships.<name>.restore_i   first restore after the first cut (int or null)
  event types              squall, fair_wind, cut, restore (cut_i stays the first cut)
  watch events             add `event` (the calendar event's name)
  storm.event, event_i     for a scheduled storm: the calendar event and its frame
  storm.first_onset_i      frame of the storm's first triggering window (<= onset_i; negative
                           when it began before the replay window)
  storm.alarm_i, alarm_minutes, alarm_minutes_first_onset, move_ahead_pct,
  move_ahead_pct_first_onset
                           the storm-level alarm storm.evaluate links to the storm (as scored
                           in metrics.json) against onset and first_onset; null if none
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

import numpy as np
import pandas as pd

from . import ingest
from .ai.report import facts_from_bundle, write_report
from .backtest import index_metrics, provenance, provenance_mismatches
from .detector import load_calendar, load_config, run_detector
from .evaluate import alarm_matches, link_alarm, move_ahead_pct, per_storm_row
from .exposure import (Quotes, book_for, cut_since, exposure_snapshot, leg_exposure, policy_actions,
                       ships, stress_menu)
from .features import PAIRS, build_features
from .labels import label_all, print_storms, write_storms
from .paths import BUNDLES_DIR, CALENDAR_CSV, PROCESSED_DIR, RAW_DIR

SCHEMA_VERSION = 1
STEP_S = 60
MAX_FILL_MINUTES = 5          # a longer hole inside the window is an error, not a fill
WINDOW_BEFORE = pd.Timedelta(hours=3)
WINDOW_AFTER = pd.Timedelta(hours=3)
WINDOW_LEAD = pd.Timedelta(minutes=10)   # calm minutes shown before an earlier alarm the window must include
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
          open_mask=None) -> tuple[pd.DataFrame, int, "np.ndarray"]:
    """Reindex onto the one-minute frame grid; short holes are forward-filled as flat bars.

    `open_mask` (bool per grid minute, default all open) marks when the market trades: a
    closed stretch of any length is filled flat at the last price; a hole longer than
    MAX_FILL_MINUTES while open is an error. Returns (grid, holes filled while open,
    traded: True on frames with a real bar, where a trade can fill)."""
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
    return g, int(hole.sum()), (~missing).to_numpy()


def default_window(feat: pd.DataFrame, storm, events: list[dict] | None = None
                   ) -> tuple[pd.Timestamp, pd.Timestamp]:
    """onset - 3 h .. onset + 3 h, trimmed to the first and last bars inside it.

    Given the detector's `events`, the start moves earlier until the replay no longer opens
    inside a danger alarm raised before it (exposure.cut_since): the window then begins
    WINDOW_LEAD before that alarm, so the replay shows the alarm, the cut and the restore at
    the all-clear, and both ships start at full size on calm water."""
    lo, hi = storm.onset_utc - WINDOW_BEFORE, storm.onset_utc + WINDOW_AFTER
    bars = feat.index[(feat.index >= lo) & (feat.index <= hi)]
    start, end = bars[0], bars[-1]
    while events is not None and (since := cut_since(events, start)) is not None:
        start = feat.index[feat.index >= since - WINDOW_LEAD][0]
    return start, end


def storm_window(ctx: Context, storm) -> tuple[pd.Timestamp, pd.Timestamp]:
    """The storm's replay window: default_window, widened by the detector's events (above)."""
    feat = ctx.feats[storm.pair]
    res = run_detector(feat, ctx.calendar, ctx.cfg, exposure=leg_exposure(storm.pair))
    return default_window(feat, storm, res.events)


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
    g, filled, traded = _grid(feat.join(res.frame[["risk", "state"]]), start, end)
    idx = g.index
    n = len(idx)

    def frame_of(t: pd.Timestamp) -> int:
        return int((t.floor("min") - idx[0]) / pd.Timedelta(seconds=STEP_S))

    onset_i, trough_i = frame_of(storm.onset_utc), frame_of(storm.trough_utc)
    if not (0 <= onset_i < n and 0 <= trough_i < n):
        raise ValueError(f"{storm.storm_id}: onset or trough outside the window")
    first_onset_i = frame_of(storm.first_onset_utc)      # may be < 0: before the replay window
    scheduled = storm.kind == "scheduled"
    event_i = frame_of(storm.event_utc) if scheduled else None
    if scheduled and not 0 <= event_i < n:
        raise ValueError(f"{storm.storm_id}: scheduled event outside the window")

    if (since := cut_since(res.events, idx[0])) is not None:
        raise ValueError(f"{storm.storm_id}: the window starts at {idx[0]:%Y-%m-%d %H:%M} UTC inside the danger "
                         f"alarm raised at {since:%Y-%m-%d %H:%M} UTC; the prepared ship would hold cargo the "
                         "policy cut. Start before the alarm (export.default_window does)")
    win = _visible_events([e for e in res.events if idx[0] <= e["time"] <= idx[-1]], g["state"], frame_of)
    mid = g["mid"].to_numpy(dtype=float)
    quotes = Quotes.from_frame(g, traded)
    paths = ships({pair: quotes}, book, policy_actions({pair: win}, frame_of))
    prep = paths["prepared"]

    def ahead(e: dict) -> float | None:
        if not alarm_matches(e["time"], e.get("clear"), storm):
            return None
        a = move_ahead_pct(e["time"], storm, feat["mid"])
        return None if a is None else _r(a, 1)

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
        ev = {"i": i, "type": e["type"], "text": _event_text(e, pair, ctx.cfg, ahead(e) is not None)}
        if e["type"] == "alarm":
            ev["move_ahead_pct"] = ahead(e)
        events.append(ev)
    events += trade_events(prep, pair, book["cut_fraction"])
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
            "first_onset_i": first_onset_i,
            **storm_alarm_fields(storm, res.storm_alarms(), feat["mid"], frame_of),
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
        "stress": stress_menu(ctx.feats, ctx.calendar, paths["unprepared"], {pair: quotes}, book, as_of_i,
                              idx[as_of_i]),
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
        "fills": [{**f, "utc": idx[f["i"]]} for f in prep.fills],
        "stress_n": len(bundle["stress"]),
        "restore": idx[prep.restore_i] if prep.restore_i is not None else None,
        "final_equity": {k: float(p.equity[-1]) for k, p in paths.items()},
        "margin_call": {k: (idx[p.margin_call_i] if p.margin_call_i is not None else None)
                        for k, p in paths.items()},
    }
    return bundle, summary


def storm_alarm_fields(storm, alarms: list, mid: pd.Series, frame_of) -> dict:
    """The storm-level alarm that storm.evaluate links to this storm (direction-agnostic,
    the one metrics.json scores), as frame, minutes after onset and after first_onset, and
    share of the move still ahead against each. All null when no alarm matched."""
    alarm = link_alarm(alarms, storm)
    row = per_storm_row(storm, alarm, mid)
    pct = lambda v: None if v is None else _r(v, 1)  # noqa: E731
    return {"alarm_i": None if alarm is None else frame_of(alarm),
            "alarm_minutes": row["minutes"], "alarm_minutes_first_onset": row["minutes_first_onset"],
            "move_ahead_pct": pct(row["move_ahead_pct"]),
            "move_ahead_pct_first_onset": pct(row["move_ahead_pct_first_onset"])}


def trade_events(prep, symbol: str, cut_fraction: float) -> list[dict]:
    """cut and restore events at their fill frames, stating each fill's price and side."""
    pct = round(cut_fraction * 100)
    out = []
    for f in prep.fills:
        if f["action"] not in ("cut", "restore"):
            continue
        at = "" if f["price"] == f["mid"] else f" ({'ask' if f['side'] == 'buy' else 'bid'})"
        what = f"cuts its {symbol} position by {pct}%" if f["action"] == "cut" else f"restores its full {symbol} position"
        out.append({"i": f["i"], "type": f["action"],
                    "text": f"Prepared ship {what} at {f['price']:.6g}{at}, the next bar's open"})
    return out


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
    if st.get("alarm_i") is not None:
        # An earlier alarm in the window (an earlier move's, linked to no storm) is not this
        # storm's warning: the report states the timing of the alarm the evaluator links.
        first = (st["alarm_i"] - st["onset_i"]) * bundle["step_s"] / 60
        facts["alarm_events"] = [e for e in facts["alarm_events"]
                                 if e["type"] != "alarm" or e["minutes_from_onset"] >= first]
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


class StaleMetrics(RuntimeError):
    """metrics.json was computed from other data, calendar or config than the files now on disk."""


def load_index_metrics(processed: Path = PROCESSED_DIR, calendar_path: Path = CALENDAR_CSV,
                       calendar: pd.DataFrame | None = None) -> dict | None:
    """index.json metrics from metrics.json; refuses (StaleMetrics) unless its provenance
    matches the spot data, calendar (file and the content in effect: `calendar`, default
    loaded from `calendar_path`), detector config and calculation code now."""
    path = processed / "metrics.json"
    if not path.exists():
        return None
    metrics = json.loads(path.read_text())
    now = provenance(processed, calendar_path, processed / "detector_config.json", calendar)
    bad = provenance_mismatches(metrics.get("provenance"), now)
    if bad:
        raise StaleMetrics(f"{path} does not match the inputs or code now ({'; '.join(bad)}); "
                           "re-run `python -m storm.tune` if the data or labels changed, then "
                           "`python -m storm.backtest`")
    return index_metrics(metrics)


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
    """index.json lists `bundles` (bundle, file name), or else every non-synthetic bundle in
    out_dir, keeping the order of the index.json already there (new files go last)."""
    if bundles is None:
        bundles = scan_bundles(out_dir)
        old = out_dir / "index.json"
        try:
            order = {e["file"]: k for k, e in enumerate(json.loads(old.read_text())["storms"])}
        except (OSError, ValueError, KeyError, TypeError):
            order = {}
        bundles = sorted(bundles, key=lambda bn: order.get(bn[1], len(order)))
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
        start, end = storm_window(ctx, st)
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
    for f in s.get("fills", []):
        print(f"prepared ship {f['action']} fill {f['utc']:%H:%M} UTC: {f['side']} {f['qty']:,.0f} at "
              f"{f['price']:.6g} ({f['at']}; mid {f['mid']:.6g}; cost vs mid ${f['cost_usd']:,.0f})")
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
    try:
        metrics = load_index_metrics(args.processed, CALENDAR_CSV, ctx.calendar)
    except StaleMetrics as e:
        raise SystemExit(f"refusing to export: {e}")
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
    start, end = storm_window(ctx, st)
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
