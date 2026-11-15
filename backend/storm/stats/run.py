"""Read-only, reproducible secondary evidence: python -m storm.stats.run."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import time

import numpy as np

from storm.evaluate import for_display
from .bootstrap import uncertainty, paired_caught_difference, summarize
from .datasets import load_all, detect, alarms_for, evaluate_unit
from .policy import inputs_for, real_actions, batch, oracle, check_batch, null_schedules, totals, native_library
from .protocol import DOCS, REPO_ROOT, check_frozen, rng_for, save, sha256, canonical
from .randomization import prepare_train, draw_offsets, caught_counts, null_summary, holm


def source_signature():
    folder = Path(__file__).parent
    return {p.name: sha256(p) for p in sorted(folder.iterdir()) if p.suffix in (".py", ".cpp")}


def policy_books(unit, detections, **options):
    books = []
    for window in unit.policy_windows:
        inp = inputs_for(unit, window, **{k: v for k, v in options.items() if k != "delay"})
        actions = real_actions(inp, detections, options.get("delay", 1))
        prepared, unprepared = batch(inp, [actions, []])
        books.append({"name": inp.name, "pairs": inp.pairs, "start": inp.start, "end": inp.end,
                      "prepared": prepared, "unprepared": unprepared})
    return books


def comparison_to_published(unit, calculated):
    if unit.dataset == "sgx_august":
        published = unit.metadata["published"]["methods"]["v1"]
        reconstructed = for_display(calculated)
        keys = ("storms", "alarmed", "caught", "caught_first_onset", "median_move_ahead_pct",
                "median_minutes_to_alarm", "median_move_ahead_pct_first_onset", "median_minutes_to_alarm_first_onset",
                "storm_alarms", "false_alarms", "false_alarm_episodes", "false_alarm_episodes_per_day", "days")
    elif unit.stock:
        published = unit.metadata["published"]["pooled"]["new_tickers"]
        reconstructed = dict(calculated)
        reconstructed["false_alarm_episodes_per_observed_day"] = calculated["false_alarm_episodes_per_day"]
        keys = ("storms", "alarmed", "caught", "caught_first_onset", "median_move_ahead_pct",
                "median_minutes_to_alarm", "false_alarms", "false_alarm_episodes", "false_alarm_episodes_per_observed_day")
    elif unit.dataset == "oos_round1":
        published = unit.metadata["published"]["metrics"]
        reconstructed = calculated
        keys = ("storms", "alarmed", "caught", "caught_first_onset", "median_move_ahead_pct", "median_minutes_to_alarm",
                "storm_alarms", "false_alarms", "false_alarm_episodes", "false_alarm_episodes_per_day", "days")
    else:
        exact = unit.metadata["published"].get("exact", unit.metadata["published"])
        published = exact.get("totals", {}).get("all", {}).get("metrics", exact.get("metrics", {}))
        if not published:
            raise ValueError("Explicit round-two metric schema review required")
        reconstructed = calculated
        keys = ("storms", "alarmed", "caught", "false_alarms", "false_alarm_episodes")
    differences = []
    for key in keys:
        a, b = reconstructed.get(key), published.get(key)
        if a is None or b is None:
            if a != b:
                differences.append({"field": key, "reconstructed": a, "published": b})
        elif not np.isclose(a, b, rtol=1e-10, atol=1e-9):
            differences.append({"field": key, "reconstructed": a, "published": b})
    if differences:
        raise ValueError(f"Published detection result not reproduced: {unit.name}: {differences}")
    return {"checked_fields": list(keys), "differences": differences, "passed": True}


def analyze_unit(unit, spec, do_null=True, do_sensitivity=True):
    started = time.monotonic()
    cfg = spec["config"]
    detection = detect(unit, cfg)
    methods = {method: evaluate_unit(unit, alarms_for(unit, detection, method)) for method in ("v1", "naive", "v0")}
    checked = comparison_to_published(unit, methods["v1"])
    print(f"{unit.name}: reproduced {methods['v1']['caught']}/{methods['v1']['storms']} caught", flush=True)
    trains, offsets = {}, {}
    null_data = {"dataset": unit.dataset, "unit": unit.name}
    paths, checks = [], []
    if do_null:
        for pair, result in detection.items():
            trains[pair] = prepare_train(unit, pair, result)
            offsets[pair] = draw_offsets(trains[pair], unit.name, unit.dataset, spec["detection_shuffles"])
        counts, per_storm = caught_counts(unit, trains, offsets, spec["detection_shuffles"])
        zero, _ = caught_counts(unit, trains, {p: np.asarray([0]) for p in trains}, 1)
        if int(zero[0]) != methods["v1"]["caught"]:
            raise ValueError("Vectorized detection null differs at original timing")
        # Representative shuffled scoring checks against the unmodified scorer.
        from .randomization import alarms_at
        for trial in (0, spec["detection_shuffles"] // 2, spec["detection_shuffles"] - 1):
            shuffled = {p: [(a, c) for a, c, _ in alarms_at(t, offsets[p][trial])] for p, t in trains.items()}
            if evaluate_unit(unit, shuffled)["caught"] != counts[trial]:
                raise ValueError("Shuffled detection differs from original scorer")
        null_policy = np.zeros(spec["policy_shuffles"])
        for window in unit.policy_windows:
            inp = inputs_for(unit, window)
            schedules = [real_actions(inp, detection), []] + null_schedules(inp, trains, offsets, spec["policy_shuffles"])
            results = batch(inp, schedules)
            checks.append(check_batch(inp, schedules, results))
            paths.append({"name": inp.name, "pairs": inp.pairs, "start": inp.start, "end": inp.end,
                          "prepared": results[0], "unprepared": results[1]})
            null_policy += np.asarray([r["final_equity_usd"] - results[1]["final_equity_usd"] for r in results[2:]])
        null_data.update(caught_counts=counts, policy_difference_usd=null_policy,
                         per_storm_caught=per_storm, offsets_minutes=offsets,
                         trains={p: {"alarms": t.alarms, "durations": t.durations, "censored": t.censored,
                                     "danger": t.danger, "danger_durations": t.danger_durations,
                                     "danger_censored": t.danger_censored, "horizon_minutes": t.horizon,
                                     "feasible_offset_count": len(t.feasible),
                                     "feasible_offsets_sha256": hashlib.sha256(t.feasible.astype("<i8").tobytes()).hexdigest()}
                                 for p, t in trains.items()})
    else:
        paths = policy_books(unit, detection)
    policy = totals(paths)
    sensitivity = []
    if do_sensitivity:
        for factor, values in spec["sensitivity"].items():
            for value in values:
                row = {"factor": factor, "value": value, "status": "evaluated"}
                if factor == "spread_multiplier" and unit.stock:
                    row.update(status="unavailable", reason="Yahoo trade bars have no measured bid/ask spread; 1x/2x/3x cannot be priced.")
                elif factor == "storm_on" and value < cfg["squall_on"]:
                    row.update(status="invalid", reason=f"Frozen ordering requires squall_on={cfg['squall_on']} <= storm_on; no other threshold changed.")
                else:
                    variant = detect(unit, {**cfg, "storm_on": value}) if factor == "storm_on" else detection
                    metric = evaluate_unit(unit, alarms_for(unit, variant)) if factor == "storm_on" else methods["v1"]
                    options = {"spread_multiplier": "spread", "fill_delay_bars": "delay",
                               "cut_fraction": "cut_fraction", "leverage": "leverage"}
                    books = policy_books(unit, variant, **({options[factor]: value} if factor in options else {}))
                    row.update(detection=summarize(metric["per_storm"], metric["daily"]), policy=totals(books), books=books)
                sensitivity.append(row)
    published_policy = None
    if unit.dataset == "sgx_august":
        published_policy = unit.metadata["published"]["policy"]
    elif unit.dataset == "oos_round1":
        published_policy = unit.metadata["published"]["policy"]
    return {"dataset": unit.dataset, "unit": unit.name, "stock": unit.stock,
            "group": unit.metadata["group"], "start": unit.start, "end": unit.end,
            "pairs": list(unit.feats), "published_detection_check": checked,
            "published_policy": published_policy,
            "descriptive_splits": unit.metadata.get("descriptive_splits"),
            "methods": methods, "policy": policy, "policy_books": paths,
            "sensitivity": sensitivity, "oracle_checks": checks,
            "elapsed_seconds": time.monotonic() - started}, null_data


def collect_units(results, names, method="v1"):
    picked = [r for r in results if r["dataset"] in names]
    rows = [row for r in picked for row in r["methods"][method]["per_storm"]]
    daily = [row for r in picked for row in r["methods"][method]["daily"]]
    trading = [row for r in picked for row in r["methods"][method]["trading_daily"]]
    return rows, daily, trading


def aggregate(results, nulls, spec):
    datasets = sorted({r["dataset"] for r in results})
    groups = {name: [name] for name in datasets}
    groups["pooled_fx"] = [name for name in datasets if name != "chips_new"]
    groups["pooled_all"] = datasets
    output = {}
    for group, names in groups.items():
        rows, daily, trading = collect_units(results, names)
        estimate = uncertainty(rows, daily, group, spec["bootstrap_replicates"], trading if group == "chips_new" else ())
        base = {}
        for method in ("naive", "v0"):
            br, bd, bt = collect_units(results, names, method)
            base[method] = {"point": summarize(br, bd, bt if group == "chips_new" else ()),
                            "v1_minus_baseline_caught_share": paired_caught_difference(rows, br, group + "/" + method, spec["bootstrap_replicates"])}
        picked = [r for r in results if r["dataset"] in names]
        policy = totals([book for r in picked for book in r["policy_books"]])
        row = {**estimate, "baselines": base, "policy": policy, "inferential": not group.startswith("pooled")}
        if nulls:
            selected = [n for n in nulls if n["dataset"] in names]
            counts = np.sum([n["caught_counts"] for n in selected], axis=0)
            pnl = np.sum([n["policy_difference_usd"] for n in selected], axis=0)
            degenerate = all(t["feasible_offset_count"] <= 1 for n in selected for t in n["trains"].values())
            row["chance"] = {"caught_storms": null_summary(row["point"]["caught"], counts, degenerate),
                             "policy_difference_usd": null_summary(policy["prepared_minus_unprepared_usd"], pnl, degenerate)}
            save(DOCS / "nulls" / (group + ".json"), {"caught_counts": counts, "policy_difference_usd": pnl})
        sensitivity = []
        for factor, values in spec["sensitivity"].items():
            for value in values:
                choices = [(r, next(s for s in r["sensitivity"] if s["factor"] == factor and s["value"] == value)) for r in picked]
                statuses = {s["status"] for _, s in choices}
                item = {"factor": factor, "value": value, "status": "evaluated" if statuses == {"evaluated"} else
                        "partial" if "evaluated" in statuses else next(iter(statuses)),
                        "unavailable_units": [{"unit": r["unit"], "status": s["status"], "reason": s.get("reason")} for r, s in choices if s["status"] != "evaluated"]}
                valid = [(r, s) for r, s in choices if s["status"] == "evaluated"]
                if valid:
                    # Detection does not change under trading-only perturbations.
                    caught = sum(s["detection"]["caught"] for _, s in valid)
                    storms = sum(s["detection"]["storms"] for _, s in valid)
                    alarmed = sum(s["detection"]["alarmed"] for _, s in valid)
                    days = sum(s["detection"]["observed_days"] for _, s in valid)
                    episodes = sum(s["detection"]["false_episodes"] for _, s in valid)
                    bp = totals([b for _, s in valid for b in s["books"]])
                    naive_caught = sum(r["methods"]["naive"]["caught"] for r, _ in valid)
                    headline_pnl = sum(r["policy"]["prepared_minus_unprepared_usd"] for r, _ in valid)
                    headline_delta = sum(r["methods"]["v1"]["caught"] - r["methods"]["naive"]["caught"] for r, _ in valid)
                    item.update(storms=storms, caught=caught, alarmed=alarmed, caught_share=caught/storms if storms else None,
                                alarmed_share=alarmed/storms if storms else None,
                                false_alert_episodes_per_observed_day=episodes/days if days else None, policy=bp,
                                policy_sign_survives=bool(np.sign(bp["prepared_minus_unprepared_usd"]) == np.sign(headline_pnl)),
                                caught_advantage_over_naive_survives=bool(np.sign(caught-naive_caught) == np.sign(headline_delta)),
                                sensitivity_chance_inference="not_tested; headline null is not reused as a new p-value")
                sensitivity.append(item)
        row["sensitivity"] = sensitivity
        output[group] = row
    if nulls:
        holm([test for name, group in output.items() if not name.startswith("pooled") for test in group["chance"].values()])
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-round2", action="store_true")
    parser.add_argument("--no-null", action="store_true", help="Development/smoke only; final reports require nulls")
    parser.add_argument("--resume", action="store_true", help="Reuse exact-input/source-matched unit artifacts")
    parser.add_argument("--only-unit", help="Compute one unit; no aggregate/report")
    args = parser.parse_args()
    spec = check_frozen()
    units, hashes = load_all(args.include_round2)
    signature = source_signature()
    cache_tag = hashlib.sha256(canonical({"sources": signature, "inputs": hashes, "registration": sha256(DOCS / "preregistration.md")}).encode()).hexdigest()
    results, nulls = [], []
    for unit in units:
        if args.only_unit and args.only_unit != unit.name:
            continue
        path = DOCS / "units" / (unit.name + ".json")
        null_path = DOCS / "nulls" / ("unit-" + unit.name + ".json")
        cached = json.loads(path.read_text()) if args.resume and path.exists() else None
        if cached and cached.get("cache_tag") == cache_tag and (args.no_null or null_path.exists()):
            result = cached["result"]
            null = json.loads(null_path.read_text()) if not args.no_null else None
            print("reused " + unit.name, flush=True)
        else:
            result, null = analyze_unit(unit, spec, not args.no_null)
            save(path, {"cache_tag": cache_tag, "result": result})
            if not args.no_null:
                save(null_path, null)
            print(f"completed {unit.name} in {result['elapsed_seconds']:.1f}s", flush=True)
        results.append(result)
        if not args.no_null:
            nulls.append(null)
    if args.only_unit:
        return
    groups = aggregate(results, nulls, spec)
    result = {"schema_version": 1, "analysis": "secondary retrospective; no tuning",
              "config": spec["config"], "groups": groups, "units": [str(p.relative_to(DOCS)) for p in sorted((DOCS / "units").glob("*.json"))],
              "provenance": {"registration_commit": spec["registration_commit"], "registration_sha256": sha256(DOCS / "preregistration.md"),
                             "base_commit": spec["base_commit"], "config_sha256": spec["config_sha256"],
                             "code_fingerprint": spec["code_fingerprint"], "stats_sources": signature,
                             "inputs": hashes, "seed": spec["seed"], "bootstrap_replicates": spec["bootstrap_replicates"],
                             "detection_shuffles": spec["detection_shuffles"], "policy_shuffles": spec["policy_shuffles"],
                             "runtime": {"python": platform.python_version(), **{name: importlib.metadata.version(name) for name in ("numpy", "pandas", "pyarrow")}},
                             "accelerator": "optional C++ (oracle-verified)" if native_library() else "original Python simulator",
                             "command": "python -m storm.stats.run" + (" --include-round2" if args.include_round2 else ""),
                             "amendments": {p.name: sha256(p) for p in sorted(DOCS.glob("amendment-*.md"))},
                             "finished_at_utc": datetime.now(timezone.utc).isoformat()},
              "round2_status": "included" if args.include_round2 else "pending; monitor until registered cutoff",
              "oracle_checks": [c for r in results for c in r["oracle_checks"]],
              "published_detection_checks": {r["unit"]: r["published_detection_check"] for r in results},
              "chips_descriptive_splits": next((r["descriptive_splits"] for r in results if r["stock"]), None)}
    save(DOCS / "results.json", result)
    from .report import render, write_charts
    (DOCS / "results.md").write_text(render(result))
    write_charts(result)
    print("wrote docs/stats/results.json, results.md, SVG charts and complete null arrays", flush=True)


if __name__ == "__main__":
    main()
