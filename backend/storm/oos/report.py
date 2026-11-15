"""Deterministic Markdown from the checked JSON; contains no hand-entered results."""
from __future__ import annotations

import hashlib

from storm.evaluate import for_display
from .protocol import canonical

METRICS = (
    ("Storms", "storms"), ("Alarmed", "alarmed"), ("Caught (>=50% ahead)", "caught"),
    ("Caught against first onset", "caught_first_onset"),
    ("Median share ahead (%)", "median_move_ahead_pct"),
    ("Median minutes onset to alarm", "median_minutes_to_alarm"),
    ("Median share ahead, first onset (%)", "median_move_ahead_pct_first_onset"),
    ("Median minutes first onset to alarm", "median_minutes_to_alarm_first_onset"),
    ("All storm detections", "storm_alarms"), ("False pair alarms", "false_alarms"),
    ("False alert episodes", "false_alarm_episodes"), ("Observed days", "days"),
    ("False pair alarms / observed day", "false_alarms_per_day"),
    ("False episodes / observed day", "false_alarm_episodes_per_day"),
    ("Squalls / observed day", "squalls_per_day"),
    ("Storm-state minutes", "storm_state_minutes"),
    ("Observed pair-minutes", "observed_pair_minutes"),
    ("Storm-state share (%)", "storm_state_share_pct"),
)


def cell(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value).replace("|", "\\|").replace("\n", " ")


def table(headers, rows) -> list[str]:
    return ["| " + " | ".join(map(cell, headers)) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
            *("| " + " | ".join(map(cell, row)) + " |" for row in rows), ""]


def policy_table(policy: dict) -> list[str]:
    if policy["status"] != "supported":
        return [f"Policy: {policy['status']}. {policy.get('reason', '')}", ""]
    result = policy["result"]
    book = result["book"]
    lines = ["Synthetic USD book: " + "; ".join(book["legs"]) +
             f"; equity ${book['equity_usd']}; maintenance {book['maintenance_margin']}; cut {book['cut_fraction']}.", ""]
    if policy.get("excluded_pairs"):
        lines += ["USD policy unsupported for: " + ", ".join(policy["excluded_pairs"]) + ".", ""]
    keys = ("final_equity_usd", "max_drawdown_usd", "max_drawdown_pct", "margin_calls",
            "margin_call_utc", "cuts", "restores", "fills", "spread_cost_usd")
    lines += table(["Policy metric", "Prepared", "Unprepared"],
                   [[k, result["prepared"][k], result["unprepared"][k]] for k in keys])
    lines += table(["Book-aware alert", "Count"], result["alerts"].items())
    return lines


