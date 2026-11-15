"""One frozen evaluation, or a read-only recomputation: python -m storm.oos.run --verify."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np
import pandas as pd
import pyarrow

from storm.detector import load_calendar, run_detector
from storm.evaluate import (FALSE_AFTER, LINK_BEFORE, for_display, market_days,
                            observed_minutes, score, v1_alarms_and_squalls)
from storm.exposure import book_for, policy_backtest
from storm.features import build_features, pair_features
from storm.labels import label_all
from storm.paths import REPO_ROOT
from .protocol import (DATA, DOCS, REGISTRATION, canonical, check_frozen,
                       registration_commit, sha256)

RESULTS = DOCS / "results.json"
CROSS_POLICY_REASON = "Frozen USD policy engine has no USD valuation for this non-USD cross; no extra conversion pair was registered."


def load_window_features(window: dict, records: list[dict]) -> dict:
    usable = [r["pair"] for r in records if r["status"] == "usable"]
    usd = tuple(p for p in usable if "USD" in (p[:3], p[3:]))
    folder = DATA / window["id"] / "processed"
    feats = build_features(folder, pairs=usd) if usd else {}
    for pair in usable:
        if pair not in usd:
            # The price-only computation is identical. The surrogate supplies only
            # the USD-sign field, which is discarded, and w_comove is frozen at zero.
            feat = pair_features(pd.read_parquet(folder / f"{pair}_SPOT.parquet"), "USDJPY")
            feat["usd_z"] = np.nan
            feat["comove"] = 0
            feats[pair] = feat
    return {p: feats[p] for p in usable}


def window_labels(feats: dict, calendar: pd.DataFrame) -> pd.DataFrame:
    usd = {p: f for p, f in feats.items() if "USD" in (p[:3], p[3:])}
    parts = [label_all(usd, calendar)]
    for pair, feat in feats.items():
        if pair not in usd:
            labels = label_all({"USDJPY": feat}, calendar)
            labels["pair"] = pair
            labels["storm_id"] = labels["storm_id"].str.replace("usdjpy-", pair.lower() + "-", regex=False)
            labels["usd_move_bp"] = np.nan
            parts.append(labels)
    nonempty = [p for p in parts if not p.empty]
    combined = pd.concat(nonempty, ignore_index=True) if nonempty else parts[0]
    return combined.sort_values(["onset_utc", "pair"]).reset_index(drop=True)


def details(storms: pd.DataFrame, metrics: dict) -> None:
    by_id = {r["storm_id"]: r for r in metrics["per_storm"]}
    for storm in storms.itertuples():
        row = by_id[storm.storm_id]
        row.update({"pair": storm.pair, "kind": storm.kind,
                    "onset_utc": storm.onset_utc.isoformat(),
                    "first_onset_utc": storm.first_onset_utc.isoformat(),
                    "trough_utc": storm.trough_utc.isoformat(),
                    "end_utc": storm.end_utc.isoformat(), "move_bp": storm.move_bp,
                    "duration_min": storm.duration_min})


def false_rows(alarms: dict, storms: pd.DataFrame) -> list[dict]:
    rows = []
    for pair, items in alarms.items():
        mine = storms[storms["pair"] == pair]
        for alarm, clear in items:
            if not ((mine["onset_utc"] - LINK_BEFORE <= alarm) &
                    (alarm <= mine["end_utc"] + FALSE_AFTER)).any():
                rows.append({"pair": pair, "alarm_utc": alarm.isoformat(),
                             "clear_utc": None if clear is None else clear.isoformat()})
    return sorted(rows, key=lambda r: (r["alarm_utc"], r["pair"]))


def state_metrics(metrics: dict, feats: dict, detections: dict, start, end) -> None:
    minutes = sum(int(((r.frame["state"] == 2) & (r.frame.index >= start) &
                       (r.frame.index < end)).sum()) for r in detections.values())
    observed = observed_minutes(feats, start, end)
    metrics.update({"storm_state_minutes": minutes, "observed_pair_minutes": observed,
                    "storm_state_share_pct": 100 * minutes / observed if observed else None})


def policy_totals(windows: list[dict]) -> dict:
    policies = [w["policy"]["result"] for w in windows if w["policy"]["status"] == "supported"]
    out = {"independent_reset_books": len(policies), "synthetic": True}
    for ship in ("prepared", "unprepared"):
        paths = [p[ship] for p in policies]
        out[ship] = {"pnl_usd": sum(p["final_equity_usd"] - 1_000_000 for p in paths),
                     **{key: sum(p[key] for p in paths) for key in
                        ("spread_cost_usd", "fills", "margin_calls", "cuts", "restores")},
                     "median_window_max_drawdown_usd": None if not paths else float(np.median([p["max_drawdown_usd"] for p in paths])),
                     "max_window_drawdown_usd": None if not paths else max(p["max_drawdown_usd"] for p in paths),
                     "median_window_max_drawdown_pct": None if not paths else float(np.median([p["max_drawdown_pct"] for p in paths])),
                     "max_window_drawdown_pct": None if not paths else max(p["max_drawdown_pct"] for p in paths)}
    return out


def evaluate(spec: dict, manifest: dict) -> dict:
    calendar, cfg = load_calendar(), spec["config"]
    all_windows, pools = [], []
    manifest_windows = {w["id"]: w for w in manifest["windows"]}
    if set(manifest_windows) != {w["id"] for w in spec["windows"]}:
        raise ValueError("acquisition windows differ from registration")
    for window in spec["windows"]:
        records = manifest_windows[window["id"]]["pairs"]
        if [r["pair"] for r in records] != window["pairs"]:
            raise ValueError("acquisition pair list differs from registration")
        feats = load_window_features(window, records)
        start, end = (pd.Timestamp(window[k], tz="UTC") for k in ("start", "end_exclusive"))
        labels = window_labels(feats, calendar)
        storms = labels[(labels["onset_utc"] >= start) & (labels["onset_utc"] < end)].copy()
        detections = {p: run_detector(f, calendar, cfg) for p, f in feats.items()}
        alarms, squalls = v1_alarms_and_squalls(detections, start, end)
        mids = {p: f["mid"] for p, f in feats.items()}
        days = market_days(feats, start, end)
        metrics = score(alarms, storms, mids, days, squalls)
        state_metrics(metrics, feats, detections, start, end)
        details(storms, metrics)
        false = false_rows(alarms, storms)
        supported = tuple(p for p in feats if "USD" in (p[:3], p[3:]))
        policy = {"status": "supported" if supported else "unsupported", "pairs": list(supported),
                  "excluded_pairs": [p for p in feats if p not in supported], "result": None}
        if supported:
            policy["result"] = policy_backtest(feats, cfg, start, end, calendar, book_for(supported))
        else:
            policy["reason"] = CROSS_POLICY_REASON if feats else "No usable registered USD pair."
        per_pair = []
        for record in records:
            pair = record["pair"]
            row = dict(record)
            row["metrics"] = None
            row["policy"] = {"status": "unusable", "reason": record["reason"]}
            if pair in feats:
                mine = storms[storms["pair"] == pair]
                pair_days = market_days({pair: feats[pair]}, start, end)
                _, pair_squalls = v1_alarms_and_squalls({pair: detections[pair]}, start, end)
                row["metrics"] = score({pair: alarms[pair]}, mine, {pair: mids[pair]}, pair_days, pair_squalls)
                state_metrics(row["metrics"], {pair: feats[pair]}, {pair: detections[pair]}, start, end)
                details(mine, row["metrics"])
                row["policy"] = ({"status": "supported", "result": policy_backtest(
                    feats, cfg, start, end, calendar, book_for(pair))} if pair in supported
                    else {"status": "unsupported", "reason": CROSS_POLICY_REASON})
            per_pair.append(row)
        result = {**window, "planned_pairs": len(records), "usable_pairs": len(feats),
                  "pairs": per_pair, "metrics": metrics, "false_alarms": false,
                  "policy": policy,
                  "alarms": [{"pair": p, "alarm_utc": a.isoformat(),
                              "clear_utc": None if c is None else c.isoformat()}
                             for p, items in alarms.items() for a, c in items]}
        all_windows.append(result)
        # Keys distinguish independent windows even when the physical pair repeats.
        pooled_storms = storms.copy()
        pooled_storms["pair"] = window["id"] + "/" + pooled_storms["pair"]
        pooled_storms["storm_id"] = window["id"] + "/" + pooled_storms["storm_id"]
        pools.append({"window": result, "storms": pooled_storms,
                      "alarms": {window["id"] + "/" + p: a for p, a in alarms.items()},
                      "mids": {window["id"] + "/" + p: m for p, m in mids.items()},
                      "squalls": squalls, "days": days})
        print(f"{window['id']}: {len(feats)}/{len(records)} usable pairs, {metrics['storms']} storms", flush=True)
    totals = {}
    for group in ("events", "ordinary", "all"):
        selected = [p for p in pools if group == "all" or p["window"]["group"] == group]
        alarms = {k: v for p in selected for k, v in p["alarms"].items()}
        mids = {k: v for p in selected for k, v in p["mids"].items()}
        storms = pd.concat([p["storms"] for p in selected], ignore_index=True)
        metrics = score(alarms, storms, mids, sum(p["days"] for p in selected), sum(p["squalls"] for p in selected))
        details(storms, metrics)
        metrics["storm_state_minutes"] = sum(p["window"]["metrics"]["storm_state_minutes"] for p in selected)
        metrics["observed_pair_minutes"] = sum(p["window"]["metrics"]["observed_pair_minutes"] for p in selected)
        metrics["storm_state_share_pct"] = (100 * metrics["storm_state_minutes"] / metrics["observed_pair_minutes"]
                                             if metrics["observed_pair_minutes"] else None)
        totals[group] = {"planned_pairs": sum(p["window"]["planned_pairs"] for p in selected),
                         "usable_pairs": sum(p["window"]["usable_pairs"] for p in selected),
                         "metrics": metrics, "policy": policy_totals([p["window"] for p in selected])}
    per_pair_totals = {}
    for pair in sorted({p for w in spec["windows"] for p in w["pairs"]}):
        selected = [(w, p) for w in all_windows for p in w["pairs"] if p["pair"] == pair]
        keys = {w["id"] + "/" + pair for w, p in selected if p["status"] == "usable"}
        storms = pd.concat([p["storms"][p["storms"]["pair"].isin(keys)] for p in pools], ignore_index=True)
        metrics = score({k: v for p in pools for k, v in p["alarms"].items() if k in keys}, storms,
                        {k: v for p in pools for k, v in p["mids"].items() if k in keys},
                        sum(p["metrics"]["days"] for w, p in selected if p["metrics"] is not None))
        details(storms, metrics)
        per_pair_totals[pair] = {"planned_windows": len(selected), "usable_windows": len(keys), "metrics": metrics}
    return {"windows": all_windows, "totals": totals, "per_pair_totals": per_pair_totals}


def file_inventory(manifest: dict) -> dict:
    # Read every acquisition artifact, including failure diagnostics, rather than
    # trusting the manifest's assertion that some path was unusable.
    files = {str(p.relative_to(DATA)): sha256(p) for p in sorted(DATA.rglob("*")) if p.is_file()}
    for window in manifest["windows"]:
        for record in window["pairs"]:
            expected = list(record["raw"].values())
            if record["status"] == "usable":
                expected.append(record["parquet"])
            for artifact in expected:
                if files.get(artifact["path"]) != artifact["sha256"]:
                    raise ValueError(f"missing/changed acquisition file: {artifact['path']}")
    return files


def recompute() -> dict:
    spec = check_frozen()
    manifest = json.loads((DATA / "manifest.json").read_text())
    if manifest["preregistration_sha256"] != sha256(REGISTRATION):
        raise ValueError("acquisition used a different preregistration")
    provenance = {"preregistration_sha256": sha256(REGISTRATION),
                  "preregistration_commit": registration_commit(),
                  "frozen_config_sha256": spec["config_sha256"],
                  "source_config_file_sha256": spec["source_config_file_sha256"],
                  "code_fingerprint": spec["code_fingerprint"],
                  "calendar_content_sha256": spec["calendar_content_sha256"],
                  "metrics_document_sha256": spec["metrics_document_sha256"],
                  "amendment_sha256": {p.name: sha256(p) for p in sorted(DOCS.glob("amendment-*.md"))},
                  "acquisition_notes_sha256": sha256(DOCS / "acquisition_notes.md"),
                  "downloader": spec["downloader"], "data_file_sha256": file_inventory(manifest),
                  "oos_source_sha256": {str(p.relative_to(REPO_ROOT)): sha256(p)
                                        for p in sorted(Path(__file__).parent.iterdir())
                                        if p.suffix in (".py", ".cjs")}}
    exact = evaluate(spec, manifest)
    return {"schema_version": 1, "provenance": provenance, "config": spec["config"],
            "exact": exact, "display": for_display(exact)}


def first_difference(left, right, path="root") -> str | None:
    if type(left) is not type(right):
        return f"{path}: type differs"
    if isinstance(left, dict):
        if left.keys() != right.keys():
            return f"{path}: keys differ"
        for key in left:
            if diff := first_difference(left[key], right[key], f"{path}.{key}"):
                return diff
    elif isinstance(left, list):
        if len(left) != len(right):
            return f"{path}: length differs"
        for i, (a, b) in enumerate(zip(left, right)):
            if diff := first_difference(a, b, f"{path}[{i}]"):
                return diff
    elif left != right:
        return f"{path}: value differs"
    return None


def main() -> None:
    from .report import render
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--data-dir", type=Path, default=DATA,
                    help="original acquisition artifacts for historical --verify")
    args = ap.parse_args()
    if not args.verify and (RESULTS.exists() or (DOCS / "run_started.json").exists()):
        raise SystemExit("results/one-shot marker exists; use --verify; refusing another evaluation")
    if args.verify:
        from .verify import verify_saved
        verify_saved(args.data_dir)
    else:
        # Check provenance and local acquisition integrity before claiming a run.
        check_frozen()
        manifest = json.loads((DATA / "manifest.json").read_text())
        file_inventory(manifest)
        started = {"started_utc": pd.Timestamp.now(tz="UTC").isoformat(),
                   "preregistration_sha256": sha256(REGISTRATION)}
        with (DOCS / "run_started.json").open("x") as marker:
            marker.write(json.dumps(started, indent=2) + "\n")
        result = recompute()
        result["execution"] = {**started, "finished_utc": pd.Timestamp.now(tz="UTC").isoformat(),
                               "python": sys.version.split()[0], "platform": platform.system(),
                               "pandas": pd.__version__, "numpy": np.__version__, "pyarrow": pyarrow.__version__,
                               "wrapper_commit_at_run": subprocess.check_output(
                                   ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()}
        with RESULTS.open("x") as output:
            output.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
        (DOCS / "results.md").write_text(render(result))
        print(f"wrote {RESULTS} and results.md")


if __name__ == "__main__":
    main()
