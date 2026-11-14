"""Synthetic SGX-shaped spot data for tests (no real prices)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

START = {"EURUSD": 1.15, "USDJPY": 160.0, "USDSGD": 1.29}
AUGUST = pd.Timestamp("2026-08-01", tz="UTC")


def spot_frame(pair: str, seed: int, storms: list[tuple[str, float]], start="2026-07-01 00:01",
               end="2026-08-31 23:59", sd_bp: float = 1.0) -> pd.DataFrame:
    """One-minute bars: a seeded random walk plus, for each (UTC time, move_bp), a storm
    spread over its first 3 minutes."""
    ts = pd.date_range(start, end, freq="min", tz="UTC")
    rng = np.random.default_rng(seed)
    ret = rng.normal(0.0, sd_bp, len(ts))
    for when, move in storms:
        k = ts.get_loc(pd.Timestamp(when, tz="UTC"))
        ret[k:k + 3] += move / 3
    mid = START[pair] * np.exp(np.cumsum(ret) / 1e4)
    half = mid * 0.2e-4
    prev = np.concatenate([[mid[0]], mid[:-1]])
    df = pd.DataFrame({"timestamp": ts, "settlement_date": ts.normalize() + pd.Timedelta(days=2)})
    for name, arr in (("open", prev), ("high", np.maximum(prev, mid)), ("low", np.minimum(prev, mid)),
                      ("close", mid)):
        df[f"{name}_bid"] = arr - half
        df[f"{name}_ask"] = arr + half
        df[f"{name}_mid"] = arr
    return df


STORMS = {
    "USDJPY": [("2026-07-20 12:30", -60.0), ("2026-08-20 12:30", -60.0)],
    "EURUSD": [("2026-07-20 12:30", 60.0), ("2026-08-12 09:00", -50.0)],
    "USDSGD": [("2026-07-20 12:30", -45.0)],
}


def write_spot(processed: Path, poison_august: bool = False) -> Path:
    """Write <PAIR>_SPOT.parquet for the three pairs. poison_august replaces every August
    row with wild prices and extra storms, so any August leak changes results."""
    processed.mkdir(parents=True, exist_ok=True)
    for k, (pair, storms) in enumerate(STORMS.items()):
        df = spot_frame(pair, seed=k, storms=storms)
        if poison_august:
            bad = spot_frame(pair, seed=100 + k, sd_bp=25.0,
                             storms=[("2026-08-05 10:00", -400.0), ("2026-08-25 15:00", 400.0)])
            aug = df["timestamp"] >= AUGUST
            df.loc[aug, df.columns[2:]] = bad.loc[aug, bad.columns[2:]].to_numpy() * 3.0
        df.to_parquet(processed / f"{pair}_SPOT.parquet", index=False)
    return processed
