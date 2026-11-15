"""Assemble evidence and render every reported number from results.json."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import statistics

import pandas as pd

from .protocol import DATA, DOCS, canonical, check_frozen, save, sha256

SHOCK_START = pd.Timestamp("2026-11-09 04:00", tz="America/New_York").tz_convert("UTC")
SHOCK_END = pd.Timestamp("2026-11-14 00:00", tz="America/New_York").tz_convert("UTC")


def shock_week(result: dict, data: Path = DATA) -> dict:
    """Descriptive slice of archived outputs; never rerun the detector or select anew."""
    from storm.evaluate import false_alarm_episodes

    ticker_rows = {}
    for ticker, info in result["per_ticker"].items():
        if info["status"] != "evaluated":
            continue
        feat = pd.read_parquet(data / f"{ticker}_features.parquet")
        feat = feat[(feat.index >= SHOCK_START) & (feat.index < SHOCK_END)]
        mine = [s for s in result["storms"] if s["pair"] == ticker and
                SHOCK_START <= pd.Timestamp(s["onset_utc"]) < SHOCK_END]
        alarms = [a for a in result["detections"] if a["ticker"] == ticker and
                  SHOCK_START <= pd.Timestamp(a["alarm_utc"]) < SHOCK_END]
        false = [pd.Timestamp(a["alarm_utc"]) for a in alarms if a["false_alarm"]]
        days = int(feat.session.nunique())
        alarmed = [s for s in mine if s["alarm_utc"] is not None]
        med = lambda key: statistics.median(s[key] for s in alarmed if s[key] is not None) if any(s[key] is not None for s in alarmed) else None
        ticker_rows[ticker] = {"storms": len(mine), "alarmed": len(alarmed),
                               "caught": sum(s["caught"] for s in mine), "trading_days": days,
                               "storm_alarms": len(alarms), "false_alarms": len(false),
                               "false_alarm_episodes": false_alarm_episodes(false),
                               "false_alarms_per_trading_day": len(false) / days if days else None,
                               "median_move_ahead_pct": med("move_ahead_pct"),
                               "median_minutes_to_alarm": med("minutes")}
    pools = {}
    for name, tickers in {"new_tickers": [t for t in ticker_rows if t != "NVDA"],
                          "nvda_in_sample": ["NVDA"], "all_descriptive": list(ticker_rows)}.items():
        alarms = [pd.Timestamp(a["alarm_utc"]) for a in result["detections"] if a["ticker"] in tickers
                  and a["false_alarm"] and SHOCK_START <= pd.Timestamp(a["alarm_utc"]) < SHOCK_END]
        pool = {key: sum(ticker_rows[t][key] for t in tickers) for key in
                ("storms", "alarmed", "caught", "storm_alarms", "false_alarms")}
        dates = set()
        for ticker in tickers:
            f = pd.read_parquet(data / f"{ticker}_features.parquet")
            dates.update(f.loc[(f.index >= SHOCK_START) & (f.index < SHOCK_END), "session"].unique())
        pool.update(trading_days=len(dates), false_alarm_episodes=false_alarm_episodes(alarms),
                    false_alarms_per_trading_day=len(alarms) / len(dates) if dates else None)
        pools[name] = pool
    return {"start_utc": str(SHOCK_START), "end_utc_exclusive": str(SHOCK_END),
            "method": "Descriptive slice of the sole full-history run, with its original alarm/label context; no retuning or detector restart.",
            "per_ticker": ticker_rows, "pooled": pools}


def assemble() -> dict:
    spec = check_frozen()
    result = json.loads((DATA / "evaluation.json").read_text())
    for name, filename in (("tiger", "tiger.json"), ("replays", "replays.json"),
                           ("publication", "publication.json"), ("modal_runtime", "modal_runtime.json")):
        path = DOCS / filename
        result[name] = json.loads(path.read_text()) if path.exists() else {"status": "not_run"}
    result["ai"] = [json.loads((DOCS / f"ai_{crew}.json").read_text()) for crew in ("default", "private")
                    if (DOCS / f"ai_{crew}.json").exists()]
    for name in ("modal_gpu_usage", "modal_final_state"):
        path = DOCS / f"{name}.json"
        if path.exists():
            result[name] = json.loads(path.read_text())
    result["shock_week"] = shock_week(result)
    checks_path = DOCS / "verification.json"
    result["verification"] = json.loads(checks_path.read_text()) if checks_path.exists() else {}
    # Read-only task accounting: no manual ledger/cap modification.
    ledger = Path.home() / ".stormscore/ledger.sqlite"
    if ledger.exists():
        with sqlite3.connect(ledger.as_uri() + "?mode=ro", uri=True) as db:
            rows = db.execute("SELECT provider,status,count(*),sum(cost_usd) FROM ai_calls WHERE purpose LIKE ? GROUP BY provider,status",
                              ("cx-chips-20261115:%",)).fetchall()
        result["task_ledger"] = [{"provider": p, "status": s, "calls": n, "cost_usd": c} for p, s, n, c in rows]
    result["budgets_usd"] = spec["budgets_usd"]
    result["provenance"] = {"registration_sha256": sha256(DOCS / "preregistration.md"),
                            "acquisition_manifest_sha256": sha256(DATA / "acquisition.json"),
                            "evaluation_snapshot_sha256": sha256(DATA / "evaluation.json"),
                            "lane_source_sha256": {str(p.relative_to(DOCS.parents[1])): sha256(p)
                                                   for p in sorted((DOCS.parents[1] / "backend/storm/chips").glob("*.py"))}}
    result["limitations"] = [
        "The universe and shock week were selected with NVDA already observed; the thirteen new names are a cross-ticker test, not independent future-period validation.",
        "All served history is the primary registered window. The November 9–13 view is a descriptive slice of that one run. Warm-up has no history before the earliest acquired bar.",
        "Yahoo has trades rather than quotes. Thin extended-hours bars, missing minutes, bad prints, unadjusted prices and sector correlation affect interpretation; overnight price gaps cannot trigger this session-safe detector.",
        "Labels use close extrema, not intrabar lows. The separate November close-to-low facts use the existing equity convention. False alarms are defined against labels, not a judgement that an alert had no trading value.",
        "The replay book is synthetic, uses next observed open fills and assumes no spread, slippage or fees; replay selection includes an upward storm and missed/late alarms.",
        "Modal token accounting is zero because billing is for infrastructure. The reported runtime cost is an explicitly conservative wall-time estimate, not an invoice; startup/stop are included.",
    ]
    result["assembled_at_utc"] = datetime.now(timezone.utc).isoformat()
    result["status"] = "complete" if (len(result["ai"]) == 2 and all(a["errors"] == 0 for a in result["ai"])
                                                    and result["tiger"].get("status") == "complete"
                                                    and result["modal_runtime"].get("stop_exit_code") == 0) else "partial"
    save(DOCS / "results.json", result)
    (DOCS / "results.md").write_text(render(result))
    return result


def fmt(value, places: int = 2) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.{places}f}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def table(headers: list[str], rows: list[list]) -> str:
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |",
                      *["| " + " | ".join(fmt(v) for v in row) + " |" for row in rows]]) + "\n"


def render(result: dict) -> str:
    """Pure rendering: the entire Markdown document is tested against this function."""
    r = result
    new = r["pooled"]["new_tickers"]
    sections = ["# Chip-sector frozen detector results\n",
                f"Status: **{r['status']}**. Base `{r['base_commit']}`; preregistration `{r['preregistration_commit']}`.\n",
                f"The frozen detector caught {new['caught']} of {new['storms']} storms across the thirteen new tickers, with {new['false_alarms']} false pair alerts over {new['trading_days']} observed trading dates ({new['false_alarms_per_trading_day']:.2f} per trading day). "
                "NVDA is reported separately because it was used to build the equity path. "
                "Yahoo served more history than the approximate seven-day expectation, so the registered full-retention probe includes October and the three largest new moves occur there. "
                "The results include misses and zero-storm tickers, and do not establish advance price prediction.\n",
                "## Full served window: per ticker\n",
                "Rates use distinct ET trading dates with bars; pooled dates are a union, not ticker-days. Medians include alarmed storms only and use unrounded classifications.\n"]
    headers = ["Ticker", "Role", "Bars", "Days", "Storms", "Alarmed", "Caught", "False alerts", "False/day", "Ahead median %", "Alarm median min"]
    sections.append(table(headers, [[t, "in-sample" if row["in_sample"] else "new", row["raw_rows"], row.get("trading_days"),
                                     row["storms"], row.get("alarmed"), row.get("caught"), row.get("false_alarms"),
                                     row.get("false_alarms_per_trading_day"), row.get("median_move_ahead_pct"), row.get("median_minutes_to_alarm")]
                                    for t, row in r["per_ticker"].items()]))
    sections.append("## Pooled metrics\n")
    sections.append(table(["Pool", "Storms", "Alarmed", "Caught", "First-onset caught", "Detections", "False", "Days", "False/day", "False episodes/day", "Ahead median %", "Alarm median min", "Storm-state %"],
                          [[name, *[p[k] for k in ("storms", "alarmed", "caught", "caught_first_onset", "storm_alarms", "false_alarms", "trading_days", "false_alarms_per_trading_day", "false_alarm_episodes_per_trading_day", "median_move_ahead_pct", "median_minutes_to_alarm", "storm_state_share_pct")]]
                           for name, p in r["pooled"].items()]))
    sections.append(table(["Pool", "Observed days (union minutes / 1,440)", "False/observed day", "Episodes/observed day", "First-onset ahead median %", "First-onset alarm median min"],
                          [[name, *[p[k] for k in ("observed_days", "false_alarms_per_observed_day", "false_alarm_episodes_per_observed_day", "median_move_ahead_pct_first_onset", "median_minutes_to_alarm_first_onset")]] for name, p in r["pooled"].items()]))
    week = r["shock_week"]
    sections.extend(["## Requested Nvidia shock week, November 9–13\n", week["method"] + "\n"])
    sections.append(table(["Ticker/pool", "Storms", "Alarmed", "Caught", "Detections", "False", "Days", "False/day"],
                          [[name, *[p[k] for k in ("storms", "alarmed", "caught", "storm_alarms", "false_alarms", "trading_days", "false_alarms_per_trading_day")]]
                           for name, p in {**week["per_ticker"], **week["pooled"]}.items()]))
    sections.extend(["## Every labelled storm, including misses\n",
                     "Matching: alarm in [onset − 60 min, trough], active at onset. Caught: at least 50% remains. All times UTC; label prices are closes. First onset is the earliest triggering window in the merged episode.\n"])
    sections.append(table(["Storm", "Onset UTC", "First onset UTC", "Trough UTC", "Move bp", "Alarm UTC", "Minutes", "Ahead %", "First-onset minutes", "First-onset ahead %", "Caught"],
                          [[s["storm_id"], s["onset_utc"], s["first_onset_utc"], s["trough_utc"], s["move_bp"], s["alarm_utc"], s["minutes"], s["move_ahead_pct"], s["minutes_first_onset"], s["move_ahead_pct_first_onset"], s["caught"]] for s in r["storms"]]))
    sections.append("## Every direction-agnostic detection\n")
    sections.append(table(["Ticker", "Alarm UTC", "All-clear UTC", "False against labels"],
                          [[a["ticker"], a["alarm_utc"], a["clear_utc"], a["false_alarm"]] for a in r["detections"]]))
    sections.extend(["## Three new replays\n", "Ranked by absolute unrounded labelled move, including upward moves and misses. Default-crew reports are stored in the local bundles.\n"])
    sections.append(table(["Replay", "Move bp", "Caught", "Ahead %", "Frames", "Stress scenarios", "Prepared final $", "Unprepared final $", "Prepared margin UTC", "Unprepared margin UTC"],
                          [[s["storm_id"], s["move_bp"], s["caught"], s["move_ahead_pct"], s["n"], s["stress_scenarios"],
                            s["ships"]["prepared"]["final"], s["ships"]["unprepared"]["final"],
                            s["ships"]["prepared"]["margin_call"], s["ships"]["unprepared"]["margin_call"]] for s in r["replays"]]))
    pub = r["publication"]
    sections.append(f"Existing index entries preserved: {pub.get('existing_entries_preserved')}; new entries: {pub.get('new_entries')}; order preserved: {fmt(pub.get('existing_order_preserved'))}; original metrics preserved: {fmt(pub.get('metrics_preserved'))}.\n")
    sections.append("## Real AI crew comparison, identical bundle facts\n")
    sections.append(table(["Crew", "Writer", "Inspector", "Completed", "Numeric first try", "Accepted first try", "Fallbacks", "Flags", "Errors", "Mean total s", "Mean writer s", "Total token $"],
                          [[a["crew"], a["writer_model"], ", ".join(a["inspector_models"]), a["reports"], a["first_try_numbers_verified"], a["accepted_first_try"], a["fallbacks"], a["inspector_flags"], a["errors"], a["mean_latency_s"], a["mean_writer_latency_s"], f"{a['token_cost_usd']:.7f}"] for a in r["ai"]]))
    for a in r["ai"]:
        sections.append(table([a["crew"] + " replay", "Outcome", "Latency s", "Token $", "Fact SHA-256"],
                              [[d["storm_id"], d.get("report", {}).get("outcome", d["status"]), d["latency_s"],
                                f"{d['report']['cost_usd']:.7f}" if "report" in d else None, d["facts_sha256"]] for d in a["details"]]))
    modal = r["modal_runtime"]
    sections.append(f"Modal cold wake/model discovery: {fmt(modal.get('wake_discovery_s'))} s; local wall time including deploy, startup and stop command: {fmt(modal.get('wall_time_s_including_deploy_wake_stop'))} s; billing window through server-confirmed termination: {fmt(modal.get('conservative_billing_window_s'))} s; conservative runtime cost estimate: ${fmt(modal.get('runtime_cost_upper_estimate_usd'), 4)} at ${fmt(modal.get('conservative_usd_per_wall_second'), 3)}/s; stop exit code: {modal.get('stop_exit_code')}; observed final state: {modal.get('observed_final_state')}; running tasks: {modal.get('observed_running_tasks')}. Token cost is separate from GPU runtime, and this estimate is not an invoice.\n")
    if "modal_gpu_usage" in r:
        usage = r["modal_gpu_usage"]
        sections.append(table(["Modal allocation metric", "Observed GPU minutes", "Missing buckets"],
                              [[key, value, usage["missing_buckets"][key]]
                               for key, value in usage.get("allocated_gpu_minutes_observed", {}).items()
                               if usage["missing_buckets"][key] == 0]))
        sections.append(f"Allocation window: {usage.get('since_utc')} through {usage.get('until_utc')}; bucket size {usage.get('bucket_seconds')} seconds. {usage.get('note')}\n")
    sections.append("## Tiger Data\n")
    tiger = r["tiger"]
    sections.append(table(["Statistic", "Value"], [["Status", tiger.get("status")], ["Hypertable", tiger.get("hypertable")],
                           ["Verified snapshot rows", tiger.get("verified_snapshot_rows")], ["5-minute aggregate rows", tiger.get("aggregate_rows")],
                           ["Chunks compressed", tiger.get("compressed_chunks")], ["Bytes before compression", tiger.get("bytes_before_compression")],
                           ["Bytes after compression", tiger.get("bytes_after_compression")], ["Compression ratio", tiger.get("compression_ratio")],
                           ["Sample query ms including network", tiger.get("sample_query_ms")], ["Sample query result rows", tiger.get("sample_query_rows")]]))
    sections.append("```sql\n" + tiger.get("sample_query", "") + "\n```\n")
    sections.append("Query parameters: `" + json.dumps(tiger.get("sample_query_params"), sort_keys=True) + "`.\n")
    sections.append("## Retention, warm-up and provenance\n")
    sections.append(table(["Ticker", "First UTC", "Last UTC", "In-hours rows", "Bad prints", "SD-defined rows", "Risk-defined rows", "Raw SHA-256"],
                          [[t, p.get("first_utc"), p.get("last_utc"), p.get("in_hours_rows"), p.get("bad_print_count"), p.get("sd_defined_minutes"), p.get("risk_defined_minutes"), r["acquisition"]["tickers"][t].get("sha256")] for t, p in r["per_ticker"].items()]))
    failures = [[t, a["start_et"], a["end_et_exclusive"], a["status"], a.get("error_type"), a.get("error")]
                for t, info in r["acquisition"]["tickers"].items() for a in info["requests"] if a["status"] != "ok"]
    sections.append(table(["Ticker", "Requested start ET", "End ET exclusive", "Status", "Type", "Details"], failures))
    sections.append("Packages: `" + json.dumps(r["acquisition"]["versions"], sort_keys=True) + "`. Config: `" + canonical(r["config"]).strip() + "`.\n")
    sections.append("Config/source fingerprints, all request outcomes, exact unrounded rows, fact fingerprints and local bundle hashes are in results.json; preregistration and run_started.json establish ordering. No bars, bundles, secrets or ledger are committed.\n")
    sections.append("## November 11 regular close to November 12 low, separate descriptive facts\n")
    sections.append(table(["Ticker", "Close UTC", "Close", "Low UTC", "Low", "Move bp"],
                          [[t, m["close_utc"], m["close"], m["low_utc"], m["low"], m["move_bp"]] for t, m in r["november_11_close_to_12_low"].items() if m]))
    sections.append("## Checks and limits\n")
    sections.append("Verification: `" + json.dumps(r["verification"], sort_keys=True) + "`.\n")
    sections.append("\n".join("- " + note for note in r["limitations"]) + "\n")
    return "\n".join(sections)


if __name__ == "__main__":
    result = assemble()
    print(f"Rendered results.md from results.json; status={result['status']}")
