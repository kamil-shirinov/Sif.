"""Percentile storm/day and joint-event-date uncertainty, with fixed strata."""
from __future__ import annotations

import warnings

import numpy as np

from .protocol import rng_for

STORM_FIELDS = {"alarmed_share": "alarmed", "caught_share": "caught",
                "caught_share_first_onset": "caught_first_onset",
                "median_share_ahead_pct": "move_ahead_pct", "median_minutes_to_alarm": "minutes",
                "median_share_ahead_pct_first_onset": "move_ahead_pct_first_onset",
                "median_minutes_to_alarm_first_onset": "minutes_first_onset"}


def interval(values, point=None):
    values = np.asarray(values, float)
    valid = values[np.isfinite(values)]
    return {"estimate": point, "ci95": np.quantile(valid, [0.025, 0.975]).tolist() if len(valid) else [None, None],
            "replicates": len(values), "undefined_replicates": len(values) - len(valid)}


def _arrays(rows):
    return {name: np.asarray([bool(r["alarm_utc"] is not None) if field == "alarmed" else
                             np.nan if r.get(field) is None else r[field] for r in rows], float)
            for name, field in STORM_FIELDS.items()}


def summarize(rows, daily, trading_daily=()):
    n = len(rows)
    arrays = _arrays(rows)
    result = {"storms": n, "alarmed": sum(r["alarm_utc"] is not None for r in rows),
              "caught": sum(r["caught"] for r in rows),
              "caught_first_onset": sum(r["caught_first_onset"] for r in rows)}
    for name, values in arrays.items():
        result[name] = None if not np.isfinite(values).any() else float(
            np.mean(values) if "share" in name and "median" not in name else np.nanmedian(values))
    minutes = sum(r["observed_minutes"] for r in daily)
    episodes = sum(r["episodes"] for r in daily)
    result.update(observed_days=minutes / 1440, false_episodes=episodes,
                  false_alert_episodes_per_observed_day=episodes * 1440 / minutes if minutes else None)
    if trading_daily:
        result["false_alert_episodes_per_trading_day"] = sum(r["episodes"] for r in trading_daily) / len(trading_daily)
        result["trading_days"] = len(trading_daily)
    return result


def uncertainty(rows, daily, key, replicates=10000, trading_daily=()):
    """Pooled sampling fixes each dataset's actual storm/day count, not equal weights."""
    point = summarize(rows, daily, trading_daily)
    strata = sorted({r["dataset"] for r in rows})
    fields = {name: [] for name in STORM_FIELDS}
    for dataset in strata:
        group = [r for r in rows if r["dataset"] == dataset]
        rng = rng_for("bootstrap-storm", key, dataset)
        draws = rng.integers(0, len(group), size=(replicates, len(group)))
        for name, values in _arrays(group).items():
            fields[name].append(values[draws])
    result = {}
    for name, parts in fields.items():
        if not parts:
            result[name] = interval(np.full(replicates, np.nan), point[name])
            continue
        sample = np.concatenate(parts, axis=1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            vals = np.mean(sample, axis=1) if "median" not in name else np.nanmedian(sample, axis=1)
        result[name] = interval(vals, point[name])

    num, den = np.zeros(replicates), np.zeros(replicates)
    for dataset in sorted({r["dataset"] for r in daily}):
        group = [r for r in daily if r["dataset"] == dataset]
        rng = rng_for("bootstrap-day", key, dataset)
        draws = rng.integers(0, len(group), size=(replicates, len(group)))
        num += np.asarray([r["episodes"] for r in group])[draws].sum(axis=1)
        den += np.asarray([r["observed_minutes"] for r in group])[draws].sum(axis=1) / 1440
    values = np.divide(num, den, out=np.full(replicates, np.nan), where=den > 0)
    result["false_alert_episodes_per_observed_day"] = interval(values, point["false_alert_episodes_per_observed_day"])
    if trading_daily:
        rng = rng_for("bootstrap-trading-day", key)
        draws = rng.integers(0, len(trading_daily), size=(replicates, len(trading_daily)))
        vals = np.asarray([r["episodes"] for r in trading_daily])[draws].mean(axis=1)
        result["false_alert_episodes_per_trading_day"] = interval(vals, point["false_alert_episodes_per_trading_day"])

    # Resample all storm rows on the same event date jointly across pairs/tickers.
    block_num = {name: np.zeros(replicates) for name in ("alarmed_share", "caught_share")}
    block_den = np.zeros(replicates)
    blocks_count = 0
    for dataset in strata:
        group = [r for r in rows if r["dataset"] == dataset]
        blocks = sorted({(r["unit"], r["block"]) for r in group})
        blocks_count += len(blocks)
        rng = rng_for("bootstrap-date-block", key, dataset)
        draws = rng.integers(0, len(blocks), size=(replicates, len(blocks)))
        sizes, alarmed, caught = [], [], []
        for unit, date in blocks:
            part = [r for r in group if (r["unit"], r["block"]) == (unit, date)]
            sizes.append(len(part))
            alarmed.append(sum(r["alarm_utc"] is not None for r in part))
            caught.append(sum(r["caught"] for r in part))
        block_den += np.asarray(sizes)[draws].sum(axis=1)
        block_num["alarmed_share"] += np.asarray(alarmed)[draws].sum(axis=1)
        block_num["caught_share"] += np.asarray(caught)[draws].sum(axis=1)
    result["date_block"] = {name: interval(np.divide(num, block_den, out=np.full(replicates, np.nan), where=block_den > 0), point[name])
                            for name, num in block_num.items()}
    result["date_block"]["blocks"] = blocks_count
    return {"point": point, "intervals": result}


def paired_caught_difference(v1_rows, baseline_rows, key, replicates=10000):
    other = {(r["unit"], r["storm_id"]): r for r in baseline_rows}
    if set(other) != {(r["unit"], r["storm_id"]) for r in v1_rows}:
        raise ValueError("Baseline comparison must use identical storms")
    differences, sizes = [], []
    for dataset in sorted({r["dataset"] for r in v1_rows}):
        group = [r for r in v1_rows if r["dataset"] == dataset]
        delta = np.asarray([int(r["caught"]) - int(other[r["unit"], r["storm_id"]]["caught"]) for r in group])
        rng = rng_for("paired-baseline", key, dataset)
        draws = rng.integers(0, len(group), size=(replicates, len(group)))
        differences.append(delta[draws].sum(axis=1))
        sizes.append(len(group))
    if not sizes:
        return interval(np.full(replicates, np.nan), None)
    point = sum(int(r["caught"]) - int(other[r["unit"], r["storm_id"]]["caught"]) for r in v1_rows) / sum(sizes)
    return interval(np.sum(differences, axis=0) / sum(sizes), point)
