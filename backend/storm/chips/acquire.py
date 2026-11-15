"""Download once after registration; no detector evaluation in this module."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.metadata
import json
import logging
from pathlib import Path
import time

import pandas as pd

from .protocol import DATA, check_frozen, registration_commit, save, sha256


def requests(spec: dict) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    cfg = spec["acquisition"]
    end = pd.Timestamp(cfg["end_date_exclusive"], tz="America/New_York")
    oldest = end - pd.DateOffset(days=cfg["lookback_calendar_days"])
    ranges = []
    while end > oldest:
        start = max(oldest, end - pd.DateOffset(days=cfg["max_request_calendar_days"]))
        ranges.append((start, end))
        end = start
    return ranges


def acquire(out: Path = DATA) -> dict:
    import yfinance as yf

    spec = check_frozen()
    marker = out / "acquisition.json"
    if marker.exists():
        raise FileExistsError("Acquisition is immutable; use the existing snapshot")
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
                "registration_commit": registration_commit(), "tickers": {},
                "versions": {p: importlib.metadata.version(p) for p in
                             ("yfinance", "pandas", "numpy", "pyarrow")}}
    save(marker, manifest)  # claim the run before the first network request
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    for sym in spec["tickers"]:
        frames, attempts = [], []
        for lo, hi in requests(spec):
            for retry in range(2):
                before = time.perf_counter()
                row = {"start_et": str(lo.date()), "end_et_exclusive": str(hi.date()), "attempt": retry + 1}
                try:
                    df = yf.Ticker(sym).history(start=str(lo.date()), end=str(hi.date()), interval="1m",
                                                prepost=True, auto_adjust=False, actions=False,
                                                raise_errors=True, timeout=30)
                    row.update(rows=len(df), status="ok" if len(df) else "empty")
                    if not df.empty:
                        df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
                        df.index = df.index.tz_convert("UTC")
                        frames.append(df.rename_axis("timestamp").reset_index())
                except Exception as error:
                    # Yahoo errors contain symbol/range/status, not credentials. Do not retain URLs.
                    msg = str(error)
                    row.update(status="error", error_type=type(error).__name__,
                               error=msg if "://" not in msg else type(error).__name__)
                row["elapsed_s"] = time.perf_counter() - before
                attempts.append(row)
                # Retention/parameter refusals are definitive, not transport errors.
                if row["status"] != "error" or row.get("error_type") in {
                    "YFPricesMissingError", "YFInvalidPeriodError"}:
                    break
                if retry == 0:
                    time.sleep(1)
        entry = {"requests": attempts, "status": "unavailable", "rows": 0}
        if frames:
            raw = pd.concat(frames, ignore_index=True).sort_values("timestamp")
            duplicates = raw[raw.duplicated("timestamp", keep=False)]
            if len(duplicates) and duplicates.groupby("timestamp").nunique().max().max() > 1:
                raise ValueError(f"Conflicting overlapping Yahoo bars for {sym}")
            raw = raw.drop_duplicates("timestamp").reset_index(drop=True)
            if raw[["open", "high", "low", "close"]].isna().any().any():
                raise ValueError(f"Missing OHLC for {sym}; keep snapshot for investigation")
            path = out / f"{sym}_1m.parquet"
            raw.to_parquet(path, index=False)
            entry.update(status="acquired", rows=len(raw), file=path.name, sha256=sha256(path),
                         first_utc=str(raw.timestamp.min()), last_utc=str(raw.timestamp.max()))
        manifest["tickers"][sym] = entry
        save(marker, manifest)
        print(f"{sym}: {entry['status']}, {entry['rows']} bars", flush=True)
    manifest["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    save(marker, manifest)
    return manifest


if __name__ == "__main__":
    acquire()
