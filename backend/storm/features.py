"""Per-pair, per-minute storm features from spot bars.

Columns (indexed by UTC timestamp):
  open, high, low, mid    one-minute OHLC of the mid (mid = close_mid)
  ret_bp                  simple one-minute return of mid in basis points; undefined
                          (NaN) unless the previous bar is exactly one minute earlier, so
                          no gap (a missing minute, an outage, a weekend) ever counts as a
                          one-minute move, and (when the bars carry a `session` id, as
                          equities do) when it is in another session: no return crosses a
                          closed market
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
  open_bid, open_ask,     the bar's quotes, passed through when the bars carry them (SGX
  close_bid, close_ask    spot does): trades fill at bid or ask, never at mid

Bad prints (optional `bad_print` column, 1 on a bar flagged as a one-minute print the
market did not trade through) are handled causally. At the flagged minute itself the bar
is visible like any other: its return, z and jump use the history before it, so it can
alarm (or count as a false alarm). From the next bar on, once the reversal has been seen,
it is excluded: later returns, the trailing sd and spread median, and the realised
volatility are computed as if it had never printed.

The index is normalised to nanoseconds (pandas 3 parses to microseconds by default).

The rolling windows count bars, not clock minutes, so volatility is measured over
trading minutes only. bar_features() is the generic core (storm.equity uses it too).
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
RET_STEP = pd.Timedelta(minutes=1)
JUMP_Z = 6.0
COMOVE_Z = 3.0
QUOTE_COLUMNS = ("open_bid", "open_ask", "close_bid", "close_ask")


def as_ns(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """The same instants at nanosecond resolution, whatever unit pandas parsed them at."""
    return pd.DatetimeIndex(idx).as_unit("ns")


def epoch_minutes(idx: pd.DatetimeIndex) -> np.ndarray:
    """Whole minutes since the Unix epoch, independent of the index's time unit."""
    return as_ns(idx).asi8 // 60_000_000_000


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


def bar_features(bars: pd.DataFrame) -> pd.DataFrame:
    """Features from one-minute bars indexed by UTC timestamp: columns open, high, low, mid,
    and optionally spread_bp (NaN when the data has no quotes), session (an int id per
    trading session; a return never crosses a change of session), the bid/ask quotes in
    QUOTE_COLUMNS, and bad_print (see the module doc)."""
    bars = bars.sort_index()
    bars = bars.set_axis(as_ns(bars.index), axis=0)
    bad = bars["bad_print"].astype(bool) if "bad_print" in bars else None
    if bad is None or not bad.any():
        out = _bar_features(bars)
        if bad is not None:
            out["bad_print"] = 0
        return out
    # Causal: every bar after a bad print sees the history without it; the bad bar itself
    # sees the history before it, plus itself.
    out = _bar_features(bars[~bad]).reindex(bars.index)
    for t in bars.index[bad]:
        keep = ~bad | (bars.index == t)
        out.loc[t] = _bar_features(bars[keep].loc[:t]).loc[t]
    out["bad_print"] = bad.astype(int)
    out["jump"] = out["jump"].astype(int)
    if "session" in out:
        out["session"] = out["session"].astype("int64")
    return out


def _bar_features(bars: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=bars.index)
    for col in ("open", "high", "low", "mid"):
        out[col] = bars[col].astype(float)
    for col in QUOTE_COLUMNS:
        if col in bars:
            out[col] = bars[col].astype(float)

    ret = (out["mid"] / out["mid"].shift(1) - 1.0) * 1e4
    dt = out.index.to_series().diff()
    ret[dt != RET_STEP] = np.nan
    if "session" in bars:
        out["session"] = bars["session"].astype("int64")
        ret[out["session"].diff().fillna(0) != 0] = np.nan
    ret.iloc[:1] = np.nan
    out["ret_bp"] = ret

    sd = ret.rolling(WINDOW_24H, min_periods=MIN_PERIODS_24H).std().shift(1)
    sd = sd.where(sd > 0)
    out["sd_24h"] = sd
    out["z"] = ret / sd
    rv = (ret**2).rolling(REALISED_WINDOW, min_periods=3).mean() ** 0.5
    out["vol_ratio"] = rv / sd

    spread = bars["spread_bp"].astype(float) if "spread_bp" in bars else pd.Series(np.nan, index=bars.index)
    out["spread_bp"] = spread
    med = spread.rolling(WINDOW_24H, min_periods=MIN_PERIODS_24H).median().shift(1)
    out["spread_ratio"] = spread / med.where(med > 0)

    out["jump"] = (out["z"].abs() >= JUMP_Z).astype(int)
    return out


def pair_features(spot: pd.DataFrame, pair: str) -> pd.DataFrame:
    """Features for one pair from its spot frame (columns as written by storm.ingest)."""
    df = spot.sort_values("timestamp").set_index("timestamp")
    bars = pd.DataFrame({
        "open": df["open_mid"], "high": df["high_mid"], "low": df["low_mid"], "mid": df["close_mid"],
        "spread_bp": (df["close_ask"] - df["close_bid"]) / df["close_mid"] * 1e4,
        **{c: df[c] for c in QUOTE_COLUMNS},
    }, index=df.index)
    out = bar_features(bars)
    out["usd_z"] = out["z"] * usd_sign(pair)
    return out


def add_comove(feats: dict[str, pd.DataFrame], col: str = "usd_z",
               among: tuple[str, ...] | None = None) -> dict[str, pd.DataFrame]:
    """Add the cross-market `comove` count to every frame (in place, also returned): how many
    of the markets in `among` (default all) have |col| >= COMOVE_Z the same way that minute."""
    among = tuple(feats) if among is None else among
    zs = pd.concat({p: feats[p][col] for p in among}, axis=1)
    up = (zs >= COMOVE_Z).sum(axis=1)
    down = (zs <= -COMOVE_Z).sum(axis=1)
    comove = np.maximum(up, down)
    for f in feats.values():
        f["comove"] = comove.reindex(f.index).fillna(0).astype(int)
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
