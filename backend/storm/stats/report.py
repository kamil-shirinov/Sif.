"""Deterministic Markdown and standalone SVGs from the numerical artifact."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

import numpy as np

from .protocol import DOCS

LABELS = {"sgx_august": "SGX August", "oos_round1": "FX historical round 1", "oos_round2": "FX chronological round 2",
          "chips_new": "Chips: 13 new tickers", "pooled_fx": "Pooled FX (descriptive)", "pooled_all": "Pooled all (descriptive)"}


def save_svg(fig, path):
    fig.savefig(path, metadata={"Date": None})
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")


def number(value, digits=2):
    return "undefined" if value is None else f"{value:,.{digits}f}"


def percent(value):
    return "undefined" if value is None else number(value*100, 1) + "%"


def ci(row, is_share=False, digits=2):
    fmt = percent if is_share else lambda x: number(x, digits)
    return f"{fmt(row['estimate'])} [{fmt(row['ci95'][0])}, {fmt(row['ci95'][1])}]"


def judge_sentences(result):
    groups = result["groups"]
    sgx, oos, chips, pooled = (groups[k] for k in ("sgx_august", "oos_round1", "chips_new", "pooled_all"))
    policy_tests = [g['chance']['policy_difference_usd'] for n,g in groups.items() if not n.startswith('pooled') and 'chance' in g]
    surviving = sum(t.get('holm_p_value',1) <= .05 for t in policy_tests)
    sgx_delay = next(r for r in sgx['sensitivity'] if r['factor']=='fill_delay_bars' and r['value']==5)
    sentences = [
        f"On SGX's August test month the frozen detector caught {sgx['point']['caught']} of {sgx['point']['storms']} storms, with a storm-bootstrap 95% interval of {percent(sgx['intervals']['caught_share']['ci95'][0])} to {percent(sgx['intervals']['caught_share']['ci95'][1])}; that is a small sample.",
        f"On the selected historical FX windows it caught {oos['point']['caught']} of {oos['point']['storms']}, with timing-randomization p={number(oos.get('chance',{}).get('caught_storms',{}).get('p_value'),4)}, but these events were chosen for stress rather than sampled prospectively.",
        f"On the thirteen new chip tickers it caught {chips['point']['caught']} of {chips['point']['storms']}; their shared dates, sector and already seen shock week weaken independence.",
        f"The descriptive pooled catch rate is {percent(pooled['point']['caught_share'])}, with a joint-date-block 95% interval of {percent(pooled['intervals']['date_block']['caught_share']['ci95'][0])} to {percent(pooled['intervals']['date_block']['caught_share']['ci95'][1])}; pooling does not create a new holdout.",
        f"False-alert burden was {number(sgx['point']['false_alert_episodes_per_observed_day'])} episodes per observed day on SGX and {number(chips['point']['false_alert_episodes_per_trading_day'])} per trading day on chips ({number(chips['point']['false_alert_episodes_per_observed_day'])} per observed day).",
        f"The synthetic prepared books' pooled FX result was USD {number(groups['pooled_fx']['policy']['prepared_minus_unprepared_usd'],0)} relative to holding, but {surviving} of {len(policy_tests)} individual dataset policy tests survived multiplicity correction.",
        f"At five-bar fills, SGX's simulated policy advantage changes from USD {number(sgx['policy']['prepared_minus_unprepared_usd'],0)} to USD {number(sgx_delay['policy']['prepared_minus_unprepared_usd'],0)}, so the benefit is sensitive to execution delay.",
        f"Round-two status is {result['round2_status']}; this retrospective evidence supports assessment of detection and risk response, and does not demonstrate price prediction or causal trading profit."
    ]
    return sentences


def render(result):
    lines = ["# Frozen statistical evidence", "", *judge_sentences(result), "",
             "## Frozen headline and uncertainty", "",
             "Secondary retrospective analysis. The headline configuration is fixed throughout. Brackets are percentile 95% intervals from 10,000 resamples; conditional medians use alarmed storms only. Shares use all storms, including misses. Negative minutes mean an alarm before the strongest-window onset.", "",
             "| Dataset | Storms | Alarmed share [95%] | Caught share [95%] | Median share ahead, % [95%] | Median minutes to alarm [95%] | False episodes / observed day [95%] |",
             "|---|---:|---|---|---|---|---|"]
    for name, group in result["groups"].items():
        u = group["intervals"]
        lines.append(f"| {LABELS[name]} | {group['point']['storms']} | {ci(u['alarmed_share'],True)} | {ci(u['caught_share'],True)} | {ci(u['median_share_ahead_pct'])} | {ci(u['median_minutes_to_alarm'])} | {ci(u['false_alert_episodes_per_observed_day'])} |")
    lines += ["", "Storm resampling assumes independent storms; the date-block intervals below jointly resample storms across pairs on the same event date. They remain weak with few independent event dates. An all-success sample produces a degenerate empirical bootstrap interval (SGX alarmed share is 100% to 100%); that cannot establish perfect population sensitivity or account for misses absent from the sample. Dataset strata and their actual storm counts are retained in pooled resamples. False-alert intervals resample whole days jointly across pairs, including zero-alarm and partial days; unrelated historical windows are separate timelines.", "",
              "| Dataset | Event-date blocks | Alarmed share, date-block [95%] | Caught share, date-block [95%] | Caught share, first onset [95%] | First-onset median minutes [95%] | Undefined conditional-median replicates |",
              "|---|---:|---|---|---|---|---:|"]
    for name, group in result["groups"].items():
        u = group["intervals"]
        lines.append(f"| {LABELS[name]} | {u['date_block']['blocks']} | {ci(u['date_block']['alarmed_share'],True)} | {ci(u['date_block']['caught_share'],True)} | {ci(u['caught_share_first_onset'],True)} | {ci(u['median_minutes_to_alarm_first_onset'])} | {u['median_share_ahead_pct']['undefined_replicates']} |")
    chips = result["groups"]["chips_new"]
    lines += ["", f"Chips additionally retains the original ET trading-day denominator: {ci(chips['intervals']['false_alert_episodes_per_trading_day'])} false episodes per trading day, over {chips['point']['trading_days']} dates. Observed days mean 1,440 union observed minutes; the two rates are not interchangeable. NVDA is excluded from every headline and pooled row. Its original in-sample and all-ticker descriptive splits remain in results.json.", "",
              "![Catch-rate intervals](caught-intervals.svg)", "", "## Against chance", "",
              "The null uniformly translates each complete pair/window alarm train over feasible integer-minute offsets, preserving alarm count, clock duration and within-pair timing. It rejects boundary-crossing episodes, undefined/off-market alarm starts and unobserved closed endpoints. Detection and danger trains share offsets; pairs move independently. Open episodes retain administrative observed duration and schedule no invented restore. Feasible offset counts and their hashes, sampled offsets, full null arrays, per-storm hit arrays and oracle checks are retained under nulls/ and units/.", "",
              "One-sided Monte Carlo p=(1+null values at least observed)/(B+1). Detection uses 10,000 draws; policy uses the same first 1,000 draws and full execution/margin paths. Holm adjustment covers both primary tests across the available individual datasets; pooled tests are descriptive and excluded from this family. This is a conditional timing null, not a causal randomization, a uniform distribution over all possible alarm schedules, or a deployable random-trader benchmark. Independent pair shifts remove cross-pair timing dependence. Duration conditioning and sparse feasible offsets can limit power.", "",
              "| Dataset | Statistic | Observed | Null median [2.5%, 97.5%] | B | Exceedances | Raw p | Holm p | Monte Carlo SE | Degenerate |",
              "|---|---|---:|---|---:|---:|---:|---:|---:|---|"]
    for name, group in result["groups"].items():
        for statistic, test in group.get("chance", {}).items():
            label = "Caught storms" if statistic == "caught_storms" else "Prepared − unprepared, USD"
            lines.append(f"| {LABELS[name]} | {label} | {number(test['statistic'],0)} | {number(test['null_median'],0)} [{number(test['null_ci95'][0],0)}, {number(test['null_ci95'][1],0)}] | {test['replicates']} | {test['exceedances']} | {number(test['p_value'],4)} | {number(test.get('holm_p_value'),4)} | {number(test['monte_carlo_se'],4)} | {test['fully_degenerate']} |")
    lines += ["", "![Timing null distributions](timing-nulls.svg)", "", "## Naive and v0 on identical features", "",
              "These are detection baselines, not retrofitted trading policies. Paired intervals resample the same storm indices for v1 and each baseline. Naive waits for the label-sized 15-minute price move; v0 uses its unchanged hand-set settings. Baselines retain their existing gap/session behavior, so chip comparisons inherit that implementation's limitations.", "",
              "| Dataset | Baseline | Alarmed / storms | Caught / storms | False episodes / observed day | v1 − baseline caught share [95%] |",
              "|---|---|---:|---:|---:|---|"]
    for name, group in result["groups"].items():
        for method, baseline in group["baselines"].items():
            p = baseline["point"]
            lines.append(f"| {LABELS[name]} | {method} | {p['alarmed']} / {p['storms']} | {p['caught']} / {p['storms']} | {number(p['false_alert_episodes_per_observed_day'])} | {ci(baseline['v1_minus_baseline_caught_share'],True)} |")
    lines += ["", "## Synthetic policy outcomes", "",
              "Current-main policy is frozen at the registered base, without tuning. FX books start with USD 1m equity, 20x total gross exposure, 2.5% maintenance; chip secondary books are independent long-stock books per new ticker, 4x exposure and 15% maintenance. All cut 75% on book-danger alarms and restore at all-clear, filling next observed open. USD crosses without a registered conversion leg are excluded from policy only. Round two retains its usable independent weekly reset books and carry-in convention. Policy sums across reset books are scenario totals, not the return of one investable portfolio. Maximum book drawdown is the worst individual reset book, not an aggregate portfolio drawdown.", "",
              "| Dataset | Reset books | Prepared − unprepared, USD | Prepared P&L, USD | Holding P&L, USD | Prepared / holding margin calls | Prepared / holding spread cost, USD | Worst prepared / holding book drawdown, USD |",
              "|---|---:|---:|---:|---:|---|---|---|"]
    for name, group in result["groups"].items():
        p = group["policy"]
        a, b = p["prepared"], p["unprepared"]
        lines.append(f"| {LABELS[name]} | {p['independent_reset_books']} | {number(p['prepared_minus_unprepared_usd'],0)} | {number(a['pnl_usd'],0)} | {number(b['pnl_usd'],0)} | {a['margin_calls']} / {b['margin_calls']} | {number(a['spread_cost_usd'],0)} / {number(b['spread_cost_usd'],0)} | {number(a['max_book_drawdown_usd'],0)} / {number(b['max_book_drawdown_usd'],0)} |")
    lines += ["", "Round 1's published policy used an older valuation implementation. Original per-window policy results are preserved beside current-main recomputation in units/; they are not silently revised. Chip full-period policies here are new secondary analyses, rather than the original selected replay outcomes. Yahoo bars contain trades, not measured quotes: zero simulated spread is not evidence of free execution, and spread sensitivities are unavailable for chips.", "", "## Sensitivity beside the frozen headline", "",
              "Every row changes one factor only. There is no search, selection or replacement of the headline. Invalid storm_on=0.70 remains invalid because frozen squall_on=0.75 would exceed it. Fill delays count observed traded bars after the signal and apply to cuts and restores. Leverage 10x/20x/30x is an additional stress for chip books whose headline is 4x; unchanged 15% maintenance can force immediate liquidation. No sensitivity p-values were run and headline null distributions are not reused to infer significance for a changed policy."]
    for name, group in result["groups"].items():
        p = group["point"]
        lines += ["", f"### {LABELS[name]}", "",
                  "| Setting | Status | Caught / storms | Alarmed share | False episodes / observed day | Prepared − unprepared, USD | Prepared / holding margin calls | Policy-sign conclusion survives | Catch-advantage sign vs naive survives |",
                  "|---|---|---:|---:|---:|---:|---|---|---|",
                  f"| **Frozen headline** | fixed | {p['caught']} / {p['storms']} | {percent(p['alarmed_share'])} | {number(p['false_alert_episodes_per_observed_day'])} | {number(group['policy']['prepared_minus_unprepared_usd'],0)} | {group['policy']['prepared']['margin_calls']} / {group['policy']['unprepared']['margin_calls']} | reference | reference |"]
        for row in group["sensitivity"]:
            setting = f"{row['factor']}={row['value']}"
            if "policy" not in row:
                reason = "; ".join(sorted({u['reason'] for u in row['unavailable_units']}))
                lines.append(f"| {setting} | {row['status']}: {reason} | — | — | — | — | — | — | — |")
                continue
            policy = row["policy"]
            status = row["status"] + (" (FX subset only)" if row["status"] == "partial" else "")
            lines.append(f"| {setting} | {status} | {row['caught']} / {row['storms']} | {percent(row['alarmed_share'])} | {number(row['false_alert_episodes_per_observed_day'])} | {number(policy['prepared_minus_unprepared_usd'],0)} | {policy['prepared']['margin_calls']} / {policy['unprepared']['margin_calls']} | {row['policy_sign_survives']} | {row['caught_advantage_over_naive_survives']} |")
    lines += ["", "## Provenance and reproduction", "",
              f"Registration commit: `{result['provenance']['registration_commit']}`. Frozen main base: `{result['provenance']['base_commit']}`. Canonical config SHA-256: `{result['provenance']['config_sha256']}`. No production module, dependency manifest, configuration, calendar or data file was changed.", "",
              f"Seed: `{result['provenance']['seed']}`. Independent random streams are SHA-256-keyed by dataset/unit/pair/task, so adding round two does not change earlier draws. Runtime: `{json.dumps(result['provenance']['runtime'],sort_keys=True)}`. Accelerator: {result['provenance']['accelerator']}; representative real and shuffled paths are checked against the original simulator with USD absolute tolerance 0.00001 and relative tolerance 1e-9. Timing ties use >=; no null or undefined metric is converted to zero.", "",
              "```sh", "cd backend", result["provenance"]["command"], "python -m pytest -q", "```", "",
              "results.json contains runtime/core/config/source/document/data hashes and all estimates. units/ contains per-storm rows, zero/partial-day exposure blocks, original policy results, all policy books and sensitivity outcomes. nulls/ contains complete 10,000-draw detection and 1,000-draw policy arrays plus every sampled offset. Source data remain uncommitted at their original read-only locations. The Markdown is rendered deterministically from JSON and checked byte-for-byte by a test. The preregistration and dated amendments record the exact estimands, censoring, denominators and limitations.", ""]
    return "\n".join(lines)


def write_charts(result):
    # Matplotlib is used only for export, not calculation. It is already installed in
    # the retained experiment environment; no repository dependency is changed.
    cache = Path(tempfile.gettempdir()) / 'stormscore-stats-plot-cache'
    cache.mkdir(exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(cache))
    os.environ.setdefault('XDG_CACHE_HOME', str(cache))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    matplotlib.rcParams.update({"svg.hashsalt": "stormscore-stats", "font.size": 9})
    names = list(result["groups"])
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for y, name in enumerate(names):
        g = result["groups"][name]
        point = g["point"]["caught_share"]
        lo, hi = g["intervals"]["caught_share"]["ci95"]
        blo, bhi = g["intervals"]["date_block"]["caught_share"]["ci95"]
        if point is None:
            continue
        ax.plot([lo*100, hi*100], [y-.08,y-.08], color="#0a6c9c", lw=3)
        ax.plot([blo*100, bhi*100], [y+.08,y+.08], color="#db791a", lw=3)
        ax.plot(point*100, y, "o", color="#102b3f")
    ax.set_yticks(range(len(names)), [LABELS[n] for n in names])
    ax.set_xlim(0,100)
    ax.invert_yaxis()
    ax.set_xlabel("Caught storms / all storms (%) — 95% percentile intervals")
    ax.set_title("Frozen catch rate: storm bootstrap (blue), event-date blocks (orange)")
    ax.grid(axis="x", alpha=.2)
    fig.tight_layout()
    save_svg(fig, DOCS / "caught-intervals.svg")
    plt.close(fig)
    available = [n for n in names if "chance" in result["groups"][n]]
    if not available:
        return
    fig, axes = plt.subplots(len(available), 2, figsize=(10, 2.1*len(available)), squeeze=False)
    for y, name in enumerate(available):
        data = json.loads((DOCS / "nulls" / (name + ".json")).read_text())
        for x, statistic in enumerate(("caught_counts", "policy_difference_usd")):
            ax = axes[y,x]
            field = "caught_storms" if x==0 else "policy_difference_usd"
            test = result["groups"][name]["chance"][field]
            ax.hist(data[statistic], bins=30, color="#73a8be", edgecolor="#eaf2f5")
            ax.axvline(test["statistic"],color="#b93825",lw=2,label="Observed")
            ax.set_title(LABELS[name] + (" — caught storms" if x==0 else " — policy USD difference"))
            ax.set_ylabel("Shuffles")
            ax.ticklabel_format(axis="x",style="plain",useOffset=False)
            ax.legend(fontsize=7)
    fig.tight_layout()
    save_svg(fig, DOCS / "timing-nulls.svg")
    plt.close(fig)
