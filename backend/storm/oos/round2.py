"""One preregistered chronological 2025 evaluation; no parameter search."""
import argparse
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

from storm.detector import load_calendar, run_detector
from storm.evaluate import EPISODE_GAP, _median, for_display, market_days, score, v1_alarms_and_squalls
from storm.exposure import aligned_quotes, book_for, cut_since, leg_exposure, max_drawdown, policy_actions, ships
from storm.features import add_comove, pair_features
from storm.labels import label_all
from .protocol import DOCS, REPO_ROOT, sha256
from .protocol2 import DATA2, REGISTRATION2, check_frozen2, registration2_commit, runtime
from .run import details, false_rows, first_difference, state_metrics

RESULTS2 = DOCS / "results-2.json"
START = pd.Timestamp("2025-01-01", tz="UTC")


def selected_prefix(spec, manifest):
    if manifest["preregistration_sha256"] != sha256(REGISTRATION2):
        raise ValueError("round-two acquisition used another registration")
    if [w["id"] for w in manifest["months"]] != [w["id"] for w in spec["months"]]:
        raise ValueError("acquisition did not account for every planned month")
    selected, stopped = [], False
    for window in manifest["months"]:
        if [r["pair"] for r in window["pairs"]] != spec["pairs"]:
            raise ValueError("acquisition pair order/list differs from registration")
        complete = window["completed"]
        if complete and stopped:
            raise ValueError("completed months must form a chronological prefix")
        if complete:
            if not all(r["status"] in ("usable", "unusable") for r in window["pairs"]):
                raise ValueError("selected month has unfinished pairs")
            if not all(pd.Timestamp(r["finished_utc"]) < pd.Timestamp(spec["deadline"]["hard_acquisition_stop_utc"])
                       for r in window["pairs"]):
                raise ValueError("selected month finished after hard cutoff")
            selected.append(window["id"])
        else:
            stopped = True
    if selected != manifest["selected_months"]:
        raise ValueError("manifest prefix does not match completed chronological months")
    expected_end = next((w["end_exclusive"] for w in spec["months"] if selected and w["id"] == selected[-1]), None)
    if manifest["selected_end"] != expected_end:
        raise ValueError("manifest end does not match selected prefix")
    return selected


def inventory(manifest):
    files = {str(p.relative_to(DATA2)): sha256(p) for p in sorted(DATA2.rglob("*")) if p.is_file()}
    for w in manifest["months"]:
        for r in w["pairs"]:
            artifacts = list(r["raw"].values())
            if r["status"] == "usable":
                artifacts.append(r["parquet"])
            if r.get("warmup", {}).get("status") == "usable":
                artifacts.append(r["warmup"])
            for item in artifacts:
                if files.get(item["path"]) != item["sha256"]:
                    raise ValueError("missing/changed round-two artifact: " + item["path"])
    return files


def transport_audit(manifest):
    blocked_path = DATA2 / "exhausted-urls.json"
    blocked = set(json.loads(blocked_path.read_text())) if blocked_path.exists() else set()
    counts, cache_hits, cached_failures = {}, 0, 0
    for phase in (DATA2 / "https-interrupted-pass", DATA2):
        for window in manifest["months"]:
            folder = phase / window["id"] / "raw"
            for path in folder.glob("*_http.jsonl"):
                for line in path.read_text().splitlines():
                    row = json.loads(line)
                    if row.get("network", True):
                        if phase == DATA2 and row["url"] in blocked:
                            raise ValueError("exhausted artifact was queried again: " + row["url"])
                        counts[row["url"]] = counts.get(row["url"], 0) + 1
                    else:
                        cache_hits += int(row.get("cache", False))
                        cached_failures += int(row.get("exhausted_previous_pass", False))
    if any(count > 4 for count in counts.values()):
        raise ValueError("more than initial plus three known network attempts for a daily artifact")
    return {"known_network_requests": sum(counts.values()), "unique_queried_urls": len(counts),
            "maximum_known_requests_per_url": max(counts.values(), default=0),
            "conservatively_exhausted_urls": len(blocked), "content_cache_hits": cache_hits,
            "cached_unavailable_attempts_without_network": cached_failures,
            "exhausted_urls_never_requeried": True,
            "original_unlogged_socket_failures_treated_conservatively": True}


