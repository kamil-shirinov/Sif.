"""Per-pair, per-minute storm features from spot bars.

Columns (indexed by UTC timestamp):
  open, high, low, mid    one-minute OHLC of the mid (mid = close_mid)
  ret_bp                  simple one-minute return of mid in basis points; undefined
                          (NaN) when the previous bar is more than 5 minutes earlier,
                          so a weekend or outage gap never counts as a one-minute move
  sd_24h                  sd of ret_bp over the trailing 1,440 bars, excluding the
                          current bar so a jump cannot dampen its own z-score
  z                       ret_bp / sd_24h
  vol_ratio               5-minute realised sd (root mean square of ret_bp, so a
                          one-way slide counts as volatile) / sd_24h
  spread_bp               (close_ask - close_bid) / close_mid in basis points
  spread_ratio            spread_bp / trailing 1,440-bar median of spread_bp
  jump                    1 when |z| >= 6
  usd_z                   z signed so positive means USD up (EURUSD inverted)
  comove                  number of pairs with |usd_z| >= 3 in the same direction
                          that minute (the larger of the up and down counts)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .paths import PROCESSED_DIR

PAIRS = ("EURUSD", "USDJPY", "USDSGD")
USD_SIGN = {"EURUSD": -1, "USDJPY": 1, "USDSGD": 1}

WINDOW_24H = 1440
MIN_PERIODS_24H = 720
REALISED_WINDOW = 5
MAX_RET_GAP = pd.Timedelta(minutes=5)
JUMP_Z = 6.0
COMOVE_Z = 3.0


def load_spot(pair: str, processed_dir: Path = PROCESSED_DIR) -> pd.DataFrame:
    path = processed_dir / f"{pair}_SPOT.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run `python -m storm.ingest` first")
    return pd.read_parquet(path)


def usd_sign(pair: str) -> int:
    if pair in USD_SIGN:
        return USD_SIGN[pair]
    if pair.startswith("USD"):
        return 1
    if pair.endswith("USD"):
        return -1
    raise ValueError(f"{pair} has no USD leg")


def pair_features(spot: pd.DataFrame, pair: str) -> pd.DataFrame:
    """Features for one pair from its spot frame (columns as written by storm.ingest)."""
    df = spot.sort_values("timestamp").set_index("timestamp")
    out = pd.DataFrame(index=df.index)
    out["open"] = df["open_mid"]
    out["high"] = df["high_mid"]
    out["low"] = df["low_mid"]
    out["mid"] = df["close_mid"]

    ret = (out["mid"] / out["mid"].shift(1) - 1.0) * 1e4
    dt = out.index.to_series().diff()
    ret[dt > MAX_RET_GAP] = np.nan
    out["ret_bp"] = ret

    sd = ret.rolling(WINDOW_24H, min_periods=MIN_PERIODS_24H).std().shift(1)
    sd = sd.where(sd > 0)
    out["sd_24h"] = sd
    out["z"] = ret / sd
    rv = (ret**2).rolling(REALISED_WINDOW, min_periods=3).mean() ** 0.5
    out["vol_ratio"] = rv / sd

    spread = (df["close_ask"] - df["close_bid"]) / df["close_mid"] * 1e4
    out["spread_bp"] = spread
    med = spread.rolling(WINDOW_24H, min_periods=MIN_PERIODS_24H).median().shift(1)
    out["spread_ratio"] = spread / med.where(med > 0)

    out["jump"] = (out["z"].abs() >= JUMP_Z).astype(int)
    out["usd_z"] = out["z"] * usd_sign(pair)
    return out


def add_comove(feats: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Add the cross-pair `comove` count to every pair's frame (in place, also returned)."""
    usd_z = pd.concat({p: f["usd_z"] for p, f in feats.items()}, axis=1)
    up = (usd_z >= COMOVE_Z).sum(axis=1)
    down = (usd_z <= -COMOVE_Z).sum(axis=1)
    comove = np.maximum(up, down)
    for f in feats.values():
        f["comove"] = comove.reindex(f.index).astype(int)
    return feats


def build_features(
    processed_dir: Path = PROCESSED_DIR, pairs: tuple[str, ...] = PAIRS
) -> dict[str, pd.DataFrame]:
    feats = {p: pair_features(load_spot(p, processed_dir), p) for p in pairs}
    return add_comove(feats)


def main() -> None:
    feats = build_features()
    for pair, f in feats.items():
        path = PROCESSED_DIR / f"{pair}_features.parquet"
        f.to_parquet(path)
        print(f"{pair}: {len(f)} rows, {int(f['jump'].sum())} jumps -> {path}")


if __name__ == "__main__":
    main()
