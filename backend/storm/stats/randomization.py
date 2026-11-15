"""Conditional circular translations preserve clock durations and complete alarm trains."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .protocol import rng_for

MINUTE = pd.Timedelta(minutes=1)


@dataclass
class Train:
    pair: str
    start: pd.Timestamp
    horizon: int
    alarms: np.ndarray
    durations: np.ndarray
    censored: np.ndarray
    danger: np.ndarray
    danger_durations: np.ndarray
    danger_censored: np.ndarray
    feasible: np.ndarray


def prepare_train(unit, pair, detection):
    horizon = int((unit.end - unit.start) / MINUTE)
    feat = unit.feats[pair]
    observed = np.zeros(horizon + 1, bool)
    defined = np.zeros(horizon + 1, bool)
    keep = (feat.index >= unit.start) & (feat.index < unit.end)
    pos = ((feat.index[keep] - unit.start) / MINUTE).astype(int)
    observed[pos] = True
    defined[pos] = detection.frame.risk.loc[feat.index[keep]].notna().to_numpy()

    def rows(items):
        alarms, durations, censored = [], [], []
        for alarm, clear in items:
            if not unit.start <= alarm < unit.end:
                continue
            end = min(clear, unit.end) if clear is not None else unit.end
            alarms.append(int((alarm - unit.start) / MINUTE))
            durations.append(int((end - alarm) / MINUTE))
            censored.append(clear is None or clear >= unit.end)
        return np.asarray(alarms, int), np.asarray(durations, int), np.asarray(censored, bool)

    alarm, duration, censored = rows(detection.storm_alarms())
    danger, dduration, dcensored = rows([(e["time"], e["clear"]) for e in detection.events if e["type"] == "alarm"])
    offsets = np.arange(horizon, dtype=int)
    allowed = np.ones(horizon, bool)
    for aa, ds, cs in ((alarm, duration, censored), (danger, dduration, dcensored)):
        for a, d, c in zip(aa, ds, cs):
            shifted = (a + offsets) % horizon
            valid = (shifted + d <= horizon) & defined[shifted]
            if not c:
                valid &= observed[np.minimum(shifted + d, horizon)]
            allowed &= valid
    feasible = offsets[allowed] if len(alarm) + len(danger) else np.asarray([0])
    if not len(feasible) or 0 not in feasible:
        raise ValueError(f"Original offset infeasible: {unit.name}/{pair}")
    return Train(pair, unit.start, horizon, alarm, duration, censored, danger, dduration, dcensored, feasible)


def draw_offsets(train, unit_name, dataset, replicates=10000):
    rng = rng_for("timing-offsets", dataset, unit_name, train.pair)
    return rng.choice(train.feasible, size=replicates, replace=True)


def shifted(train, offsets, danger=False):
    starts = train.danger if danger else train.alarms
    duration = train.danger_durations if danger else train.durations
    alarms = (np.asarray(offsets)[:, None] + starts[None, :]) % train.horizon
    return alarms, alarms + duration[None, :]


def caught_counts(unit, trains, offsets, replicates=10000):
    """Vectorized copy of exact matching/share rules; tested against storm.evaluate."""
    counts = np.zeros(replicates, int)
    per_storm = {}
    for pair, train in trains.items():
        alarms, clear = shifted(train, offsets[pair])
        feat = unit.feats[pair]
        mid = np.full(train.horizon, np.nan)
        keep = (feat.index >= unit.start) & (feat.index < unit.end)
        positions = ((feat.index[keep] - unit.start) / MINUTE).astype(int)
        mid[positions] = feat.mid.loc[feat.index[keep]]
        for storm in unit.storms[unit.storms.pair == pair].itertuples():
            onset = int((storm.onset_utc - unit.start) / MINUTE)
            trough = int((storm.trough_utc - unit.start) / MINUTE)
            if alarms.shape[1]:
                matches = (alarms >= onset - 60) & (alarms <= trough) & (clear >= onset)
                first = np.min(np.where(matches, alarms, train.horizon), axis=1)
            else:
                first = np.full(replicates, train.horizon)
            valid = first < train.horizon
            share = np.zeros(replicates)
            share[valid & (first <= onset)] = 100
            later = valid & (first > onset) & (first < trough)
            if storm.onset_mid != storm.trough_mid:
                share[later] = np.clip((mid[first[later]] - storm.trough_mid) /
                                      (storm.onset_mid - storm.trough_mid) * 100, 0, 100)
            hit = valid & (share >= 50)
            counts += hit
            per_storm[storm.storm_id] = hit
    return counts, per_storm


def alarms_at(train, offset, danger=False):
    aa, cc = shifted(train, [offset], danger)
    censored = train.danger_censored if danger else train.censored
    return [(train.start + int(a) * MINUTE, train.start + int(c) * MINUTE, bool(z))
            for a, c, z in sorted(zip(aa[0], cc[0], censored))]


def null_summary(observed, values, degenerate=False):
    arr = np.asarray(values)
    exceed = int(np.sum(arr >= observed))
    p = (1 + exceed) / (len(arr) + 1)
    return {"statistic": observed, "replicates": len(arr), "exceedances": exceed,
            "p_value": p, "monte_carlo_se": float(np.sqrt(p * (1 - p) / (len(arr) + 1))),
            "null_median": float(np.median(arr)), "null_ci95": np.quantile(arr, [0.025, 0.975]).tolist(),
            "fully_degenerate": degenerate, "tail": "greater_or_equal"}


def holm(tests):
    ordered = sorted(tests, key=lambda t: t["p_value"])
    last = 0
    for rank, row in enumerate(ordered):
        last = max(last, min(1.0, (len(ordered) - rank) * row["p_value"]))
        row["holm_p_value"] = last
        row["holm_family_size"] = len(ordered)
