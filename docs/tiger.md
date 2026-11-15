# StormScore on Tiger Data

For the Tiger Data prize. Everything below was measured on 15 November 2026 against the live Tiger Data service (PostgreSQL 18.6, TimescaleDB 2.32.0) by [scripts/tiger_bench.py](../scripts/tiger_bench.py); the raw numbers are in [docs/tiger_bench.json](tiger_bench.json). To repeat it: `cd backend && python ../scripts/tiger_bench.py` (read-only; the database URL stays in `.env` and is never printed).

## What we used

| Tiger Data / TimescaleDB feature | Where in StormScore |
|---|---|
| **Hypertables** with 7-day chunks | `spot_1m` (EURUSD, USDJPY, USDSGD one-minute bid/ask/mid bars), `forward_1m` (every forward tenor's mid, forward points and all-in price), and `equity_1m` (one-minute bars of 14 chip tickers, for the out-of-sample chip test) |
| **Native compression**, `segmentby` the series (`symbol`, plus `tenor` for forwards), ordered by `ts` | all three hypertables; every chunk compressed, plus a 7-day compression policy so new data would compress by itself |
| **Continuous aggregates** | `candles_5m` (first, max, min, last of mid per 5 minutes: serves the chart), `vol_1h` (realised volatility per hour), `equity_5m` (the chips' 5-minute candles) |
| `time_bucket`, `first`, `last` | the candle queries, raw and aggregated |
| `hypertable_compression_stats`, `hypertable_size` | the numbers in this document, and `/api/stats` |
| `COPY` loading | `python -m storm.live.tiger --load` loads 1.85 million rows in about a minute |

Not used, and we say so: retention policies (two months of data, nothing to expire), real-time aggregates (all three views are `materialized_only`, refreshed after each load), and Tiger's AI features.

## Why

SGX's data is exactly what a time-series database is for: three pairs, ten series each (spot and nine forward tenors), one row a minute, mostly read by time range and symbol. Three things made it the right place for it.

1. **The chart reads candles, and candles are a time-bucketed aggregate.** `GET /api/candles` returns 5-minute candles from `candles_5m`; the app shows the database's own query time in the chart's corner ("Tiger Data · 21 ms") and "Live · Tiger Data" in the HUD. Without the service running, the app plays the bundles as they are: the database makes the chart live, it is not a dependency.
2. **The forward curve is the bulk of the data and it compresses well.** 1.66 million of the 1.85 million FX rows are forward bars. Compression took them from 269.0 MB to 26.9 MB.
3. **A second dataset went in without a schema change to the first.** For the chip-sector test, 14 tickers' bars went into their own hypertable and continuous aggregate in the same service (`backend/storm/chips/tiger.py`), alongside the FX tables, loaded with `CREATE TABLE IF NOT EXISTS` so it could not touch the FX data.

## Measurements

### Size before and after compression

From TimescaleDB's own statistics, per hypertable (tables, indexes and TOAST together). "Now" is `hypertable_size()` today, which also counts what the statistics leave out.

| Hypertable | Rows | Chunks (compressed / total) | Before compression | After compression | Ratio | Size now |
|---|---|---|---|---|---|---|
| `spot_1m` | 193,049 | 10 / 10 | 47,579,136 B | 16,097,280 B | 2.96 | 16,367,616 B |
| `forward_1m` | 1,661,187 | 10 / 10 | 268,984,320 B | 26,853,376 B | 10.02 | 27,123,712 B |
| `equity_1m` | 211,948 | 5 / 5 | 31,309,824 B | 5,480,448 B | 5.71 | 5,627,904 B |
| **All three** | 2,066,184 | 25 / 25 | **347,873,280 B** | **48,431,104 B** | **7.18** | 49,119,232 B |

The FX tables alone (`spot_1m` and `forward_1m`) went from 316,563,456 B to 42,950,656 B, a ratio of 7.37: the figure in the README and in [docs/tiger_stats.json](tiger_stats.json), which is the same number measured on 14 November.

Where the space went (before, then after):

| | table | index | TOAST |
|---|---|---|---|
| `spot_1m` | 31.2 MB, then 0.4 MB | 16.3 MB, then 0.2 MB | 0.08 MB, then 15.5 MB |
| `forward_1m` | 128.5 MB, then 0.9 MB | 140.4 MB, then 0.3 MB | 0.08 MB, then 25.7 MB |
| `equity_1m` | 21.6 MB, then 0.2 MB | 9.7 MB, then 0.1 MB | 0.04 MB, then 5.2 MB |

In the forward table the indexes were larger than the data (140 MB against 129 MB); compression keeps the columnar data in TOAST and shrinks the indexes to almost nothing. The spot table compresses least; we think because its price columns are noisy floating-point numbers, but we did not test that, and we did not tune `segmentby`, `orderby` or the chunk size (7 days was our first choice and we kept it). We have not tested other settings, so we do not claim these are the best ones.

The continuous aggregates hold 38,691 rows (`candles_5m`), 3,249 (`vol_1h`) and 49,817 (`equity_5m`).

### Candle queries: raw hypertable against the continuous aggregate

The same 5-minute USDJPY candles, two ways. **Raw:** `time_bucket('5 minutes', ts)` with `first`, `max`, `min`, `last` over `spot_1m`. **Aggregate:** a plain `SELECT` from `candles_5m`. Before any timing the two results were compared value by value, and they are identical for every window. Each query ran 20 times after one warm-up, alternating raw and aggregate, on one open connection from the developer's laptop to the cloud service. All the data is in compressed chunks.

Wall clock (milliseconds, median, with the fastest and the 90th-percentile run in brackets), which includes the network round trip:

| Window | Candles (from 1-minute bars) | Raw hypertable | Continuous aggregate | Speed-up |
|---|---|---|---|---|
| 1 hour (30 Jul 13:00 to 14:00 UTC) | 12 (60) | 20.4 (17.5 to 26.5) | 19.3 (17.5 to 37.8) | 1.06x |
| 1 day (30 Jul) | 288 (1,438) | 21.8 (19.9 to 28.0) | 22.0 (19.9 to 28.7) | 0.99x |
| 1 week (27 Jul to 3 Aug) | 1,465 (7,312) | 30.9 (26.2 to 36.0) | 25.4 (19.9 to 29.9) | 1.22x |
| 1 month (August) | 6,208 (30,985) | 55.9 (52.1 to 78.5) | 38.2 (30.2 to 72.2) | 1.46x |

The round trip alone (`SELECT 1`) has a median of **19.4 ms** (16.8 to 41.3). Everything up to a day is inside that: the network is the cost, and the database's choice of table is not visible. **Honest reading: for the chart's normal use (a few hours to a day of 5-minute candles), the aggregate makes no difference a user could see.** It starts to show at a week and shows clearly at a month.

The database's own time, from `EXPLAIN (ANALYZE)` over the same 20 runs (milliseconds, median), shows what the round trip hides:

| Window | Raw: planning + execution | Aggregate: planning + execution | Execution speed-up |
|---|---|---|---|
| 1 hour | 0.28 + 0.15 | 0.17 + 0.03 | 5.0x |
| 1 day | 0.28 + 0.77 | 0.22 + 0.28 | 2.8x |
| 1 week | 0.47 + 7.09 | 0.18 + 1.28 | 5.5x |
| 1 month | 0.80 + 29.56 | 0.27 + 5.42 | 5.5x |

So the continuous aggregate does three to five and a half times less work on the server, whatever the window, and the raw query's work grows with the window (decompressing and bucketing 31,000 bars for a month), while the aggregate reads 6,208 pre-made rows. On a closer network, or with many users asking at once, that is the gap that would matter. In the demo it is hidden behind a 19 ms round trip, and the 1-hour and 1-day figures at 0.03 to 0.28 ms are close to what the timer can resolve.

## What we would do with more time

- Try other `segmentby` / `orderby` / chunk settings for `spot_1m`, which compressed least.
- Make `candles_5m` a real-time aggregate and add 1-hour and 1-day aggregates stacked on it, so a month-wide chart reads hundreds of rows, not thousands.
- Load the data from a script that runs in CI, so the numbers here could be regenerated on every change.