def load_features(spec, manifest, selected):
    feats = {}
    for pair in spec["pairs"]:
        warmups = [r["warmup"] for w in manifest["months"] if w["id"] == "2025-01" and w["id"] in selected
                   for r in w["pairs"] if r["pair"] == pair and r.get("warmup", {}).get("status") == "usable"]
        parts = [pd.read_parquet(DATA2 / r["parquet"]["path"])
                 for w in manifest["months"] if w["id"] in selected
                 for r in w["pairs"] if r["pair"] == pair and r["status"] == "usable"]
        if warmups:
            parts = [pd.read_parquet(DATA2 / warmups[0]["path"])] + [f[f["timestamp"] >= START] for f in parts]
        # A missing initial warm-up makes this pair unavailable for detection,
        # rather than treating January's first returns as warmed-up observations.
        if not parts:
            continue
        bars = pd.concat(parts, ignore_index=True).sort_values("timestamp")
        if bars["timestamp"].duplicated().any():
            raise ValueError("duplicate monthly joined timestamps for " + pair)
        if int((bars["timestamp"] < START).sum()) < 720:
            continue
        if not (bars["timestamp"] >= START).any():
            continue
        feats[pair] = pair_features(bars, pair)
    return add_comove(feats) if feats else {}


def episode_openings(rows):
    opened, times = None, []
    for row in sorted(rows, key=lambda r: (r["alarm_utc"], r["pair"])):
        when = pd.Timestamp(row["alarm_utc"])
        if opened is None or when - opened > EPISODE_GAP:
            times.append(when)
            opened = when
    return times


def monthly_metrics(annual, false, alarms, detections, feat, start, end):
    rows = [r for r in annual["per_storm"] if start <= pd.Timestamp(r["onset_utc"]) < end]
    alarmed = [r for r in rows if r["alarm_utc"] is not None]
    f = [r for r in false if start <= pd.Timestamp(r["alarm_utc"]) < end]
    episodes = sum(start <= t < end for t in episode_openings(false))
    days = market_days(feat, start, end)
    m = {"storms": len(rows), "alarmed": len(alarmed), "caught": sum(r["caught"] for r in rows),
         "caught_first_onset": sum(r["caught_first_onset"] for r in rows),
         "median_move_ahead_pct": _median([r["move_ahead_pct"] for r in alarmed]),
         "median_minutes_to_alarm": _median([r["minutes"] for r in alarmed]),
         "median_move_ahead_pct_first_onset": _median([r["move_ahead_pct_first_onset"] for r in alarmed]),
         "median_minutes_to_alarm_first_onset": _median([r["minutes_first_onset"] for r in alarmed]),
         "storm_alarms": sum(start <= t < end for items in alarms.values() for t, _ in items),
         "false_alarms": len(f), "false_alarm_episodes": episodes, "days": days,
         "false_alarms_per_day": len(f) / days if days else None,
         "false_alarm_episodes_per_day": episodes / days if days else None}
    _, squalls = v1_alarms_and_squalls(detections, start, end)
    m["squalls_per_day"] = squalls / days if days else None
    state_metrics(m, feat, detections, start, end)
    return m


