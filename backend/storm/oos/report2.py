"""Deterministic registration-2 report; no manually entered outcomes."""
import hashlib

from storm.evaluate import for_display
from .protocol import canonical
from .report import METRICS, table


def storm_table(rows):
    return table(["Pair", "Storm", "Onset UTC", "First onset UTC", "Move bp", "Alarm UTC", "Caught",
                  "Ahead %", "Minutes", "First ahead %", "First minutes"],
                 [[s["pair"], s["storm_id"], s["onset_utc"], s["first_onset_utc"], s["move_bp"],
                   s["alarm_utc"], s["caught"], s["move_ahead_pct"], s["minutes"],
                   s["move_ahead_pct_first_onset"], s["minutes_first_onset"]] for s in rows])


def policy_table(rows):
    keys = ("usable_pair_weeks", "unavailable_pair_weeks", "helped", "hurt", "ties", "helped_share_pct",
            "median_difference_usd", "total_difference_usd", "margin_calls_avoided", "margin_calls_induced",
            "both_margin_called", "neither_margin_called")
    lines = table(["Group", *keys], [[name, *(p[k] for k in keys)] for name, p in rows])
    lines += table(["Group", "Ship", "Spread USD", "Margin calls", "Cuts", "Restores", "Fills", "Total P&L USD",
                    "Median book DD USD", "Max book DD USD", "Median book DD %", "Max book DD %"],
                   [[name, ship, *(p[ship][k] for k in ("spread_cost_usd", "margin_calls", "cuts", "restores", "fills",
                     "total_pnl_usd", "median_week_max_drawdown_usd", "max_week_drawdown_usd",
                     "median_week_max_drawdown_pct", "max_week_drawdown_pct"))]
                    for name, p in rows for ship in ("prepared", "unprepared")])
    return lines


