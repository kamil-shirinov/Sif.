"""Storm detector, version 0.

risk = clip(w_vol * max(0, vol_ratio - 1) + w_z * |z| + w_comove * [comove >= comove_min], 0, 1)

State per minute: 0 calm, 1 watch, 2 storm.
  storm  after `storm_on_minutes` consecutive minutes with risk >= storm_on (the alarm
         fires on the minute the condition completes)
  calm   again after `calm_off_minutes` consecutive minutes with risk < calm_off
  watch  the `watch_lead_minutes` before any release in contracts/calendar.csv, unless
         already in storm

Undefined risk (warm-up, gaps) counts towards neither run. All thresholds live in
THRESHOLDS; they get tuned on July and tested on August.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .paths import CALENDAR_CSV

THRESHOLDS = {
    "w_vol": 0.15,
    "w_z": 0.12,
    "w_comove": 0.2,
    "comove_min": 2,
    "storm_on": 0.7,
    "storm_on_minutes": 2,
    "calm_off": 0.35,
    "calm_off_minutes": 20,
    "watch_lead_minutes": 30,
    "max_bar_gap_minutes": 5,  # a longer gap between bars breaks a run of storm minutes
}

CALM, WATCH, STORM = 0, 1, 2


def risk_score(feat: pd.DataFrame, th: dict = THRESHOLDS) -> pd.Series:
    raw = (
        th["w_vol"] * np.maximum(0.0, feat["vol_ratio"] - 1.0)
        + th["w_z"] * feat["z"].abs()
        + th["w_comove"] * (feat["comove"] >= th["comove_min"]).astype(float)
    )
    return raw.clip(0.0, 1.0).rename("risk")


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


def run_detector(
    feat: pd.DataFrame, calendar: pd.DataFrame | None = None, th: dict = THRESHOLDS
) -> tuple[pd.DataFrame, list[dict]]:
    """Returns (frame with `risk` and `state`, events). Events: {time, type[, at, event]}."""
    risk = risk_score(feat, th)
    idx = feat.index
    calendar = load_calendar() if calendar is None else calendar
    lead = pd.Timedelta(minutes=th["watch_lead_minutes"])
    max_gap = pd.Timedelta(minutes=th["max_bar_gap_minutes"])

    # Watch windows: [release - lead, release).
    watch_of = np.full(len(idx), -1)
    for k, release in enumerate(calendar["time_utc"] if len(calendar) else []):
        mask = (idx >= release - lead) & (idx < release)
        watch_of[mask & (watch_of < 0)] = k

    state = np.zeros(len(idx), dtype=int)
    events: list[dict] = []
    in_storm = False
    hot = cold = 0
    prev_t = None
    last_watch = -1
    r = risk.to_numpy()
    for i, t in enumerate(idx):
        if prev_t is not None and t - prev_t > max_gap:
            hot = 0
        prev_t = t
        ri = r[i]
        defined = not np.isnan(ri)
        hot = hot + 1 if defined and ri >= th["storm_on"] else 0
        cold = cold + 1 if defined and ri < th["calm_off"] else 0

        if not in_storm and hot >= th["storm_on_minutes"]:
            in_storm, cold = True, 0
            events.append({"time": t, "type": "alarm"})
        elif in_storm and cold >= th["calm_off_minutes"]:
            in_storm, hot = False, 0
            events.append({"time": t, "type": "all_clear"})

        if in_storm:
            state[i] = STORM
        elif watch_of[i] >= 0:
            state[i] = WATCH
            if watch_of[i] != last_watch:
                row = calendar.iloc[watch_of[i]]
                events.append(
                    {"time": t, "type": "watch", "at": row["time_utc"], "event": str(row["event"])}
                )
        if watch_of[i] >= 0:
            last_watch = watch_of[i]

    out = pd.DataFrame({"risk": risk, "state": state}, index=idx)
    return out, events