def weekly_book(pair, feat, events, start, end):
    weekday_count = int((pd.date_range(start.normalize(), end, freq="D", inclusive="left").weekday < 5).sum())
    observed = int(((feat.index >= start) & (feat.index < end)).sum())
    coverage = observed / (weekday_count * 1440) if weekday_count else 0
    out = {"pair": pair, "from_utc": start.isoformat(), "to_utc": end.isoformat(),
           "status": "unavailable", "reason": None, "observed_minutes": observed,
           "weekday_coverage": coverage}
    if observed < 2 or coverage < 0.5:
        out["reason"] = "weekly coverage below registered minimum (2 bars and 50% weekday minutes)"
        return out
    idx, quotes = aligned_quotes({pair: feat}, (pair,), start, end)
    visible = [e for e in events if idx[0] <= e["time"] <= idx[-1]]
    since = cut_since(events, idx[0] + pd.Timedelta(nanoseconds=1))
    carry = since if since is not None and since < idx[0] else None
    if carry is not None:
        visible.insert(0, {"type": "alarm", "time": idx[0], "carry_in": True})
    actions = policy_actions({pair: visible}, lambda t: int(idx.searchsorted(t, side="left")))
    paths = ships(quotes, book_for(pair), actions)
    out.update(status="usable", carry_in_alarm_utc=None if carry is None else carry.isoformat(),
               partial_week=(start.weekday() != 0 or end.weekday() != 0),
               first_bar_utc=idx[0].isoformat(), last_bar_utc=idx[-1].isoformat())
    for name, path in paths.items():
        dd_usd, dd_pct = max_drawdown(path.equity)
        mc = path.margin_call_i
        out[name] = {"final_equity_usd": float(path.equity[-1]), "max_drawdown_usd": dd_usd,
                     "max_drawdown_pct": dd_pct, "margin_calls": int(mc is not None),
                     "margin_call_utc": None if mc is None else idx[mc].isoformat(),
                     "cuts": len(path.cuts), "restores": len(path.restores), "fills": len(path.fills),
                     "spread_cost_usd": path.spread_cost_usd,
                     "trades": [{"utc": idx[f["i"]].isoformat(), "signal_utc": idx[f["signal_i"]].isoformat(),
                                 "action": f["action"], "side": f["side"], "at": f["at"],
                                 "fill_price": f["price"], "mid_price": f["mid"], "cost_usd": f["cost_usd"]}
                                for f in path.fills]}
    difference = out["prepared"]["final_equity_usd"] - out["unprepared"]["final_equity_usd"]
    prep, unprep = (bool(out[n]["margin_calls"]) for n in ("prepared", "unprepared"))
    out.update(difference_usd=difference, helped=difference > 0, hurt=difference < 0,
               margin_outcome="both" if prep and unprep else "induced" if prep else "avoided" if unprep else "neither")
    return out


def policy_summary(weeks):
    used = [w for w in weeks if w["status"] == "usable"]
    diffs = [w["difference_usd"] for w in used]
    n = len(used)
    result = {"planned_pair_weeks": len(weeks), "usable_pair_weeks": n, "unavailable_pair_weeks": len(weeks) - n,
              "helped": sum(d > 0 for d in diffs), "hurt": sum(d < 0 for d in diffs), "ties": sum(d == 0 for d in diffs),
              "helped_share_pct": 100 * sum(d > 0 for d in diffs) / n if n else None,
              "median_difference_usd": _median(diffs), "total_difference_usd": sum(diffs),
              "margin_calls_avoided": sum(w["margin_outcome"] == "avoided" for w in used),
              "margin_calls_induced": sum(w["margin_outcome"] == "induced" for w in used),
              "both_margin_called": sum(w["margin_outcome"] == "both" for w in used),
              "neither_margin_called": sum(w["margin_outcome"] == "neither" for w in used)}
    for name in ("prepared", "unprepared"):
        result[name] = {key: sum(w[name][key] for w in used) for key in
                        ("spread_cost_usd", "margin_calls", "cuts", "restores", "fills")}
        result[name]["total_pnl_usd"] = sum(w[name]["final_equity_usd"] - 1_000_000 for w in used)
        result[name]["median_week_max_drawdown_usd"] = _median([w[name]["max_drawdown_usd"] for w in used])
        result[name]["max_week_drawdown_usd"] = max((w[name]["max_drawdown_usd"] for w in used), default=None)
        result[name]["median_week_max_drawdown_pct"] = _median([w[name]["max_drawdown_pct"] for w in used])
        result[name]["max_week_drawdown_pct"] = max((w[name]["max_drawdown_pct"] for w in used), default=None)
    return result


