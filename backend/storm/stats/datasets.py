"""Read-only dataset adapters and auditable per-storm/day sufficient statistics."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

import numpy as np
import pandas as pd

from storm.backtest import in_split, naive_alarms, v0_alarms
from storm.chips.evaluate import EMPTY_CALENDAR, labels as chip_labels, snapshot
from storm.detector import run_detector, load_calendar
from storm.evaluate import score, market_days, v1_alarms_and_squalls, LINK_BEFORE, FALSE_AFTER, EPISODE_GAP
from storm.features import build_features, pair_features, add_comove
from storm.labels import label_all
from storm.oos.run import details
from .protocol import MAIN, REPO_ROOT, sha256, worktrees


@dataclass
class Unit:
    dataset: str
    name: str
    feats: dict
    storms: pd.DataFrame
    start: pd.Timestamp
    end: pd.Timestamp
    calendar: pd.DataFrame
    stock: bool = False
    policy_windows: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def utc(value):
    t = pd.Timestamp(value)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def cut_labels(labels, start, end):
    return labels[(labels.onset_utc >= start) & (labels.onset_utc < end)].copy()


def inventory(paths):
    return {str(p): sha256(p) for p in sorted(set(paths))}


def load_sgx():
    folder = MAIN / "data/processed"
    feats = build_features(folder)
    start, end = utc("2026-08-01"), utc("2026-09-01")
    cal = load_calendar()
    unit = Unit("sgx_august", "sgx-august", feats, cut_labels(label_all(feats, cal), start, end), start, end, cal)
    unit.policy_windows = [{"name": unit.name, "pairs": list(feats), "start": start, "end": end}]
    unit.metadata = {"source": "SGX", "group": "test", "published": json.loads((folder / "metrics.json").read_text())}
    return [unit], inventory([folder / f"{p}_SPOT.parquet" for p in feats] + [folder / "metrics.json", folder / "detector_config.json"])


def fx_labels(feats, calendar):
    # Exactly the original OOS non-USD-cross adapter; no policy conversion is invented.
    usd = {p: f for p, f in feats.items() if "USD" in (p[:3], p[3:])}
    parts = [label_all(usd, calendar)]
    for pair, feat in feats.items():
        if pair not in usd:
            labels = label_all({"USDJPY": feat}, calendar)
            labels["pair"] = pair
            labels["storm_id"] = labels.storm_id.str.replace("usdjpy-", pair.lower() + "-", regex=False)
            labels["usd_move_bp"] = np.nan
            parts.append(labels)
    nonempty = [p for p in parts if not p.empty]
    return pd.concat(nonempty, ignore_index=True) if nonempty else parts[0]


def load_oos1(root: Path):
    published = json.loads((REPO_ROOT / "docs/oos/results.json").read_text())
    folder = root / "data/external"
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    records = {w["id"]: w["pairs"] for w in manifest["windows"]}
    units, inputs = [], [manifest_path, REPO_ROOT / "docs/oos/results.json"]
    cal = load_calendar()
    for window in published["exact"]["windows"]:
        feats = {}
        for rec in records[window["id"]]:
            if rec["status"] != "usable":
                continue
            path = folder / rec["parquet"]["path"]
            if sha256(path) != rec["parquet"]["sha256"]:
                raise ValueError("OOS acquisition hash differs: " + str(path))
            inputs.append(path)
            pair = rec["pair"]
            is_usd = "USD" in (pair[:3], pair[3:])
            feats[pair] = pair_features(pd.read_parquet(path), pair if is_usd else "USDJPY")
            if not is_usd:
                feats[pair]["usd_z"] = np.nan
        if feats:
            add_comove(feats, among=tuple(p for p in feats if "USD" in (p[:3], p[3:])))
            for p in feats:
                if "USD" not in (p[:3], p[3:]):
                    feats[p]["comove"] = 0
        start, end = utc(window["start"]), utc(window["end_exclusive"])
        unit = Unit("oos_round1", window["id"], feats, cut_labels(fx_labels(feats, cal), start, end), start, end, cal)
        pairs = [p for p in feats if "USD" in (p[:3], p[3:])]
        if pairs:
            unit.policy_windows = [{"name": unit.name, "pairs": pairs, "start": start, "end": end}]
        unit.metadata = {"source": "Dukascopy", "group": window["group"], "published": window}
        units.append(unit)
    return units, inventory(inputs)


def load_chips(root: Path):
    folder = root / "data/processed/chips"
    acquisition, bars, feats = snapshot(folder)
    published = json.loads((REPO_ROOT / "docs/chips/results.json").read_text())
    new = {p: f for p, f in feats.items() if p != "NVDA"}
    start = min(f.index.min() for f in new.values())
    end = max(f.index.max() for f in new.values()) + pd.Timedelta(minutes=1)
    unit = Unit("chips_new", "chips-new-tickers", new, chip_labels(new), start, end, EMPTY_CALENDAR, True)
    unit.policy_windows = [{"name": "chips-" + p, "pairs": [p], "start": start, "end": end} for p in new]
    unit.metadata = {"source": "Yahoo", "group": "cross_ticker", "published": published,
                     "descriptive_splits": published["pooled"], "excludes": ["NVDA"]}
    return [unit], inventory([folder / "acquisition.json", REPO_ROOT / "docs/chips/results.json"] +
                            [folder / info["file"] for info in acquisition["tickers"].values() if info["status"] == "acquired"])


def load_oos2(root: Path, document: dict):
    """Rebuild the served chronological prefix; retain the published weekly reset list."""
    folder = root / "data/external/round2"
    # Protocol names its actual folder; use only a literal data path from source.
    candidates = [root / "data/external/round2", root / "data/external/round-2", root / "data/external/oos2"]
    manifest_path = next((p / "manifest.json" for p in candidates if (p / "manifest.json").exists()), None)
    if manifest_path is None:
        candidates = list((root / "data/external").glob("*/manifest.json"))
        manifest_path = next((p for p in candidates if "months" in json.loads(p.read_text())), None)
    if manifest_path is None:
        raise FileNotFoundError("No round-two monthly manifest")
    folder = manifest_path.parent
    manifest = json.loads(manifest_path.read_text())
    expected_manifest = document.get("provenance", {}).get("data_file_sha256", {}).get("manifest.json")
    if expected_manifest is None or sha256(manifest_path) != expected_manifest:
        raise ValueError("Round-two acquisition manifest differs from published provenance")
    from .protocol import registration
    if document["config"] != registration()["config"]:
        raise ValueError("Round-two configuration differs from the frozen headline")
    selected = manifest["selected_months"]
    if document["exact"]["selected_months"] != selected:
        raise ValueError("Round-two served prefix differs from published result")
    start = utc("2025-01-01")
    end = utc(manifest["selected_end"]) if selected else start
    pair_names = list(dict.fromkeys(r["pair"] for w in manifest["months"] for r in w["pairs"]))
    feats, inputs = {}, [manifest_path]
    for pair in pair_names:
        records = [r for w in manifest["months"] if w["id"] in selected for r in w["pairs"] if r["pair"] == pair]
        warmup = [r["warmup"] for w in manifest["months"] if w["id"] == "2025-01" and w["id"] in selected
                  for r in w["pairs"] if r["pair"] == pair and r.get("warmup", {}).get("status") == "usable"]
        parts = []
        for artifact in warmup[:1] + [r["parquet"] for r in records if r["status"] == "usable"]:
            path = folder / artifact["path"]
            if sha256(path) != artifact["sha256"]:
                raise ValueError("Round-two data hash mismatch: " + str(path))
            inputs.append(path)
            frame = pd.read_parquet(path)
            if parts and warmup:
                frame = frame[frame.timestamp >= start]
            parts.append(frame)
        if not parts:
            continue
        frame = pd.concat(parts, ignore_index=True).sort_values("timestamp")
        if frame.timestamp.duplicated().any():
            raise ValueError("Round-two duplicate joined timestamps")
        if int((frame.timestamp < start).sum()) >= 720 and (frame.timestamp >= start).any():
            feats[pair] = pair_features(frame, pair)
    add_comove(feats) if feats else None
    cal = load_calendar()
    unit = Unit("oos_round2", "chronological-2025", feats, cut_labels(label_all(feats, cal), start, end), start, end, cal)
    exact = document.get("exact", document)
    # Schema is checked explicitly when the artifact arrives, rather than guessing silently.
    weeks = exact.get("weekly_policy", {}).get("weeks", exact.get("weeks", []))
    if not weeks:
        weeks = [w for p in exact.get("per_pair", []) for w in p.get("weekly_policy", p.get("weeks", []))]
    if not weeks and feats:
        raise ValueError("Round-two weekly policy schema requires explicit review")
    unit.policy_windows = [{"name": str(w["pair"]) + "/" + str(w["from_utc"]), "pairs": [w["pair"]],
                            "start": utc(w["from_utc"]), "end": utc(w["to_utc"]), "carry_in": True}
                           for w in weeks if w["status"] == "usable"]
    unit.metadata = {"source": "Dukascopy", "group": "chronological", "published": document,
                     "selected_months": selected, "partial": len(selected) < 12,
                     "planned_pair_months": exact["planned_pair_months"],
                     "usable_pair_months": exact["usable_pair_months"],
                     "usable_pair_weeks": exact["policy"]["usable_pair_weeks"],
                     "planned_pair_weeks": exact["policy"]["planned_pair_weeks"],
                     "published_status": exact["status"]}
    return [unit], inventory(inputs)


def load_all(include_round2: bool = False):
    trees = worktrees()
    units, hashes = load_sgx()
    for loader, branch in ((load_oos1, "lane/cx-oos"), (load_chips, "lane/cx-chips")):
        more, inputs = loader(trees[branch])
        units.extend(more)
        hashes.update(inputs)
    if include_round2:
        path = REPO_ROOT / "docs/stats/round2-source-results.json"
        more, inputs = load_oos2(trees["lane/cx-oos2"], json.loads(path.read_text()))
        units.extend(more)
        hashes.update(inputs)
        hashes[str(path)] = sha256(path)
    return units, hashes


def detect(unit, cfg):
    def side(pair):
        return 1 if unit.stock or pair.startswith("USD") else -1 if pair.endswith("USD") else 0
    return {p: run_detector(f, unit.calendar, cfg, exposure=side(p)) for p, f in unit.feats.items()}


def alarms_for(unit, detections, method="v1"):
    if method == "v1":
        return v1_alarms_and_squalls(detections, unit.start, unit.end)[0]
    return {p: in_split(naive_alarms(f) if method == "naive" else v0_alarms(f, unit.calendar), unit.start, unit.end)
            for p, f in unit.feats.items()}


def false_openings(alarms, storms):
    times = []
    for p, items in alarms.items():
        mine = storms[storms.pair == p]
        for t, _ in items:
            if not ((mine.onset_utc - LINK_BEFORE <= t) & (t <= mine.end_utc + FALSE_AFTER)).any():
                times.append(t)
    openings, opened = [], None
    for t in sorted(times):
        if opened is None or t - opened > EPISODE_GAP:
            openings.append(t)
            opened = t
    return times, openings


def daily_rows(unit, alarms):
    idx = pd.DatetimeIndex([], tz="UTC")
    for f in unit.feats.values():
        idx = idx.union(f.index[(f.index >= unit.start) & (f.index < unit.end)])
    _, openings = false_openings(alarms, unit.storms)
    dates = idx.floor("D")
    counts = pd.Series(1, index=dates).groupby(level=0).sum()
    opened = pd.Series([t.floor("D") for t in openings]).value_counts()
    rows = [{"dataset": unit.dataset, "unit": unit.name, "date": str(t.date()), "observed_minutes": int(n),
             "episodes": int(opened.get(t, 0))} for t, n in counts.items()]
    trading = []
    if unit.stock:
        et = idx.tz_convert("America/New_York").strftime("%Y-%m-%d")
        es = pd.Series([t.tz_convert("America/New_York").strftime("%Y-%m-%d") for t in openings]).value_counts()
        trading = [{"dataset": unit.dataset, "unit": unit.name, "date": str(d), "trading_days": 1,
                    "episodes": int(es.get(d, 0))} for d in sorted(set(et))]
    return rows, trading


def evaluate_unit(unit, alarms):
    m = score(alarms, unit.storms, {p: f.mid for p, f in unit.feats.items()},
              market_days(unit.feats, unit.start, unit.end))
    details(unit.storms, m)
    for row in m["per_storm"]:
        row.update(dataset=unit.dataset, unit=unit.name)
        time = utc(row["onset_utc"])
        row["block"] = str((time.tz_convert("America/New_York") if unit.stock else time).date())
    daily, trading = daily_rows(unit, alarms)
    m["daily"] = daily
    m["trading_daily"] = trading
    return m