def render(result: dict) -> str:
    exact, display = result["exact"], result["display"]
    if display != for_display(exact):
        raise ValueError("stored display values disagree with exact results")
    digest = hashlib.sha256(canonical(result).encode()).hexdigest()
    prov = result["provenance"]
    lines = ["# Frozen external FX holdout results", "",
             "Generated from `results.json`; every displayed metric comes from code. "
             "A dash is undefined or unavailable, never a zero observation.", "",
             f"Registration commit: `{prov['preregistration_commit']}`. "
             f"Frozen effective-config SHA-256: `{prov['frozen_config_sha256']}`.", "",
             f"Canonical results JSON SHA-256: `{digest}`.", "",
             "## Totals", "",
             "Observed days union minutes across pairs within a window, then sum the disjoint windows. "
             "Medians pool unrounded storm records and exclude misses. Planned/usable counts are pair-windows.", ""]
    groups = [("Events", display["totals"]["events"]),
              ("Ordinary months", display["totals"]["ordinary"]),
              ("All windows", display["totals"]["all"])]
    lines += table(["Metric", *(n for n, _ in groups)],
                   [["Planned / usable pair-windows", *(f"{g['planned_pairs']} / {g['usable_pairs']}" for _, g in groups)],
                    *[[label, *(g["metrics"].get(key) for _, g in groups)] for label, key in METRICS]])
    lines += ["### Policy totals: independent reset books", "",
              "These are sums of independent book P&L and costs; drawdowns describe individual windows, "
              "rather than a continuous portfolio. Unsupported crosses have no invented USD result.", ""]
    keys = ("pnl_usd", "spread_cost_usd", "fills", "margin_calls", "cuts", "restores",
            "median_window_max_drawdown_usd", "max_window_drawdown_usd",
            "median_window_max_drawdown_pct", "max_window_drawdown_pct")
    lines += table(["Group", "Reset books", "Ship", *keys],
                   [[name, g["policy"]["independent_reset_books"], ship,
                     *(g["policy"][ship][key] for key in keys)]
                    for name, g in groups for ship in ("prepared", "unprepared")])
    lines += ["### Per-pair pooled totals", "",
              "Each pair uses its own observed-day denominator. A window with unusable data "
              "adds no fabricated observations.", ""]
    lines += table(["Pair", "Planned / usable windows", "Storms", "Alarmed", "Caught", "Caught first onset",
                    "Ahead %", "Minutes", "First ahead %", "First minutes", "Days", "False pairs/day", "False episodes/day"],
                   [[p, f"{g['planned_windows']} / {g['usable_windows']}",
                     *(g["metrics"][k] for k in ("storms", "alarmed", "caught", "caught_first_onset",
                       "median_move_ahead_pct", "median_minutes_to_alarm", "median_move_ahead_pct_first_onset",
                       "median_minutes_to_alarm_first_onset", "days", "false_alarms_per_day", "false_alarm_episodes_per_day"))]
                    for p, g in display["per_pair_totals"].items()])
    for window in display["windows"]:
        lines += [f"## {window['name']} ({window['id']})", "",
                  f"UTC evaluation: [{window['start']}, {window['end_exclusive']}); "
                  f"warm-up from {window['download_start']}. "
                  f"Usable pairs: {window['usable_pairs']} of {window['planned_pairs']}.", ""]
        lines += table(["Pair", "Status", "Reason", "Warm-up bars", "Scored bars", "Weekday coverage", "Unmatched bid / ask", "Largest gap min"],
                       [[r["pair"], r["status"], r["reason"], r.get("quality", {}).get("warmup_rows"),
                         r.get("quality", {}).get("evaluation_rows"), r.get("quality", {}).get("nominal_weekday_coverage"),
                         (f"{r['quality']['unmatched_bid']} / {r['quality']['unmatched_ask']}" if "quality" in r else None),
                         r.get("quality", {}).get("largest_gap_minutes")] for r in window["pairs"]])
        lines += table(["Detector metric", "Joint window", *(r["pair"] for r in window["pairs"])],
                       [[label, window["metrics"].get(key),
                         *((r["metrics"] or {}).get(key) for r in window["pairs"])] for label, key in METRICS])
        lines += ["### Every labelled storm", ""]
        lines += table(["Storm", "Onset UTC", "First onset UTC", "Trough UTC", "Move bp", "Alarm UTC",
                        "Alarmed", "Caught", "Ahead %", "Minutes", "Caught first", "First ahead %", "First minutes"],
                       [[r["storm_id"], r["onset_utc"], r["first_onset_utc"], r["trough_utc"], r["move_bp"],
                         r["alarm_utc"], r["alarm_utc"] is not None, r["caught"], r["move_ahead_pct"], r["minutes"],
                         r["caught_first_onset"], r["move_ahead_pct_first_onset"], r["minutes_first_onset"]]
                        for r in window["metrics"]["per_storm"]])
        lines += ["### Every false pair alarm", ""]
        lines += table(["Pair", "Alarm UTC", "All-clear UTC"],
                       [[r["pair"], r["alarm_utc"], r["clear_utc"]] for r in window["false_alarms"]])
        lines += ["### Joint-window policy", ""] + policy_table(window["policy"])
        lines += ["### Comparable single-pair policies", ""]
        for row in window["pairs"]:
            lines += [f"**{row['pair']}**", ""] + policy_table(row["policy"])
    total = display["totals"]["all"]
    m = total["metrics"]
    sentences = [
        f"The frozen detector alarmed on {m['alarmed']} of {m['storms']} labelled storms and caught {m['caught']} with at least half the peak-onset move still ahead.",
        f"Against the first onset, it caught {m['caught_first_onset']}; misses and late alarms remain in the tables.",
        f"The ordinary-month sample produced {display['totals']['ordinary']['metrics']['false_alarm_episodes']} false alert episodes over {display['totals']['ordinary']['metrics']['days']} observed days.",
        f"Data were usable for {total['usable_pairs']} of {total['planned_pairs']} planned pair-windows; non-USD crosses have no supported USD policy valuation in the frozen engine.",
        "This historical stress selection measures rapid detection on another feed and period, and does not demonstrate advance prediction of unscheduled prices.",
    ]
    lines += ["## What the test shows", "", " ".join(sentences), "",
              "All acquisition artifacts and per-fill policy records are hashed or recorded in `results.json`. "
              "Recompute locally with `cd backend && python -m storm.oos.run --verify`; this requires "
              "the original gitignored `data/external/` artifacts and performs no downloads.", ""]
    return "\n".join(lines)
