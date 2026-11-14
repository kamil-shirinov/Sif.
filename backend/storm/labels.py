"""Label storms in the spot history.

    python -m storm.labels      -> data/processed/storms.csv and a printed table

A 15-minute window triggers when |move| >= max(30 bp, 8 x sd_24h x sqrt(15)), with
sd_24h taken at the window's start (the calm level before the move). Triggering
windows less than 6 hours apart on the same pair are one storm. For each storm:

  onset    start of its strongest 15-minute window
  trough   the extreme mid, in that window's direction, from onset to the end of
           the last triggering window
  move_bp  trough mid / onset mid - 1, in basis points (signed)
  duration trough - onset, in minutes
  kind     scheduled when the onset is within 15 minutes (either side) of an event in
           contracts/calendar.csv, else unscheduled; event = that event's name (the
           nearest one if several qualify), empty when unscheduled
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from .features import PAIRS, build_features, usd_sign
from .paths import PROCESSED_DIR

WINDOW = pd.Timedelta(minutes=15)
MIN_MOVE_BP = 30.0
SD_MULT = 8.0
MERGE_GAP = pd.Timedelta(hours=6)
SCHEDULED_WITHIN = pd.Timedelta(minutes=15)

STORM_COLUMNS = [
    "storm_id", "pair", "onset_utc", "trough_utc", "end_utc", "move_bp", "usd_move_bp",
    "duration_min", "peak_15m_bp", "onset_mid", "trough_mid", "kind", "event", "event_utc",
]


def window_moves(feat: pd.DataFrame) -> pd.DataFrame:
    """15-minute move ending at every bar, and its trigger threshold."""
    mid = feat["mid"]
    start_ts = feat.index - WINDOW
    start_mid = mid.reindex(start_ts).to_numpy()
    start_sd = feat["sd_24h"].reindex(start_ts).to_numpy()
    move = (mid.to_numpy() / start_mid - 1.0) * 1e4
    thresh = np.maximum(MIN_MOVE_BP, SD_MULT * start_sd * math.sqrt(WINDOW / pd.Timedelta(minutes=1)))
    w = pd.DataFrame({"move_bp": move, "threshold_bp": thresh}, index=feat.index)
    # Undefined start price or sd -> undefined threshold -> the window cannot trigger.
    w["trigger"] = np.abs(w["move_bp"]) >= w["threshold_bp"]
    return w


def find_storms(feat: pd.DataFrame, pair: str) -> list[dict]:
    w = window_moves(feat)
    trig = w[w["trigger"]]
    if trig.empty:
        return []
    cluster = (trig.index.to_series().diff() > MERGE_GAP).cumsum().to_numpy()
    mid = feat["mid"]
    storms = []
    for c in np.unique(cluster):
        part = trig[cluster == c]
        peak_end = part["move_bp"].abs().idxmax()
        peak = float(part.loc[peak_end, "move_bp"])
        onset = peak_end - WINDOW
        end = part.index[-1]
        path = mid.loc[onset:end]
        trough = path.idxmin() if peak < 0 else path.idxmax()
        move = (mid[trough] / mid[onset] - 1.0) * 1e4
        sign = usd_sign(pair)
        usd_move = move if sign > 0 else (1.0 / (1.0 + move / 1e4) - 1.0) * 1e4
        storms.append(
            {
                "pair": pair,
                "onset_utc": onset,
                "trough_utc": trough,
                "end_utc": end,
                "move_bp": round(float(move), 1),
                "usd_move_bp": round(float(usd_move), 1),
                "duration_min": int((trough - onset) / pd.Timedelta(minutes=1)),
                "peak_15m_bp": round(peak, 1),
                "onset_mid": float(mid[onset]),
                "trough_mid": float(mid[trough]),
            }
        )
    return storms


def scheduled_event(onset: pd.Timestamp, calendar: pd.DataFrame | None) -> tuple[str, pd.Timestamp] | None:
    """(name, time) of the calendar event nearest the onset, if within SCHEDULED_WITHIN."""
    if calendar is None or len(calendar) == 0:
        return None
    gap = (calendar["time_utc"] - onset).abs()
    k = gap.idxmin()
    if gap[k] > SCHEDULED_WITHIN:
        return None
    return str(calendar.loc[k, "event"]), calendar.loc[k, "time_utc"]


def label_all(feats: dict[str, pd.DataFrame], calendar: pd.DataFrame | None = None) -> pd.DataFrame:
    """`calendar` defaults to contracts/calendar.csv (pass an empty frame for none)."""
    if calendar is None:
        from .detector import load_calendar
        calendar = load_calendar()
    rows = [s for pair in feats for s in find_storms(feats[pair], pair)]
    for r in rows:
        ev = scheduled_event(r["onset_utc"], calendar)
        r["kind"] = "unscheduled" if ev is None else "scheduled"
        r["event"] = "" if ev is None else ev[0]
        r["event_utc"] = pd.NaT if ev is None else ev[1]
    df = pd.DataFrame(rows, columns=[c for c in STORM_COLUMNS if c != "storm_id"])
    df["event_utc"] = pd.to_datetime(df["event_utc"], utc=True)
    df = df.sort_values(["onset_utc", "pair"]).reset_index(drop=True)
    base = df["pair"].str.lower() + "-" + df["onset_utc"].dt.strftime("%Y-%m-%d")
    nth = base.groupby(base).cumcount()
    df.insert(0, "storm_id", np.where(nth == 0, base, base + "-" + (nth + 1).astype(str)))
    return df


def write_storms(storms: pd.DataFrame, path: Path = PROCESSED_DIR / "storms.csv") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = storms.copy()
    for col in ("onset_utc", "trough_utc", "end_utc", "event_utc"):
        out[col] = out[col].dt.strftime("%Y-%m-%d %H:%M")
    out.to_csv(path, index=False)
    return path


def read_storms(path: Path = PROCESSED_DIR / "storms.csv") -> pd.DataFrame:
    df = pd.read_csv(path, keep_default_na=False, na_values={"event_utc": [""]})
    for col in ("onset_utc", "trough_utc", "end_utc", "event_utc"):
        if col in df:
            df[col] = pd.to_datetime(df[col], utc=True)
    return df


def print_storms(storms: pd.DataFrame) -> None:
    print(f"{'storm_id':22} {'pair':7} {'onset UTC':17} {'move_bp':>8} {'duration':>9}  {'kind':11} event")
    for r in storms.itertuples():
        print(
            f"{r.storm_id:22} {r.pair:7} {r.onset_utc:%Y-%m-%d %H:%M} {r.move_bp:8.1f} {r.duration_min:6d} min"
            f"  {r.kind:11} {r.event}"
        )
    print(f"{len(storms)} storms")


def main() -> None:
    storms = label_all(build_features(PROCESSED_DIR, PAIRS))
    path = write_storms(storms)
    print_storms(storms)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
