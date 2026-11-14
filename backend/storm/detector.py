"""Storm detector, version 1: direction-agnostic detection, book-aware alerts.

Detection (a storm is a storm, whichever way it blows)
  strength   max over the windows m in `move_windows` of
             |mid_t / mid_(t-m) - 1| / (sd_24h x sqrt(m)): the move of the last m minutes
             in units of its normal size (m = 1 is |z|). A window that spans a bar gap,
             or a change of `session` when the features carry one, is undefined.
  risk       clip(strength / strength_full + w_comove x [comove >= comove_min], 0, 1)
  direction  sign of the move in the window that set the strength (+1 pair up, -1 down)
  episode    opens at the first minute with risk >= squall_on and closes (all-clear) after
             `calm_minutes` consecutive minutes with risk < calm_off
  storm      inside an episode, once `storm_minutes` consecutive minutes have
             risk >= storm_on. State is 2 from then until the all-clear.
  watch      from `watch_lead_minutes` before each event in contracts/calendar.csv
             until `watch_after_minutes` after it (state 1 unless a storm is active);
             one watch event per calendar event, at its first watch minute

Book-aware alerts, given the book's signed exposure to the pair (> 0 long the base
currency, < 0 short it, 0 no position: no alerts)
  danger     the move goes against the exposure; fair wind: it goes in its favour
  squall     the first danger minute of an episode with risk >= squall_on, unless an
             alarm fires that minute or already has
  alarm      `storm_minutes` consecutive danger minutes with risk >= storm_on
  fair_wind  `storm_minutes` consecutive fair-wind minutes with risk >= storm_on
  all_clear  the close of an episode that reached storm level or raised an alert
Each alert fires at most once per episode.

Undefined risk (warm-up, gaps) breaks every run of minutes. Every threshold lives in
the config dict; storm.tune picks them on July and writes data/processed/detector_config.json.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .paths import CALENDAR_CSV, PROCESSED_DIR

CONFIG_PATH = PROCESSED_DIR / "detector_config.json"

DEFAULT_CONFIG = {
    "version": 1,
    "move_windows": [1, 3, 5],
    "strength_full": 10.0,
    "w_comove": 0.15,
    "comove_min": 2,
    "squall_on": 0.42,
    "storm_on": 0.7,
    "storm_minutes": 1,
    "calm_off": 0.3,
    "calm_minutes": 20,
    "watch_lead_minutes": 30,
    "watch_after_minutes": 15,
    "max_bar_gap_minutes": 5,
}

CALM, WATCH, STORM = 0, 1, 2


def load_calendar(path: Path = CALENDAR_CSV) -> pd.DataFrame:
    """Scheduled releases. An empty calendar (header only) or a missing file is fine."""
    cols = ["time_utc", "event", "region", "source_url", "verified"]
    if not path.exists():
        return pd.DataFrame(columns=cols)
    cal = pd.read_csv(path)
    if cal.empty:
        return pd.DataFrame(columns=cols)
    cal["time_utc"] = pd.to_datetime(cal["time_utc"], utc=True)
    return cal.sort_values("time_utc").reset_index(drop=True)


def load_config(path: Path = CONFIG_PATH) -> dict:
    """The tuned config (falls back to DEFAULT_CONFIG, with a warning, if not tuned yet)."""
    if not path.exists():
        print(f"warning: {path} missing; using the untuned DEFAULT_CONFIG (run `python -m storm.tune`)")
        return dict(DEFAULT_CONFIG)
    saved = json.loads(path.read_text())
    return {**DEFAULT_CONFIG, **saved["config"]}


def check_config(cfg: dict) -> None:
    if not cfg["calm_off"] <= cfg["squall_on"] <= cfg["storm_on"]:
        raise ValueError("config needs calm_off <= squall_on <= storm_on")
    if cfg["storm_minutes"] < 1 or cfg["calm_minutes"] < 1:
        raise ValueError("storm_minutes and calm_minutes must be >= 1")


def risk_frame(feat: pd.DataFrame, cfg: dict = DEFAULT_CONFIG) -> pd.DataFrame:
    """Per-minute `strength`, `risk` (0..1, NaN when undefined) and `direction` (-1, 0, +1)."""
    mid = feat["mid"].to_numpy(dtype=float)
    sd = feat["sd_24h"].to_numpy(dtype=float)
    t = feat.index.asi8 // 60_000_000_000  # minutes since epoch
    sess = feat["session"].to_numpy() if "session" in feat else None
    n = len(mid)
    strengths, signs = [], []
    for m in cfg["move_windows"]:
        s = np.full(n, np.nan)
        d = np.zeros(n)
        if n > m:
            move = mid[m:] / mid[:-m] - 1.0
            span = t[m:] - t[:-m]
            ok = span <= (m - 1) + cfg["max_bar_gap_minutes"]
            if sess is not None:
                ok &= sess[m:] == sess[:-m]   # never measure a move across a closed market
            val = np.abs(move) * 1e4 / (sd[m:] * np.sqrt(m))
            s[m:] = np.where(ok, val, np.nan)
            d[m:] = np.sign(move)
        strengths.append(s)
        signs.append(d)
    S = np.vstack(strengths)
    D = np.vstack(signs)
    filled = np.where(np.isnan(S), -np.inf, S)
    best = filled.argmax(axis=0)
    strength = filled[best, np.arange(n)]
    strength = np.where(np.isfinite(strength), strength, np.nan)
    direction = np.where(np.isnan(strength), 0, D[best, np.arange(n)]).astype(int)
    boost = cfg["w_comove"] * (feat["comove"].to_numpy() >= cfg["comove_min"])
    risk = np.clip(strength / cfg["strength_full"] + boost, 0.0, 1.0)
    return pd.DataFrame({"strength": strength, "risk": risk, "direction": direction}, index=feat.index)


@dataclass
class Episode:
    """One disturbed spell: opens at squall level, closes after the calm run."""
    start: pd.Timestamp
    storm_at: pd.Timestamp | None = None   # first minute at storm level (the detection alarm)
    direction: int = 0                     # direction of the move at storm_at
    end: pd.Timestamp | None = None        # all-clear minute; None if still open at the end


@dataclass
class DetectorResult:
    frame: pd.DataFrame                    # strength, risk, direction, state
    events: list[dict]                     # book-aware: watch, squall, alarm, fair_wind, all_clear
    episodes: list[Episode] = field(default_factory=list)

    def storm_alarms(self) -> list[tuple[pd.Timestamp, pd.Timestamp | None]]:
        """Direction-agnostic storm-level alarms as (alarm time, all-clear time)."""
        return [(e.storm_at, e.end) for e in self.episodes if e.storm_at is not None]


def _watch_index(idx: pd.DatetimeIndex, calendar: pd.DataFrame, lead: pd.Timedelta,
                 after: pd.Timedelta) -> np.ndarray:
    """Calendar row whose watch window [event - lead, event + after) holds each minute, or -1.
    Where windows overlap, the earlier event keeps the minute."""
    watch_of = np.full(len(idx), -1)
    for k, release in enumerate(calendar["time_utc"] if len(calendar) else []):
        mask = (idx >= release - lead) & (idx < release + after)
        watch_of[mask & (watch_of < 0)] = k
    return watch_of


def run_detector(
    feat: pd.DataFrame,
    calendar: pd.DataFrame | None = None,
    cfg: dict = DEFAULT_CONFIG,
    exposure: float = 0.0,
    rf: pd.DataFrame | None = None,
) -> DetectorResult:
    """Run v1 over one pair's features. `exposure` is the book's signed position in the pair.

    `rf` is an optional precomputed risk_frame(feat, cfg) (the grid search reuses it).
    """
    check_config(cfg)
    rf = risk_frame(feat, cfg) if rf is None else rf
    idx = feat.index
    calendar = load_calendar() if calendar is None else calendar
    watch_of = _watch_index(idx, calendar, pd.Timedelta(minutes=cfg["watch_lead_minutes"]),
                            pd.Timedelta(minutes=cfg["watch_after_minutes"]))
    book = int(np.sign(exposure))

    risk = rf["risk"].to_numpy()
    dirs = rf["direction"].to_numpy()
    t_min = idx.asi8 // 60_000_000_000
    storm_on, squall_on, calm_off = cfg["storm_on"], cfg["squall_on"], cfg["calm_off"]
    k, calm_n, max_gap = cfg["storm_minutes"], cfg["calm_minutes"], cfg["max_bar_gap_minutes"]

    state = np.zeros(len(idx), dtype=int)
    events: list[dict] = []
    episodes: list[Episode] = []
    ep: Episode | None = None
    alerted = squalled = fair = False
    hot = hot_against = hot_favour = cold = 0
    announced: set[int] = set()
    for i in range(len(idx)):
        if i and t_min[i] - t_min[i - 1] > max_gap:
            hot = hot_against = hot_favour = 0
        r = risk[i]
        defined = not np.isnan(r)
        side = book * dirs[i]                  # < 0 danger, > 0 fair wind, 0 no book / flat
        high = defined and r >= storm_on
        hot = hot + 1 if high else 0
        hot_against = hot_against + 1 if high and side < 0 else 0
        hot_favour = hot_favour + 1 if high and side > 0 else 0
        cold = cold + 1 if defined and r < calm_off else 0
        t = idx[i]

        if ep is None and defined and r >= squall_on:
            ep = Episode(start=t)
            episodes.append(ep)
            alerted = squalled = fair = False
        if ep is not None:
            if ep.storm_at is None and hot >= k:
                ep.storm_at, ep.direction = t, int(dirs[i])
            if not alerted and hot_against >= k:
                alerted = True
                events.append({"time": t, "type": "alarm", "direction": int(dirs[i])})
            elif not alerted and not squalled and side < 0 and r >= squall_on:
                squalled = True
                events.append({"time": t, "type": "squall", "direction": int(dirs[i])})
            if not fair and hot_favour >= k:
                fair = True
                events.append({"time": t, "type": "fair_wind", "direction": int(dirs[i])})
            if cold >= calm_n:
                ep.end = t
                if ep.storm_at is not None or alerted or squalled or fair:
                    events.append({"time": t, "type": "all_clear"})
                ep = None
                hot = hot_against = hot_favour = 0

        if ep is not None and ep.storm_at is not None:
            state[i] = STORM
        elif watch_of[i] >= 0:
            state[i] = WATCH
            if watch_of[i] not in announced:
                announced.add(int(watch_of[i]))
                row = calendar.iloc[watch_of[i]]
                events.append({"time": t, "type": "watch", "at": row["time_utc"], "event": str(row["event"])})

    frame = rf.assign(state=state)
    return DetectorResult(frame, events, episodes)