def render2(result):
    x, d = result["exact"], result["display"]
    if d != for_display(x):
        raise ValueError("registration 2 display disagrees with exact results")
    p = result["provenance"]
    lines = ["# Frozen FX out-of-sample results — registration 2", "",
             f"Status: **{d['status']}**. Completed chronological months: {', '.join(d['selected_months']) or 'none'}; "
             f"end exclusive: {d['selected_end']}. Usable pair-months: {d['usable_pair_months']} / {d['planned_pair_months']}.", "",
             f"Registration commit `{p['preregistration_commit']}`; base `{p['base_commit']}`; "
             f"config SHA-256 `{p['config_sha256']}`.", "",
             "Canonical results JSON SHA-256: `" + hashlib.sha256(canonical(result).encode()).hexdigest() + "`.", "",
             "A dash is unavailable, not zero. Monthly storms are assigned by peak onset; shares and minutes also "
             "refer to first onset where labelled. False-alarm classifications use all labels in the completed prefix.", "",
             "## Detector totals", ""]
    lines += table(["Metric", "All six pairs", "SGX pairs"],
                   [[label, d["metrics"].get(key), d["sgx_metrics"].get(key)] for label, key in METRICS])
    lines += ["## Independent Monday-reset policy books", "",
              "SYNTHETIC: each pair-week starts with $1M equity and a long-USD $20M leg; maintenance 2.5%, "
              "cut 75%, side-correct next-bar execution. Positive difference means prepared final equity exceeded "
              "unprepared final equity. These independent books do not constitute one continuous annual return. "
              "Active carry-in alarms are acted on after the first observed close, as registered. "
              "USD-base pairs are long the base; pairs ending USD are short the base. No true non-USD crosses were added.", ""]
    groups = [("All", d["policy"]), ("SGX", d["sgx_policy"])] + [(r["pair"], r["policy"]) for r in d["pairs"]]
    lines += policy_table(groups)
    for pair in d["pairs"]:
        lines += [f"## {pair['pair']} — every planned month", ""]
        keys = ("storms", "alarmed", "caught", "caught_first_onset", "median_move_ahead_pct", "median_minutes_to_alarm",
                "median_move_ahead_pct_first_onset", "median_minutes_to_alarm_first_onset", "days", "false_alarms",
                "false_alarm_episodes", "false_alarms_per_day", "false_alarm_episodes_per_day", "storm_state_share_pct")
        lines += table(["Month", "Status", "Reason", "Storms", "Alarmed", "Caught", "Caught first", "Ahead %", "Minutes",
                        "First ahead %", "First minutes", "Obs days", "False pairs", "False episodes", "False pairs/day",
                        "False episodes/day", "Storm state %"],
                       [[r["month"], r["status"], r["reason"], *((r["metrics"] or {}).get(k) for k in keys)] for r in pair["months"]])
        lines += ["Acquisition coverage and gap diagnostics (weekends and holidays are not filled):", ""]
        lines += table(["Month", "Observed minutes", "Warm-up", "Weekday coverage", "Missing-side bid / ask", "Gaps >1m", "Max gap min"],
                       [[r["month"], (r["quality"] or {}).get("evaluation_rows"), (r["quality"] or {}).get("warmup_rows"),
                         (r["quality"] or {}).get("weekday_coverage"),
                         None if not r["quality"] else f"{r['quality']['unmatched_bid']} / {r['quality']['unmatched_ask']}",
                         (r["quality"] or {}).get("gaps_over_one_minute"), (r["quality"] or {}).get("largest_gap_minutes")]
                        for r in pair["months"]])
    lines += ["## Ten largest labelled storms in the completed 2025 interval", "",
              "Ranked by absolute unrounded move_bp, then onset UTC and pair; no named-event substitutions.", ""]
    lines += storm_table(d["largest_storms"])
    lines += ["## Every primary miss", "", "Includes every caught=false storm: both absent alarms and alarms with less than half the peak-onset move ahead.", ""]
    lines += storm_table(d["misses"])
    lines += ["## Every independent pair-week", ""]
    lines += table(["Pair", "From UTC", "To UTC", "Status", "Reason", "Carry-in alarm UTC", "Difference USD", "Helped", "Margin outcome",
                    "Prepared spread USD", "Unprepared spread USD", "Prepared final equity", "Unprepared final equity"],
                   [[w["pair"], w["from_utc"], w["to_utc"], w["status"], w["reason"], w.get("carry_in_alarm_utc"),
                     w.get("difference_usd"), w.get("helped"), w.get("margin_outcome"),
                     w.get("prepared", {}).get("spread_cost_usd"), w.get("unprepared", {}).get("spread_cost_usd"),
                     w.get("prepared", {}).get("final_equity_usd"), w.get("unprepared", {}).get("final_equity_usd")]
                    for w in d["weeks"]])
    m, pol = d["metrics"], d["policy"]
    detection_sentence = (f"Across {d['usable_pair_months']} usable pair-months, the frozen detector alarmed on {m['alarmed']} of {m['storms']} storms and caught {m['caught']} with at least half the move ahead. "
                          if d["usable_pair_months"] else "No pair-month was usable, so detector performance is unassessed rather than a zero-storm success. ")
    policy_sentence = (f"Following the alarms helped in {pol['helped']} of {pol['usable_pair_weeks']} usable independent pair-weeks, with median weekly difference ${pol['median_difference_usd']} and total difference ${pol['total_difference_usd']}; spread costs and both-sided margin-call outcomes are included. "
                       if pol["usable_pair_weeks"] else "No paired week met the registered coverage threshold, so weekly policy performance is unassessed. ")
    lines += ["## Strengths and limits", "",
              detection_sentence +
              f"It produced {m['false_alarm_episodes']} false alert episodes over {m['days']} observed days, and every labelled miss remains listed; missing source intervals can conceal unlabelled storms. "
              + policy_sentence +
              "June 2025 for EURUSD, USDJPY and GBPUSD overlaps registration 1 and is not newly unseen evidence. "
              "This frozen historical evaluation measures detection and synthetic book outcomes, not prospective prediction of unscheduled prices.", "",
              "Full exact results, every labelled storm/false alarm, every weekly fill, and raw/parquet/source hashes are in `results-2.json`. "
              "Recompute both registrations with `cd backend && python -m storm.oos.run --verify`, using the recorded runtime and local acquisition directories.", ""]
    return "\n".join(lines)
