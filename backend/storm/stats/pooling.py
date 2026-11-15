"""Fixed-priority observation accounting without gapped-history relabelling."""
from __future__ import annotations

from dataclasses import replace

import pandas as pd

from .bootstrap import summarize
from .datasets import daily_rows, false_openings, utc

PRIORITY = ("sgx_august", "oos_round1", "oos_round2", "chips_new")


def prepare_pooling(units):
    seen = {}
    for dataset in PRIORITY:
        selected = [u for u in units if u.dataset == dataset]
        for unit in selected:
            duplicates = {}
            for pair, feat in unit.feats.items():
                idx = feat.index[(feat.index >= unit.start) & (feat.index < unit.end)]
                prior = seen.get((unit.metadata["source"], pair), pd.DatetimeIndex([], tz="UTC"))
                duplicates[pair] = idx.intersection(prior)
            keep_storm = {s.storm_id: s.onset_utc not in duplicates[s.pair] for s in unit.storms.itertuples()}
            keep_book = {w["name"]: not any(((duplicates[p] >= w["start"]) & (duplicates[p] < w["end"])).any()
                                          for p in w["pairs"]) for w in unit.policy_windows}
            unit.metadata["pool_duplicates"] = duplicates
            unit.metadata["pool_keep_storm"] = keep_storm
            unit.metadata["pool_keep_book"] = keep_book
            unit.metadata["pooling_summary"] = {
                "priority": list(PRIORITY), "duplicate_minutes_by_pair": {p: len(idx) for p, idx in duplicates.items()},
                "excluded_storm_ids": [s for s, keep in keep_storm.items() if not keep],
                "excluded_policy_books": [s for s, keep in keep_book.items() if not keep],
                "rule": "same source/pair/UTC minute, higher-priority dataset first; drop entire overlapping reset book"}
        # Within-dataset independent windows retain their original design; only a
        # higher-priority dataset can remove a lower-priority contribution.
        for unit in selected:
            for pair, feat in unit.feats.items():
                key = (unit.metadata["source"], pair)
                idx = feat.index[(feat.index >= unit.start) & (feat.index < unit.end)]
                seen[key] = idx.union(seen.get(key, pd.DatetimeIndex([], tz="UTC")))


def pooled_metric(unit, alarms, metric):
    dup = unit.metadata["pool_duplicates"]
    if not any(len(idx) for idx in dup.values()):
        return dict(metric)
    retained_feats = {p: f[~f.index.isin(dup[p])] for p, f in unit.feats.items()}
    filtered = {p: [(a,c) for a,c in items if a not in dup[p]] for p, items in alarms.items()}
    # False classification keeps ALL original labels, including labels assigned to
    # a higher-priority sample. Exposure uses only retained observed minutes.
    view = replace(unit, feats=retained_feats)
    daily, trading = daily_rows(view, filtered)
    false, openings = false_openings(filtered, unit.storms)
    rows = [r for r in metric["per_storm"] if unit.metadata["pool_keep_storm"][r["storm_id"]]]
    p = summarize(rows, daily)
    result = {"storms": len(rows), "alarmed": p["alarmed"], "caught": p["caught"],
              "caught_first_onset": p["caught_first_onset"],
              "median_move_ahead_pct": p["median_share_ahead_pct"], "median_minutes_to_alarm": p["median_minutes_to_alarm"],
              "median_move_ahead_pct_first_onset": p["median_share_ahead_pct_first_onset"],
              "median_minutes_to_alarm_first_onset": p["median_minutes_to_alarm_first_onset"],
              "days": p["observed_days"], "storm_alarms": sum(map(len, filtered.values())),
              "false_alarms": len(false), "false_alarm_episodes": len(openings),
              "false_alarm_episodes_per_day": p["false_alert_episodes_per_observed_day"],
              "false_alarms_per_day": len(false)/p["observed_days"] if p["observed_days"] else None,
              "per_storm": rows, "daily": daily, "trading_daily": trading}
    return result
