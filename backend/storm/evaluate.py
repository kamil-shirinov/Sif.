"""Score storm alarms against the labelled storms (shared by storm.tune, storm.backtest
and storm.export).

Alarms are direction-agnostic and per pair: (alarm time, all-clear time or None).

One matcher, alarm_matches(), decides whether an alarm belongs to a labelled storm on
its pair, everywhere (the evaluator here and the bundles' alarm events in storm.export):
  onset - 60 min <= alarm <= trough, and still in force at onset (all-clear >= onset).
An alarm that fired and cleared before the onset is not credited, and neither is a storm
already inside an alarm that fired earlier than onset - 60 min: a detector that stays
in storm state cannot game the score. A storm's alarm is the earliest matching one.

Each storm has two onsets (storm.labels): `onset`, the start of its strongest 15-minute
window (the one used for matching and `caught`), and `first_onset`, the start of its
first triggering window (never later). Minutes and share ahead are reported against both:

  move_ahead_pct   share of the onset-to-trough move still ahead at the alarm minute:
                   (mid_alarm - trough) / (onset - trough), clipped to 0..100 (100 if the
                   alarm came before the onset)
  minutes          alarm - onset (negative when it came first)
  ..._first_onset  the same two with first_onset in place of onset
  alarmed          the storm has an alarm (at or before the trough)
  caught           alarmed with at least half the move still ahead (move_ahead_pct >= 50)

A false alarm is an alarm on a pair outside [onset - 60 min, end + 60 min] of every
labelled storm on that pair. Two rates, each labelled exactly:
  false_alarms_per_day          pair alarms per observed day: every pair's false alarm
                                counts on its own (one USD shock that alarms two pairs is two)
  false_alarm_episodes_per_day  distinct alert episodes per observed day: false alarms on
                                any pairs, sorted by time; an episode opens at the first one
                                not yet in an episode and holds every false alarm within 15
                                minutes of that opening alarm (so any two alarms in one
                                episode are at most 15 minutes apart)
An observed day is 1,440 minutes with a bar on any pair in the split.

Nothing is rounded while scoring: classification (caught), tuning constraints and ranking
all see the exact values. for_display() rounds a finished metrics object for JSON and print.
"""
from __future__ import annotations

import math

import pandas as pd

LINK_BEFORE = pd.Timedelta(minutes=60)
FALSE_AFTER = pd.Timedelta(minutes=60)
EPISODE_GAP = pd.Timedelta(minutes=15)
CAUGHT_PCT = 50.0

Alarm = tuple[pd.Timestamp, "pd.Timestamp | None"]


def market_days(feats: dict[str, pd.DataFrame], start: pd.Timestamp, end: pd.Timestamp) -> float:
    idx = None
    for f in feats.values():
        part = f.index[(f.index >= start) & (f.index < end)]
        idx = part if idx is None else idx.union(part)
    return len(idx) / 1440.0 if idx is not None else 0.0


def observed_minutes(feats: dict[str, pd.DataFrame], start: pd.Timestamp, end: pd.Timestamp) -> int:
    """Pair-minutes with a bar: the sum over pairs of each pair's own bars in [start, end)."""
    return int(sum(((f.index >= start) & (f.index < end)).sum() for f in feats.values()))


def move_ahead_pct(alarm: pd.Timestamp, storm, mid: pd.Series, first: bool = False) -> float | None:
    """Share of the move from onset (or first_onset) to trough still ahead at the alarm.
    None when that move is zero (the share is undefined)."""
    start = storm.first_onset_utc if first else storm.onset_utc
    start_mid = storm.first_onset_mid if first else storm.onset_mid
    if alarm <= start:
        return 100.0
    if alarm >= storm.trough_utc:
        return 0.0
    if start_mid == storm.trough_mid:
        return None
    share = (float(mid.loc[alarm]) - storm.trough_mid) / (start_mid - storm.trough_mid) * 100.0
    return min(100.0, max(0.0, share))


def alarm_matches(alarm: pd.Timestamp, clear: pd.Timestamp | None, storm) -> bool:
    """The one alarm-to-storm rule: in [onset - 60 min, trough] and in force at onset."""
    return (storm.onset_utc - LINK_BEFORE <= alarm <= storm.trough_utc
            and (clear is None or clear >= storm.onset_utc))


def link_alarm(alarms: list[Alarm], storm) -> pd.Timestamp | None:
    linked = [a for a, clear in alarms if alarm_matches(a, clear, storm)]
    return min(linked) if linked else None


def false_alarm_episodes(times: list[pd.Timestamp]) -> int:
    """Distinct alert episodes: each opens at a false alarm not yet in an episode and holds
    every false alarm (any pair) within EPISODE_GAP of that opening alarm."""
    n, opened = 0, None
    for t in sorted(times):
        if opened is None or t - opened > EPISODE_GAP:
            n, opened = n + 1, t
    return n