def evaluate_year(spec, manifest):
    selected = selected_prefix(spec, manifest)
    end = pd.Timestamp(manifest["selected_end"], tz="UTC") if selected else START
    feats = load_features(spec, manifest, selected)
    calendar = load_calendar()
    labels = label_all(feats, calendar)
    storms = labels[(labels["onset_utc"] >= START) & (labels["onset_utc"] < end)].copy()
    detections = {p: run_detector(f, calendar, spec["config"], exposure=leg_exposure(p)) for p, f in feats.items()}
    alarms, squalls = v1_alarms_and_squalls(detections, START, end)
    mids = {p: f["mid"] for p, f in feats.items()}
    def metrics_for(pairs):
        subset = {p: f for p, f in feats.items() if p in pairs}
        mine = storms[storms["pair"].isin(pairs)]
        aa, sq = v1_alarms_and_squalls({p: detections[p] for p in subset}, START, end)
        m = score(aa, mine, {p: mids[p] for p in subset}, market_days(subset, START, end), sq)
        details(mine, m)
        state_metrics(m, subset, {p: detections[p] for p in subset}, START, end)
        return m
    total, sgx = metrics_for(spec["pairs"]), metrics_for(spec["sgx_pairs"])
    false = false_rows(alarms, storms)
    weeks, pair_results = [], []
    for pair in spec["pairs"]:
        pm = metrics_for([pair])
        own_weeks = []
        monday = START.normalize() - pd.Timedelta(days=START.weekday())
        planned_end = pd.Timestamp("2026-01-01", tz="UTC")
        while monday < planned_end:
            a = max(START, monday)
            planned_week_end = min(planned_end, monday + pd.Timedelta(days=7))
            b = min(end, planned_week_end) if a < end else planned_week_end
            if a >= end:
                row = {"pair": pair, "from_utc": a.isoformat(), "to_utc": b.isoformat(),
                       "status": "not_completed_by_deadline", "reason": "outside selected chronological prefix"}
            elif pair in feats:
                row = weekly_book(pair, feats[pair], detections[pair].events, a, b)
            else:
                row = {"pair": pair, "from_utc": a.isoformat(), "to_utc": b.isoformat(),
                       "status": "unavailable", "reason": "pair lacks registered initial warm-up/data"}
            row["planned_to_utc"] = planned_week_end.isoformat()
            own_weeks.append(row)
            monday += pd.Timedelta(days=7)
        weeks.extend(own_weeks)
        months = []
        for w in manifest["months"]:
            rec = next(r for r in w["pairs"] if r["pair"] == pair)
            usable = w["id"] in selected and rec["status"] == "usable" and pair in feats
            row = {"month": w["id"], "acquisition_status": rec["status"],
                   "status": "usable" if usable else "unusable" if w["id"] in selected else "not_completed_by_deadline",
                   "reason": rec["reason"] if not usable else None, "quality": rec.get("quality"), "metrics": None}
            if w["id"] in selected and rec["status"] == "usable" and pair not in feats:
                row["reason"] = "pair has insufficient initial warm-up; no inferred history"
            if usable:
                a, b = (pd.Timestamp(w[k], tz="UTC") for k in ("start", "end_exclusive"))
                row["metrics"] = monthly_metrics(pm, [r for r in false if r["pair"] == pair],
                    {pair: alarms[pair]}, {pair: detections[pair]}, {pair: feats[pair]}, a, b)
            months.append(row)
        initial = manifest["months"][0]
        initial_record = next(r for r in initial["pairs"] if r["pair"] == pair)
        warmup = initial_record.get("warmup", {"status": "not_recorded", "reason": "see initial acquisition status"})
        pair_results.append({"pair": pair, "metrics": pm, "months": months, "warmup": warmup,
                             "policy": policy_summary(own_weeks)})
        print(pair, "storms:", pm["storms"], "weekly books:", len(own_weeks), flush=True)
    return {"status": "unassessed_no_usable_observations" if not feats else "full_year" if len(selected) == 12 else "chronological_prefix",
            "selected_months": selected, "selected_end": manifest["selected_end"],
            "planned_pair_months": len(spec["pairs"]) * 12,
            "usable_pair_months": sum(r["status"] == "usable" for p in pair_results for r in p["months"]),
            "metrics": total, "sgx_metrics": sgx, "pairs": pair_results, "weeks": weeks,
            "policy": policy_summary(weeks), "sgx_policy": policy_summary([w for w in weeks if w["pair"] in spec["sgx_pairs"]]),
            "largest_storms": sorted(total["per_storm"], key=lambda s: (-abs(s["move_bp"]), s["onset_utc"], s["pair"]))[:10],
            "misses": [s for s in total["per_storm"] if not s["caught"]], "false_alarms": false,
            "alarms": [{"pair": p, "alarm_utc": a.isoformat(), "clear_utc": None if c is None else c.isoformat()}
                       for p, items in alarms.items() for a, c in items]}


