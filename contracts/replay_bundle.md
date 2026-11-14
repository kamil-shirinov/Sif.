# Replay bundle contract (schema_version 1)

One JSON file per storm. The backend writes it (`python -m storm.export`) and the web app plays it. Kamil owns this file: changes go through a PR to main and bump `schema_version`.

Every array in `series` has length `n` and is indexed by frame `i`. Frame time = `t0 + i * step_s` (UTC epoch seconds).

## Top level

| Key | Type | Meaning |
|---|---|---|
| schema_version | int | 1 |
| storm_id | string | e.g. `usdjpy-2026-07-30` |
| title | string | e.g. `USDJPY, 30 July 2026` |
| symbol | string | what the ship trades, e.g. `USDJPY` (any market works) |
| asset_class | string | `fx` for SGX data; `equity` or `crypto` later |
| source | string | `sgx` (SGX data) or `synthetic` |
| book_is_synthetic | bool | always `true`: the trader book is invented |
| t0 | int | UTC epoch seconds of frame 0 |
| step_s | int | 60 |
| n | int | number of frames |
| storm | object | `onset_i` (int), `trough_i` (int), `move_bp` (signed float), `kind` (`scheduled` or `unscheduled`), `label` (short text, e.g. `-2.9% in 54 min`) |
| series | object | arrays, see below |
| ships | object | `prepared` and `unprepared`, each with `label`, `start_equity_usd`, `margin_call_i` (int or null), `cut_i` (frame where it cut exposure, or null) and `cut_fraction` (0 to 1) |
| events | array | `{i, type, text}` where type is `watch`, `alarm`, `margin_call` or `all_clear`; alarms add `move_ahead_pct`; margin calls add `ship`; watch events add `at_i` (frame of the scheduled release) |
| exposure | object | `as_of_i`, `positions` (`instrument`, `side`, `notional_usd`), `net_usd_by_ccy` (object), `leverage`, `margin_buffer_pct` |
| stress | array | `{scenario, pnl_usd, margin_call}` |
| report | object or null | `text`, `verified` (bool), `unverified_numbers` (array), `model` |

## series (every array has length n)

| Key | Type | Meaning | Drives in 3D |
|---|---|---|---|
| open, high, low | float | one-minute OHLC of the mid price (close = mid) | candles on the market chart |
| mid | float | mid price (the close) | market chart, HUD price |
| spread_bp | float | ask minus bid, in basis points of mid | chart tooltip |
| vol_ratio | float | 5-minute realised volatility divided by the trailing 24 h level; 1 = normal | wave height and choppiness |
| risk | float 0 to 1 | storm risk score | sky darkness, fog, rain |
| state | int | 0 calm, 1 watch, 2 storm | HUD badge, wind, sound intensity |
| jump | int 0 or 1 | one-minute move of at least 6 times normal | lightning flash |
| prepared_equity | float | USD equity of the ship that followed the alarm | that ship's tilt and waterline |
| unprepared_equity | float | USD equity of the ship that ignored it | that ship's tilt and sinking |

Rounding: prices to 5 significant decimals, ratios to 2 decimals, equity to whole dollars.

## index.json (same folder as the bundles)

```json
{
  "schema_version": 1,
  "storms": [{"storm_id": "usdjpy-2026-07-30", "title": "USDJPY, 30 July 2026", "symbol": "USDJPY", "asset_class": "fx", "kind": "unscheduled", "move_bp": -290.4, "file": "usdjpy-2026-07-30.json"}],
  "metrics": {"split": "test: August 2026", "storms": 0, "caught": 0, "median_move_ahead_pct": null, "false_alarms_per_day": null}
}
```

`metrics` may be null until the backtest exists.

## Example

`contracts/mock_storm.json` is a complete bundle with synthetic prices, labelled `source: synthetic`. The web lane copies it to `web/public/bundles/mock_storm.json` and builds against it.