def _median(xs: list[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    return float(pd.Series(xs).median()) if xs else None


def _minutes(a: pd.Timestamp, t: pd.Timestamp) -> int:
    return int((a - t) / pd.Timedelta(minutes=1))


def per_storm_row(storm, alarm: pd.Timestamp | None, mid: pd.Series) -> dict:
    ahead = None if alarm is None else move_ahead_pct(alarm, storm, mid)
    first = getattr(storm, "first_onset_utc", None)
    has_first = alarm is not None and first is not None and not pd.isna(first)
    ahead_first = move_ahead_pct(alarm, storm, mid, first=True) if has_first else None
    return {
        "storm_id": storm.storm_id,
        "alarm_utc": None if alarm is None else f"{alarm:%Y-%m-%d %H:%M}",
        "move_ahead_pct": ahead,
        "minutes": None if alarm is None else _minutes(alarm, storm.onset_utc),
        "caught": ahead is not None and ahead >= CAUGHT_PCT,
        "move_ahead_pct_first_onset": ahead_first,
        "minutes_first_onset": _minutes(alarm, first) if has_first else None,
        "caught_first_onset": ahead_first is not None and ahead_first >= CAUGHT_PCT,
    }


def score(
    alarms: dict[str, list[Alarm]],
    storms: pd.DataFrame,
    mids: dict[str, pd.Series],
    days: float,
    squalls: int | None = None,
) -> dict:
    """Metrics for one method, unrounded. `alarms` and `storms` must already be cut to the split."""
    per_storm = [per_storm_row(s, link_alarm(alarms.get(s.pair, []), s), mids[s.pair])
                 for s in storms.itertuples()]

    false_times = []
    for pair, items in alarms.items():
        mine = storms[storms["pair"] == pair]
        for a, _ in items:
            near = ((mine["onset_utc"] - LINK_BEFORE <= a) & (a <= mine["end_utc"] + FALSE_AFTER)).any()
            if not near:
                false_times.append(a)
    false = len(false_times)
    episodes = false_alarm_episodes(false_times)

    alarmed = [p for p in per_storm if p["alarm_utc"] is not None]
    return {
        "storms": len(per_storm),
        "alarmed": len(alarmed),
        "caught": sum(p["caught"] for p in per_storm),
        "median_move_ahead_pct": _median([p["move_ahead_pct"] for p in alarmed]),
        "median_minutes_to_alarm": _median([p["minutes"] for p in alarmed]),
        "caught_first_onset": sum(p["caught_first_onset"] for p in per_storm),
        "median_move_ahead_pct_first_onset": _median([p["move_ahead_pct_first_onset"] for p in alarmed]),
        "median_minutes_to_alarm_first_onset": _median([p["minutes_first_onset"] for p in alarmed]),
        "storm_alarms": sum(len(v) for v in alarms.values()),
        "false_alarms": int(false),
        "false_alarms_per_day": false / days if days > 0 else None,
        "false_alarm_episodes": episodes,
        "false_alarm_episodes_per_day": episodes / days if days > 0 else None,
        "squalls_per_day": None if squalls is None else (squalls / days if days > 0 else None),
        "days": days,
        "per_storm": per_storm,
    }


def v1_alarms_and_squalls(results: dict, start: pd.Timestamp, end: pd.Timestamp) -> tuple[dict, int]:
    """Storm alarms per pair and the count of squall-only episodes, from v1 DetectorResults."""
    alarms, squalls = {}, 0
    for pair, res in results.items():
        alarms[pair] = [(a, c) for a, c in res.storm_alarms() if start <= a < end]
        squalls += sum(1 for e in res.episodes if e.storm_at is None and start <= e.start < end)
    return alarms, squalls


# Display precision by key (exact key first, then suffix). Anything else is left as is.
_DIGITS_EXACT = {"days": 2, "watch_precision": 2, "leverage": 2, "storm_state_share_pct": 2}
_DIGITS_SUFFIX = (("_per_day", 2), ("_pct", 1), ("_usd", 0), ("_minutes", 1),
                  ("median_minutes_to_alarm", 1), ("median_minutes_to_alarm_first_onset", 1),
                  ("_bp", 1), ("_price", 6))


def _digits(key: str) -> int | None:
    key = key.removesuffix("_first_onset")      # median_move_ahead_pct_first_onset rounds as *_pct
    if key in _DIGITS_EXACT:
        return _DIGITS_EXACT[key]
    for suffix, nd in _DIGITS_SUFFIX:
        if key.endswith(suffix):
            return nd
    return None


def for_display(obj, key: str = ""):
    """A copy of a metrics object with floats rounded for JSON and print (by key name:
    *_per_day, days, watch_precision 2 dp; *_pct, *_bp, minutes medians 1 dp; *_usd whole
    dollars; *_price 6 dp). Only output goes through this: scoring never sees it."""
    if isinstance(obj, dict):
        return {k: for_display(v, k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [for_display(v, key) for v in obj]
    if isinstance(obj, float) and not isinstance(obj, bool):
        if not math.isfinite(obj):
            raise ValueError(f"non-finite metric {key}={obj!r}")
        nd = _digits(key)
        if nd is None:
            return obj
        return int(round(obj)) if nd == 0 else round(obj, nd) + 0.0
    return obj
