"""Score storm alarms against the labelled storms (shared by storm.tune and storm.backtest).

Alarms are direction-agnostic and per pair: (alarm time, all-clear time or None).

For each labelled storm on a pair, its alarm is the earliest alarm on that pair with
  onset - 60 min <= alarm <= trough, and still in force at onset (all-clear >= onset).
An alarm that fired and cleared before the onset is not credited, and neither is a storm
already inside an alarm that fired earlier than onset - 60 min: a detector that stays
in storm state cannot game the score.

  move_ahead_pct   share of the onset-to-trough move still ahead at the alarm minute:
                   (mid_alarm - trough) / (onset - trough), clipped to 0..100 (100 if the
                   alarm came before the onset)
  minutes          alarm - onset (negative when it came first)
  alarmed          the storm has an alarm (at or before the trough)
  caught           alarmed with at least half the move still ahead (move_ahead_pct >= 50)

A false alarm is an alarm on a pair outside [onset - 60 min, end + 60 min] of every
labelled storm on that pair. Each pair's false alarm counts on its own (one USD shock that
alarms two pairs is two false alarms). A false alarm episode de-duplicates across pairs:
false alarms (any pairs) sorted by time join one episode while each is within 15 minutes
of the previous one. Rates are per day of market data: the minutes with a bar on any pair
in the split, divided by 1,440.
"""
from __future__ import annotations

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


def move_ahead_pct(alarm: pd.Timestamp, storm, mid: pd.Series) -> float:
    if alarm <= storm.onset_utc:
        return 100.0
    if alarm >= storm.trough_utc:
        return 0.0
    share = (float(mid.loc[alarm]) - storm.trough_mid) / (storm.onset_mid - storm.trough_mid) * 100.0
    return min(100.0, max(0.0, share))


def link_alarm(alarms: list[Alarm], storm) -> pd.Timestamp | None:
    linked = [a for a, clear in alarms
              if storm.onset_utc - LINK_BEFORE <= a <= storm.trough_utc
              and (clear is None or clear >= storm.onset_utc)]
    return min(linked) if linked else None


def false_alarm_episodes(times: list[pd.Timestamp]) -> int:
    """Cross-pair de-duplication: sorted false alarms within EPISODE_GAP of the previous one
    belong to the same episode."""
    ts = sorted(times)
    return sum(1 for k, t in enumerate(ts) if k == 0 or t - ts[k - 1] > EPISODE_GAP)


def _median(xs: list[float]) -> float | None:
    return round(float(pd.Series(xs).median()), 1) if xs else None


def score(
    alarms: dict[str, list[Alarm]],
    storms: pd.DataFrame,
    mids: dict[str, pd.Series],
    days: float,
    squalls: int | None = None,
) -> dict:
    """Metrics for one method. `alarms` and `storms` must already be cut to the split."""
    per_storm = []
    for s in storms.itertuples():
        a = link_alarm(alarms.get(s.pair, []), s)
        ahead = None if a is None else round(move_ahead_pct(a, s, mids[s.pair]), 1)
        per_storm.append({
            "storm_id": s.storm_id,
            "alarm_utc": None if a is None else f"{a:%Y-%m-%d %H:%M}",
            "move_ahead_pct": ahead,
            "minutes": None if a is None else int((a - s.onset_utc) / pd.Timedelta(minutes=1)),
            "caught": ahead is not None and ahead >= CAUGHT_PCT,
        })

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
        "storm_alarms": sum(len(v) for v in alarms.values()),
        "false_alarms": int(false),
        "false_alarms_per_day": round(false / days, 2) if days > 0 else None,
        "false_alarm_episodes": episodes,
        "false_alarm_episodes_per_day": round(episodes / days, 2) if days > 0 else None,
        "squalls_per_day": None if squalls is None else (round(squalls / days, 2) if days > 0 else None),
        "days": round(days, 2),
        "per_storm": per_storm,
    }


def v1_alarms_and_squalls(results: dict, start: pd.Timestamp, end: pd.Timestamp) -> tuple[dict, int]:
    """Storm alarms per pair and the count of squall-only episodes, from v1 DetectorResults."""
    alarms, squalls = {}, 0
    for pair, res in results.items():
        alarms[pair] = [(a, c) for a, c in res.storm_alarms() if start <= a < end]
        squalls += sum(1 for e in res.episodes if e.storm_at is None and start <= e.start < end)
    return alarms, squalls
