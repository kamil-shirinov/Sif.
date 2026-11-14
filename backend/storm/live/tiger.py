"""Load SGX's data into Tiger Data (TimescaleDB).

    python -m storm.live.tiger --load [--time-budget-min 15]

Reads data/processed (run `python -m storm.ingest` first), then in one run:
  1. drops and recreates this tool's own tables (spot_1m, forward_1m, storms, candles_5m,
     vol_1h) so the command can be repeated;
  2. COPYs spot_1m (EURUSD, USDJPY, USDSGD: OHLC bid/ask/mid) and forward_1m (close mid,
     forward points, all-in price for every tenor) in batches;
  3. loads the storm list from data/processed/storms.csv into `storms`;
  4. creates the continuous aggregates candles_5m and vol_1h and refreshes them;
  5. prints row counts and size, compresses every chunk, prints size again.

Compression policies (7 days) are installed too, so new data would compress on its own.
If the load passes the time budget (default 15 minutes) it stops after the spot table and
whichever forward series are already in, and says so.
Tiger's URL comes from TIGER_DATABASE_URL in .env and is never printed.
"""
from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

from ..features import PAIRS
from ..ingest import MAX_GAP
from ..paths import PROCESSED_DIR
from . import sql
from .db import TigerConfigError, connect, scrub

BATCH_ROWS = 50_000
TENORS = ["1W", "2W", "3W", "1M", "2M", "3M", "6M", "9M", "1Y"]
SPOT_PRICE_COLUMNS = [c for c in sql.SPOT_COLUMNS if c.split("_")[0] in ("open", "high", "low", "close")]


def add_returns(df: pd.DataFrame) -> pd.Series:
    """One-minute log return of close_mid; NULL across a gap longer than five minutes."""
    ts = df["timestamp"]
    ret = np.log(df["close_mid"]).diff()
    ret[ts.diff() > MAX_GAP] = np.nan
    return ret


def spot_frame(pair: str, processed: Path = PROCESSED_DIR) -> pd.DataFrame:
    """One pair's spot bars shaped for spot_1m (column order = sql.SPOT_COLUMNS)."""
    raw = pd.read_parquet(processed / f"{pair}_SPOT.parquet").sort_values("timestamp").reset_index(drop=True)
    out = pd.DataFrame({"ts": raw["timestamp"], "symbol": pair, "settlement_date": raw["settlement_date"].dt.date})
    for col in SPOT_PRICE_COLUMNS:
        out[col] = raw[col]
    out["ret_1m"] = add_returns(raw)
    return out[sql.SPOT_COLUMNS]


def forward_frame(pair: str, tenor: str, processed: Path = PROCESSED_DIR) -> pd.DataFrame:
    raw = pd.read_parquet(processed / f"{pair}_{tenor}.parquet").sort_values("timestamp")
    return pd.DataFrame({
        "ts": raw["timestamp"], "symbol": pair, "tenor": tenor,
        "settlement_date": raw["settlement_date"].dt.date,
        "close_mid": raw["close_mid"], "close_fp": raw["close_mid_fp"], "close_all_in": raw["close_mid_all_in"],
    })[sql.FORWARD_COLUMNS]


def storms_frame(processed: Path = PROCESSED_DIR) -> pd.DataFrame:
    raw = pd.read_csv(processed / "storms.csv")

    def utc(col: str) -> pd.Series:
        return pd.to_datetime(raw[col], utc=True)

    return pd.DataFrame({
        "storm_id": raw["storm_id"], "symbol": raw["pair"],
        "onset": utc("onset_utc"), "trough": utc("trough_utc"), "storm_end": utc("end_utc"),
        "move_bp": raw["move_bp"], "usd_move_bp": raw["usd_move_bp"],
        "duration_min": raw["duration_min"].astype("Int64"),
        "kind": raw["kind"], "event": raw["event"],
        "event_time": pd.to_datetime(raw["event_utc"], utc=True),
    })[sql.STORM_COLUMNS]


def copy_frame(cur: psycopg.Cursor, table: str, df: pd.DataFrame, batch: int = BATCH_ROWS) -> int:
    """COPY a frame in CSV batches (NaN/NaT become NULL). Returns rows written."""
    columns = list(df.columns)
    for start in range(0, len(df), batch):
        buf = io.StringIO()
        df.iloc[start:start + batch].to_csv(buf, header=False, index=False, date_format="%Y-%m-%d %H:%M:%S%z")
        with cur.copy(sql.copy_statement(table, columns)) as copy:
            copy.write(buf.getvalue().encode())
    return len(df)