def recompute2():
    spec = check_frozen2()
    manifest = json.loads((DATA2 / "manifest.json").read_text())
    hashes = inventory(manifest)
    audit = transport_audit(manifest)
    exact = evaluate_year(spec, manifest)
    return {"schema_version": 2, "config": spec["config"], "exact": exact, "display": for_display(exact),
            "provenance": {"preregistration_sha256": sha256(REGISTRATION2), "preregistration_commit": registration2_commit(),
                           "base_commit": spec["base_commit"], "config_sha256": spec["config_sha256"],
                           "code_fingerprint": spec["code_fingerprint"], "runtime": runtime(),
                           "metrics_document_sha256": spec["metrics_document_sha256"],
                           "calendar_content_sha256": spec["calendar_content_sha256"],
                           "source_config_file_sha256": spec["source_config_file_sha256"], "downloader": spec["downloader"],
                           "amendment_sha256": {p.name: sha256(p) for p in sorted(DOCS.glob("amendment-2-*.md"))},
                           "data_file_sha256": hashes, "transport_audit": audit,
                           "oos_source_sha256": {str(p.relative_to(REPO_ROOT)): sha256(p)
                               for p in sorted(Path(__file__).parent.iterdir()) if p.suffix in (".py", ".cjs")}}}


def main():
    from .report2 import render2
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify-local", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.verify_local:
        saved = json.loads(RESULTS2.read_text())
        current = recompute2()
        if diff := first_difference({k: saved[k] for k in current}, current):
            raise SystemExit("Registration 2 verification failed: " + diff)
        if (DOCS / "results-2.md").read_text() != render2(saved):
            raise SystemExit("Registration 2 Markdown disagrees with JSON")
        print("Verified registration 2: all data, results, weekly policies, source hashes and frozen provenance match.")
        return
    marker = DOCS / "run-2-started.json"
    if marker.exists() or RESULTS2.exists():
        raise SystemExit("registration 2 primary run already started; refusing another evaluation")
    check_frozen2()
    manifest = json.loads((DATA2 / "manifest.json").read_text())
    selected_prefix(check_frozen2(), manifest)
    inventory(manifest)
    started = pd.Timestamp.now(tz="UTC").isoformat()
    marker.write_text(json.dumps({"started_utc": started, "preregistration_sha256": sha256(REGISTRATION2)}, indent=2) + "\n")
    result = recompute2()
    result["execution"] = {"started_utc": started, "finished_utc": pd.Timestamp.now(tz="UTC").isoformat(),
                           "wrapper_commit_at_run": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip(),
                           **runtime()}
    with RESULTS2.open("x") as out:
        out.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    (DOCS / "results-2.md").write_text(render2(result))
    print("Wrote results-2.json and results-2.md")


if __name__ == "__main__":
    main()
