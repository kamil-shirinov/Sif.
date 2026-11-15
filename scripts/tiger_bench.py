#!/usr/bin/env python
"""Tiger Data evidence: candle-query timings (raw hypertable vs continuous aggregate) and sizes.

    cd backend && python ../scripts/tiger_bench.py [--runs 20] [--out ../docs/tiger_bench.json]

Read-only: it only SELECTs. It uses the live package's own connection helper, so the URL comes
from .env and is never printed (error texts go through storm.live.db.scrub).

What it measures
  1. For four windows (1 hour, 1 day, 1 week, 1 month of USDJPY spot) the same 5-minute candles
     two ways: aggregated from the raw hypertable `spot_1m` with time_bucket(), and read from the
     continuous aggregate `candles_5m`. Each query runs --runs times (after one warm-up run) on one
     open connection, alternating raw and aggregate; the wall clock around execute + fetchall is
     recorded (so it includes the network round trip from this machine), plus the server-side
     "Execution Time" from EXPLAIN (ANALYZE) for the same statements. The two results are compared
     value by value before any timing is trusted.
  2. The round trip alone (SELECT 1), to read the timings against.
  3. Every hypertable's size now and its size before and after compression, from TimescaleDB's own
     statistics (hypertable_compression_stats), with chunk counts.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

from storm.live import sql  # noqa: E402
from storm.live.db import TigerConfigError, connect, scrub  # noqa: E402

SYMBOL = "USDJPY"
RAW_QUERY = f"""
SELECT extract(epoch FROM bucket)::bigint AS t, open, high, low, close FROM (
    SELECT time_bucket(INTERVAL '5 minutes', ts) AS bucket,
           first(open_mid, ts) AS open, max(high_mid) AS high, min(low_mid) AS low, last(close_mid, ts) AS close
    FROM {sql.SPOT_TABLE}
    WHERE symbol = %s AND ts >= %s AND ts < %s
    GROUP BY bucket
) c ORDER BY bucket
"""
AGG_QUERY = sql.CANDLES_QUERY

UTC = timezone.utc


def window(start: tuple, end: tuple) -> tuple[datetime, datetime]:
    return datetime(*start, tzinfo=UTC), datetime(*end, tzinfo=UTC)


WINDOWS = {
    "1 hour": window((2026, 7, 30, 13), (2026, 7, 30, 14)),
    "1 day": window((2026, 7, 30), (2026, 7, 31)),
    "1 week": window((2026, 7, 27), (2026, 8, 3)),
    "1 month": window((2026, 8, 1), (2026, 9, 1)),
}


def timed(cur, statement: str, params: tuple) -> tuple[float, list]:
    t0 = time.perf_counter()
    cur.execute(statement, params)
    rows = cur.fetchall()
    return (time.perf_counter() - t0) * 1000.0, rows


def explain_ms(cur, statement: str, params: tuple) -> tuple[float, float]:
    cur.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + statement, params)
    doc = cur.fetchone()[0]
    doc = doc[0] if isinstance(doc, list) else json.loads(doc)[0]
    return float(doc["Planning Time"]), float(doc["Execution Time"])


def summary(values: list[float]) -> dict:
    s = sorted(values)
    return {
        "median": round(statistics.median(s), 2),
        "min": round(s[0], 2),
        "p90": round(s[min(len(s) - 1, int(0.9 * len(s)))], 2),
        "max": round(s[-1], 2),
    }


def same_candles(a: list[tuple], b: list[tuple]) -> bool:
    if len(a) != len(b):
        return False
    return all(x[0] == y[0] and all(abs(float(p) - float(q)) < 1e-9 for p, q in zip(x[1:], y[1:])) for x, y in zip(a, b))


def bench_windows(cur, runs: int) -> list[dict]:
    out = []
    for name, (start, end) in WINDOWS.items():
        params = (SYMBOL, start, end)
        _, raw_rows = timed(cur, RAW_QUERY, params)  # warm-up, and the rows to compare
        _, agg_rows = timed(cur, AGG_QUERY, params)
        if not same_candles(raw_rows, agg_rows):
            raise SystemExit(f"{name}: the raw and aggregate candles differ; not timing a wrong query")
        raw_ms, agg_ms = [], []
        for _ in range(runs):  # alternate, so a slow moment hits both
            raw_ms.append(timed(cur, RAW_QUERY, params)[0])
            agg_ms.append(timed(cur, AGG_QUERY, params)[0])
        raw_srv = [explain_ms(cur, RAW_QUERY, params) for _ in range(runs)]
        agg_srv = [explain_ms(cur, AGG_QUERY, params) for _ in range(runs)]
        cur.execute(f"SELECT count(*) FROM {sql.SPOT_TABLE} WHERE symbol = %s AND ts >= %s AND ts < %s", params)
        bars = cur.fetchone()[0]
        out.append({
            "window": name,
            "from": start.isoformat(),
            "to": end.isoformat(),
            "one_minute_bars_in_window": bars,
            "candles_returned": len(raw_rows),
            "identical_results": True,
            "raw_hypertable_ms": summary(raw_ms),
            "continuous_aggregate_ms": summary(agg_ms),
            "speedup_median": round(statistics.median(raw_ms) / statistics.median(agg_ms), 2),
            "server_execution_ms_raw": summary([e for _, e in raw_srv]),
            "server_execution_ms_aggregate": summary([e for _, e in agg_srv]),
            "server_planning_ms_raw": summary([p for p, _ in raw_srv]),
            "server_planning_ms_aggregate": summary([p for p, _ in agg_srv]),
            "runs": runs,
        })
    return out


def round_trip(cur, runs: int) -> dict:
    cur.execute("SELECT 1")
    cur.fetchall()
    return summary([timed(cur, "SELECT 1", ())[0] for _ in range(runs)])


def sizes(cur) -> list[dict]:
    cur.execute("SELECT hypertable_name FROM timescaledb_information.hypertables WHERE hypertable_schema = 'public' ORDER BY 1")
    names = [r[0] for r in cur.fetchall()]
    out = []
    for name in names:
        cur.execute(f"SELECT count(*) FROM {name}")
        rows = cur.fetchone()[0]
        cur.execute("SELECT hypertable_size(%s::regclass)", (name,))
        size_now = int(cur.fetchone()[0])
        cur.execute(
            "SELECT count(*), count(*) FILTER (WHERE is_compressed) FROM timescaledb_information.chunks "
            "WHERE hypertable_schema = 'public' AND hypertable_name = %s",
            (name,),
        )
        chunks, compressed = cur.fetchone()
        cur.execute(
            "SELECT coalesce(sum(before_compression_table_bytes),0), coalesce(sum(before_compression_index_bytes),0), "
            "coalesce(sum(before_compression_toast_bytes),0), coalesce(sum(before_compression_total_bytes),0), "
            "coalesce(sum(after_compression_table_bytes),0), coalesce(sum(after_compression_index_bytes),0), "
            "coalesce(sum(after_compression_toast_bytes),0), coalesce(sum(after_compression_total_bytes),0) "
            "FROM hypertable_compression_stats(%s::regclass)",
            (name,),
        )
        b_t, b_i, b_o, b_all, a_t, a_i, a_o, a_all = (int(v) for v in cur.fetchone())
        out.append({
            "hypertable": name,
            "rows": rows,
            "chunks": chunks,
            "chunks_compressed": compressed,
            "size_now_bytes": size_now,
            "before_compression_bytes": {"table": b_t, "index": b_i, "toast": b_o, "total": b_all},
            "after_compression_bytes": {"table": a_t, "index": a_i, "toast": a_o, "total": a_all},
            "ratio": round(b_all / a_all, 2) if a_all else None,
        })
    cur.execute(
        "SELECT view_name, hypertable_name, materialized_only FROM timescaledb_information.continuous_aggregates ORDER BY 1"
    )
    aggregates = [{"view": v, "over": h, "materialized_only": m} for v, h, m in cur.fetchall()]
    for agg in aggregates:
        cur.execute(f"SELECT count(*) FROM {agg['view']}")
        agg["rows"] = cur.fetchone()[0]
    return out, aggregates


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--out", default=str(HERE.parent / "docs" / "tiger_bench.json"))
    args = ap.parse_args()
    try:
        with connect(autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
            ts_version = cur.fetchone()[0]
            cur.execute("SHOW server_version")
            pg_version = cur.fetchone()[0]
            rtt = round_trip(cur, args.runs)
            windows = bench_windows(cur, args.runs)
            hypertables, aggregates = sizes(cur)
    except TigerConfigError as e:
        print(f"tiger_bench: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # never let a URL through
        print(f"tiger_bench: {type(e).__name__}: {scrub(e)}", file=sys.stderr)
        return 1
    doc = {
        "measured_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "symbol": SYMBOL,
        "candle_bucket": "5 minutes",
        "timescaledb_version": ts_version,
        "postgres_version": pg_version,
        "method": (
            f"{args.runs} runs per query after one warm-up, alternating raw and aggregate, on one open connection from this "
            "machine; wall clock around execute + fetchall (includes the network round trip). Server times are EXPLAIN (ANALYZE) "
            f"over {args.runs} runs. Raw and aggregate results are compared value by value first."
        ),
        "round_trip_ms": rtt,
        "windows": windows,
        "hypertables": hypertables,
        "continuous_aggregates": aggregates,
    }
    Path(args.out).write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {args.out}")
    print(f"round trip (SELECT 1) median {rtt['median']} ms")
    for w in windows:
        print(
            f"{w['window']:>8}: {w['candles_returned']:>4} candles from {w['one_minute_bars_in_window']:>6} bars | raw median "
            f"{w['raw_hypertable_ms']['median']:>7} ms | aggregate median {w['continuous_aggregate_ms']['median']:>7} ms | x{w['speedup_median']}"
        )
    for h in hypertables:
        print(f"{h['hypertable']:>10}: {h['rows']:>9} rows, {h['before_compression_bytes']['total']:>11} B -> {h['after_compression_bytes']['total']:>10} B (x{h['ratio']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