def _fmt_bytes(n: int) -> str:
    return f"{n / 1e6:,.1f} MB"


def _scalar(cur: psycopg.Cursor, statement: str):
    cur.execute(statement)
    return cur.fetchone()[0]


def sizes(cur: psycopg.Cursor) -> dict[str, int]:
    return {t: int(_scalar(cur, sql.size_statement(t))) for t in sql.HYPERTABLES}


def counts(cur: psycopg.Cursor) -> dict[str, int]:
    return {t: int(_scalar(cur, sql.count_statement(t))) for t in (*sql.HYPERTABLES, sql.STORMS_TABLE)}


def load(budget_min: float = 15.0, processed: Path = PROCESSED_DIR) -> dict:
    started = time.monotonic()
    deadline = started + budget_min * 60
    missing = [f"{p}_SPOT" for p in PAIRS if not (processed / f"{p}_SPOT.parquet").exists()]
    if missing:
        raise FileNotFoundError(f"{processed} lacks {missing}; run `python -m storm.ingest` first")

    result: dict = {"forward_complete": True, "forward_series_loaded": 0}
    with connect(autocommit=True, timeout=30) as conn, conn.cursor() as cur:
        for statement in [*sql.drop_statements(), *sql.table_statements()]:
            cur.execute(statement)
        print("schema created (hypertables spot_1m, forward_1m; table storms)")

        for pair in PAIRS:
            frame = spot_frame(pair, processed)
            copy_frame(cur, sql.SPOT_TABLE, frame)
            print(f"  spot_1m   {pair}: {len(frame):>7,} rows  [{time.monotonic() - started:5.0f}s]")

        series = [(p, t) for p in PAIRS for t in TENORS if (processed / f"{p}_{t}.parquet").exists()]
        for pair, tenor in series:
            if time.monotonic() > deadline:
                result["forward_complete"] = False
                print(f"time budget of {budget_min:g} min reached: stopping the forward load")
                break
            frame = forward_frame(pair, tenor, processed)
            copy_frame(cur, sql.FORWARD_TABLE, frame)
            result["forward_series_loaded"] += 1
            print(f"  forward_1m {pair} {tenor:>2}: {len(frame):>7,} rows  [{time.monotonic() - started:5.0f}s]")
        result["forward_series_expected"] = len(series)

        storms = storms_frame(processed)
        copy_frame(cur, sql.STORMS_TABLE, storms)
        print(f"  storms: {len(storms)} rows")

        for statement in sql.aggregate_statements():
            cur.execute(statement)
        for statement in sql.refresh_statements():
            cur.execute(statement)
        print("continuous aggregates candles_5m and vol_1h created and refreshed")

        result["rows"] = counts(cur)
        result["bytes_before"] = sizes(cur)
        print("\nrows:", {k: f"{v:,}" for k, v in result["rows"].items()})
        print("size before compression:", {k: _fmt_bytes(v) for k, v in result["bytes_before"].items()})

        # Compress by hand first and install the policies afterwards: a policy added to
        # old data fires at once and would race this loop.
        for statement in sql.compression_settings_statements():
            cur.execute(statement)
        for table in sql.HYPERTABLES:
            cur.execute(sql.list_chunks_statement(table))
            for (chunk,) in cur.fetchall():
                cur.execute(sql.compress_chunk_statement(), (chunk,))
        for statement in sql.compression_policy_statements():
            cur.execute(statement)
        result["bytes_after"] = sizes(cur)
        print("size after compression: ", {k: _fmt_bytes(v) for k, v in result["bytes_after"].items()})
        before, after = sum(result["bytes_before"].values()), sum(result["bytes_after"].values())
        result["compression_ratio"] = before / after if after else None
        print(f"total {_fmt_bytes(before)} -> {_fmt_bytes(after)}  (ratio {result['compression_ratio']:.1f}x)")
        result["elapsed_s"] = round(time.monotonic() - started, 1)
        if not result["forward_complete"]:
            print(f"NOTE: forward_1m is partial ({result['forward_series_loaded']} of "
                  f"{result['forward_series_expected']} series).")
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--load", action="store_true", help="(re)create the schema and load everything")
    ap.add_argument("--time-budget-min", type=float, default=15.0)
    args = ap.parse_args(argv)
    if not args.load:
        ap.print_help()
        return 2
    try:
        load(args.time_budget_min)
    except (TigerConfigError, FileNotFoundError) as error:
        print(f"error: {scrub(error)}", file=sys.stderr)
        return 1
    except psycopg.Error as error:
        print(f"database error ({type(error).__name__}): {scrub(error)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
