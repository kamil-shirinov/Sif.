"""Load every acquired Yahoo bar without replacing existing Tiger data."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import time

import pandas as pd

from storm import equity
from storm.ai import llm
from storm.live.db import connect, scrub

from .protocol import DATA, DOCS, check_frozen, save, sha256

COLUMNS = "ts, symbol, open, high, low, close, volume, session, bad_print"
QUERY = """SELECT bucket, symbol, open, high, low, close, volume, bars
FROM equity_5m WHERE symbol = %s AND bucket >= %s AND bucket < %s ORDER BY bucket"""


def load(data: Path = DATA) -> dict:
    check_frozen()
    llm.load_environment()  # existing helper reads configured .env, never renders it
    manifest = json.loads((data / "acquisition.json").read_text())
    started = time.perf_counter()
    result = {"started_at_utc": datetime.now(timezone.utc).isoformat(), "status": "running",
              "hypertable": "equity_1m", "continuous_aggregate": "equity_5m", "bucket_minutes": 5,
              "compression_policy_after_days": 7, "loaded_rows": {}, "sample_query": QUERY}
    with connect(autocommit=True, timeout=30) as conn, conn.cursor() as cur:
        cur.execute("SET statement_timeout = '120s'")
        cur.execute("SELECT extversion FROM pg_extension WHERE extname='timescaledb'")
        result["timescaledb_version"] = cur.fetchone()[0]
        cur.execute("""CREATE TABLE IF NOT EXISTS equity_1m (
            ts timestamptz NOT NULL, symbol text NOT NULL,
            open double precision NOT NULL, high double precision NOT NULL,
            low double precision NOT NULL, close double precision NOT NULL,
            volume double precision NOT NULL, session bigint NOT NULL, bad_print smallint NOT NULL,
            PRIMARY KEY (symbol, ts))""")
        cur.execute("SELECT create_hypertable('equity_1m','ts',chunk_time_interval=>INTERVAL '7 days',if_not_exists=>TRUE)")
        cur.execute("CREATE TEMP TABLE equity_chips_stage (LIKE equity_1m INCLUDING DEFAULTS)")
        for sym, info in manifest["tickers"].items():
            if info["status"] != "acquired":
                continue
            path = data / info["file"]
            if sha256(path) != info["sha256"]:
                raise ValueError(f"Acquisition hash changed: {sym}")
            frame = pd.read_parquet(path).set_index("timestamp").sort_index()
            bad = set(equity.bad_prints(frame))
            session = equity.session_ids(frame.index)
            with cur.copy(f"COPY equity_chips_stage ({COLUMNS}) FROM STDIN") as copy:
                for i, (ts, row) in enumerate(frame.iterrows()):
                    copy.write_row((ts.to_pydatetime(), sym, float(row.open), float(row.high), float(row.low),
                                    float(row.close), float(row.volume), int(session[i]), int(ts in bad)))
            result["loaded_rows"][sym] = len(frame)
        cur.execute("""SELECT count(*) FROM equity_chips_stage s JOIN equity_1m e USING(symbol,ts)
            WHERE ROW(e.open,e.high,e.low,e.close,e.volume,e.session,e.bad_print)
                IS DISTINCT FROM ROW(s.open,s.high,s.low,s.close,s.volume,s.session,s.bad_print)""")
        if cur.fetchone()[0]:
            raise ValueError("Existing equity bars conflict with snapshot; refusing replacement")
        cur.execute(f"INSERT INTO equity_1m ({COLUMNS}) SELECT {COLUMNS} FROM equity_chips_stage ON CONFLICT DO NOTHING")
        result["inserted_rows"] = cur.rowcount
        cur.execute("SELECT count(*) FROM equity_chips_stage s JOIN equity_1m e USING(symbol,ts)")
        result["verified_snapshot_rows"] = cur.fetchone()[0]
        assert result["verified_snapshot_rows"] == sum(result["loaded_rows"].values())
        cur.execute("SELECT symbol,count(*) FROM equity_1m GROUP BY symbol ORDER BY symbol")
        result["database_rows_per_ticker"] = dict(cur.fetchall())
        cur.execute("""CREATE MATERIALIZED VIEW IF NOT EXISTS equity_5m
            WITH (timescaledb.continuous) AS
            SELECT time_bucket(INTERVAL '5 minutes',ts) AS bucket, symbol,
                first(open,ts) AS open, max(high) AS high, min(low) AS low,
                last(close,ts) AS close, sum(volume) AS volume, count(*) AS bars,
                sum(bad_print) AS bad_prints
            FROM equity_1m GROUP BY bucket,symbol WITH NO DATA""")
        cur.execute("CALL refresh_continuous_aggregate('equity_5m',NULL,NULL)")
        cur.execute("SELECT add_continuous_aggregate_policy('equity_5m',start_offset=>INTERVAL '31 days',end_offset=>INTERVAL '5 minutes',schedule_interval=>INTERVAL '5 minutes',if_not_exists=>TRUE)")
        cur.execute("SELECT count(*) FROM equity_5m")
        result["aggregate_rows"] = cur.fetchone()[0]
        cur.execute("ALTER TABLE equity_1m SET (timescaledb.compress,timescaledb.compress_segmentby='symbol',timescaledb.compress_orderby='ts')")
        cur.execute("SELECT show_chunks('equity_1m')::text")
        chunks = [r[0] for r in cur.fetchall()]
        for chunk in chunks:
            cur.execute("SELECT compress_chunk(%s::regclass,if_not_compressed=>TRUE)", (chunk,))
        cur.execute("SELECT add_compression_policy('equity_1m',INTERVAL '7 days',if_not_exists=>TRUE)")
        cur.execute("""SELECT total_chunks,number_compressed_chunks,before_compression_total_bytes,
            after_compression_total_bytes FROM hypertable_compression_stats('equity_1m')""")
        total, compressed, before, after = cur.fetchone()
        result.update(total_chunks=total, compressed_chunks=compressed,
                      bytes_before_compression=before, bytes_after_compression=after,
                      compression_ratio=float(before / after) if after else None)
        cur.execute("SELECT min(ts),max(ts) FROM equity_chips_stage WHERE symbol='NVDA'")
        first, last = cur.fetchone()
        sample_start = pd.Timestamp(last).normalize()
        before_query = time.perf_counter()
        cur.execute(QUERY, ("NVDA", sample_start.to_pydatetime(),
                            (sample_start + pd.Timedelta(days=1)).to_pydatetime()))
        rows = cur.fetchall()
        result.update(sample_query_ms=(time.perf_counter() - before_query) * 1000,
                      sample_query_rows=len(rows), sample_query_timing="client wall time, one execution; includes network",
                      sample_query_params={"symbol": "NVDA", "start_utc": str(sample_start),
                                           "end_utc": str(sample_start + pd.Timedelta(days=1))})
    result.update(status="complete", elapsed_s=time.perf_counter() - started,
                  completed_at_utc=datetime.now(timezone.utc).isoformat())
    save(DOCS / "tiger.json", result)
    return result


if __name__ == "__main__":
    try:
        print(json.dumps(load(), indent=2))
    except Exception as error:
        save(DOCS / "tiger.json", {"status": "failed", "error_type": type(error).__name__, "error": scrub(error)})
        print(f"Tiger failed: {type(error).__name__}: {scrub(error)}")
        raise SystemExit(1)
