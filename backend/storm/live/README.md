# Live API on Tiger Data

SGX's 1-minute bars in TimescaleDB (Tiger Data) behind a small FastAPI app. Contract: `contracts/api.md`.

## Start the API for the demo

```
cd backend && ~/.venvs/stormscore/bin/python -m uvicorn storm.live.api:app --port 8000
```

The web app reaches it through the Vite proxy at `/api` and works without it. Needs `TIGER_DATABASE_URL` in the repo's `.env` (never printed or committed).

## Load the data (once, or to rebuild)

```
cd backend && ~/.venvs/stormscore/bin/python -m storm.live.tiger --load
```

Reads `data/processed` (run `python -m storm.ingest` first). It drops and recreates only its own objects (`spot_1m`, `forward_1m`, `storms`, `candles_5m`, `vol_1h`), loads with COPY, refreshes the continuous aggregates, then prints row counts and size before and after compression. About a minute. If it ever passes 15 minutes (`--time-budget-min`) it stops after spot and the forward series already in, and says so.

## What is in Tiger

| Object | What |
| --- | --- |
| `spot_1m` hypertable | EURUSD, USDJPY, USDSGD: OHLC bid/ask/mid, plus `ret_1m` (log return of close mid, NULL across gaps over 5 min) |
| `forward_1m` hypertable | per pair and tenor: close mid, forward points, all-in price |
| `candles_5m` continuous aggregate | first/max/min/last mid per symbol per 5 minutes; serves `/api/candles` |
| `vol_1h` continuous aggregate | realised volatility per hour, bp: sqrt of summed squared 1-minute returns |
| `storms` table | the storm list from `data/processed/storms.csv` |

Both hypertables use 7-day chunks, compress by series (`symbol`, plus `tenor` for forwards) and have a 7-day compression policy. The loader compresses every chunk by hand before installing the policies, so the policy never races it.

## Notes

- `query_ms` in `/api/candles` is measured around the database call only and includes the network round trip to Tiger.
- `/api/candles` accepts up to 14 days per request; `symbol` must be one of the three pairs. Times are ISO 8601; no zone means UTC.
- `/api/stats` row counts and sizes are cached for 60 s. `bytes_before` and `bytes_after` come from TimescaleDB's own compression statistics (tables and indexes).
- `/api/health` reports `tiger: false` instead of failing when the database is unreachable; data endpoints then answer 503.
- Tests: `python -m pytest -q tests/live`. The live test is read-only and skips without `.env` or an unloaded database.
