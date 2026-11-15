# Frozen FX out-of-sample preregistration

Registered before any external FX download or inspection. The isolated branch starts at the
`base_commit` below. This file is committed and pushed alone before data acquisition.
It is immutable: corrections require a separate dated amendment, with reason and timing
relative to the first detector run. There will be no tuning, changed thresholds, event
substitution, or selection after results. These are historical holdouts, not a prospective
forecast trial; event names are deliberately selected stress cases. This procedure does
not establish that nobody previously knew these public events or used this feed.

## Frozen artifacts

The machine-readable block is authoritative for execution. `config_sha256` hashes UTF-8
`json.dumps(config, sort_keys=True, separators=(",", ":")) + "\n"`.
`source_config_file_sha256` hashes the existing tuned file's exact bytes, including its
July-only tuning metadata. No SGX price data are read in this study. The effective config
is copied here because `data/processed/detector_config.json` is not tracked.
`code_fingerprint` is the unmodified `storm.backtest.code_fingerprint()` result, including
source, runtime constants and imported bindings for every provenance module. Execution
must refuse a config, code, metric-definition or effective-calendar mismatch.

```json
{
  "schema_version": 1,
  "frozen_at_utc": "2026-11-15T01:15:03.280012+00:00",
  "base_commit": "6e61ee4311d4c18c19def5d8b573d0fb67791ee0",
  "config": {
    "version": 1,
    "move_windows": [
      1,
      3,
      5
    ],
    "strength_full": 10.0,
    "w_comove": 0.0,
    "comove_min": 2,
    "squall_on": 0.75,
    "storm_on": 0.8,
    "storm_minutes": 2,
    "calm_off": 0.25,
    "calm_minutes": 20,
    "watch_lead_minutes": 30,
    "watch_after_minutes": 15,
    "max_bar_gap_minutes": 5
  },
  "config_sha256": "30b930c4ffaf7705c1d0c9b3442a5bd7871c957045e8f47c9f7db9fdda8d67ae",
  "source_config_file_sha256": "63d95f3ebf11e3e46b458a9621ff6c934be260d22cf96491aa54a79551082e1b",
  "code_fingerprint": {
    "labels": "47efbeb54979d77c239f0c8298180bde01aee8cf2acd867c40f3edd0d72c4304",
    "features": "d62a96bb68ea83daecf97d3fe943b79d34798fae23908210b8e27b966dfbd318",
    "detector": "a95888705317e0fa6141fc849352e2c7bd3fb580d2fb43e40138c9d36aa8f4a6",
    "detector_v0": "835b998678417447c11f31adaded6246c44580d84231f499a1d5bd632769b4f2",
    "evaluate": "b34c336f70b367a74927d9affcbe930e395b9d35b379b8c9ee93edeec1c13965",
    "exposure": "25a9e1cf036db5dca9d9628d251b044eb75242f6972d3fb6da8e192eb43cd9a0",
    "backtest": "bb8bbf73adb0fb890c1d38a3df1895c455e34e1b32bcdee100accebc136dfaee",
    "export": "f37470cfae7ffce0fc6a5923192aeb42c1f791caa4008e116ff940757ac027b1",
    "equity": "cf849b4d9019415b990127a07945f1aad0905d90f6e4c5e9bdd36016f03e9a69",
    "tune": "048572e45e14917b77736869721169d4ece57f8fbcf8a0538b0435ae729002d3"
  },
  "calendar_content_sha256": "a8bb611946afde82ccd66ce9ea472870e08e8cecad2ae12cf04f3b36d78cb794",
  "metrics_document_sha256": "afdd17d13bf0a20da9e3368076ec45c99670c1458f4291647e20e11383bce567",
  "downloader": {
    "package": "dukascopy-node",
    "version": "1.46.4",
    "published_utc": "2026-03-09T21:18:14.977Z",
    "integrity": "sha512-lpjEE/WG2Q/tpVQpvs2B2CMr2MKZHNAGFI7wHu9U7j3b3N0FdC0BoOUu2NxiUXTZF/HAptpjw6BMpwnPGFx9vQ=="
  },
  "windows": [
    {
      "id": "snb-2015",
      "name": "SNB floor removal",
      "start": "2015-01-13",
      "end_exclusive": "2015-01-17",
      "download_start": "2015-01-09",
      "pairs": [
        "EURCHF",
        "USDCHF"
      ],
      "group": "events"
    },
    {
      "id": "gbp-flash-2016",
      "name": "Sterling flash crash",
      "start": "2016-10-05",
      "end_exclusive": "2016-10-09",
      "download_start": "2016-10-03",
      "pairs": [
        "GBPUSD"
      ],
      "group": "events"
    },
    {
      "id": "jpy-flash-2019",
      "name": "Yen flash crash",
      "start": "2019-01-01",
      "end_exclusive": "2019-01-05",
      "download_start": "2018-12-28",
      "pairs": [
        "USDJPY",
        "AUDJPY"
      ],
      "group": "events"
    },
    {
      "id": "intervention-sep-2022",
      "name": "September intervention",
      "start": "2022-09-20",
      "end_exclusive": "2022-09-24",
      "download_start": "2022-09-16",
      "pairs": [
        "USDJPY"
      ],
      "group": "events"
    },
    {
      "id": "intervention-oct-2022",
      "name": "October interventions",
      "start": "2022-10-19",
      "end_exclusive": "2022-10-25",
      "download_start": "2022-10-17",
      "pairs": [
        "USDJPY"
      ],
      "group": "events"
    },
    {
      "id": "carry-2024",
      "name": "Carry-trade unwind",
      "start": "2024-08-01",
      "end_exclusive": "2024-08-08",
      "download_start": "2024-07-30",
      "pairs": [
        "USDJPY"
      ],
      "group": "events"
    },
    {
      "id": "ordinary-mar-2024",
      "name": "Ordinary March 2024",
      "start": "2024-03-01",
      "end_exclusive": "2024-04-01",
      "download_start": "2024-02-28",
      "pairs": [
        "EURUSD",
        "USDJPY",
        "GBPUSD"
      ],
      "group": "ordinary"
    },
    {
      "id": "ordinary-jun-2025",
      "name": "Ordinary June 2025",
      "start": "2025-06-01",
      "end_exclusive": "2025-07-01",
      "download_start": "2025-05-29",
      "pairs": [
        "EURUSD",
        "USDJPY",
        "GBPUSD"
      ],
      "group": "ordinary"
    }
  ]
}
```

## Acquisition and conversion (fixed before inspection)

Use Dukascopy's free historical feed, via the exact npm package/version above, published
more than fourteen days before registration. Publication and integrity were checked with
`npm view dukascopy-node@1.46.4 version dist.integrity time --json` (package metadata only).
Fetch `m1`, UTC offset zero, separately for bid and ask, without zero-volume flat candles.
Use bounded retries (three) for transport failures, never for unwanted detector results.
Do not acquire alternative vendors or events. Retain raw responses, download diagnostics,
converted parquets and acquisition manifest under `data/external/`, excluded locally via
Git's worktree exclude mechanism without changing the shared `.gitignore`.

All starts are inclusive 00:00 UTC and ends exclusive 00:00 UTC. User-specified final
dates are inclusive, hence the next-day ends above. Warm-up begins two preceding weekday
trading dates early (Monday-Friday convention; no holiday backfill or interpolation).
Each month is a joint three-pair window; each famous event is a joint window of its
specified pairs. Every listed event/pair remains in the results, even if unusable.

Join bid/ask by exact epoch-millisecond minute timestamps. Do not forward-fill missing
bars, smooth jumps, remove outliers, winsorise, or fill weekends. Report unmatched sides
and gaps. Per-side timestamps must be unique and minute aligned; quotes must be finite,
positive, internally valid OHLC and have nonnegative open/close spreads. A structural
failure makes that pair unusable, with the exact reason. Empty downloads and exhausted
transport retries are unusable. Require at least 720 joined warm-up bars and at least
50% of the nominal Monday-Friday evaluation minutes to be joined; report actual coverage
and gaps even when usable. This coarse completeness rule deliberately permits holidays;
it is not a claim that an event minute itself is observed. No price-magnitude rejection.

Write `data/external/<window>/processed/<PAIR>_SPOT.parquet`, with timestamp (UTC ns),
settlement_date (timestamp's UTC date, a schema placeholder, never used as market data),
and open/high/low/close for bid and ask. Each `*_mid` is the arithmetic average of the
same bid and ask OHLC field. High/low mids are quote-side candle averages, not tick-level
mid extrema. Preserve the source bar's timestamp as the bar stamp used by the pipeline.
No new runtime Python dependency; the pinned npm downloader is an acquisition tool only.

Source references: [downloader](https://github.com/Leo4815162342/dukascopy-node),
[CLI options](https://www.dukascopy-node.app/config/cli),
[versions](https://www.npmjs.com/package/dukascopy-node?activeTab=versions).

## Execution and pair compatibility

Run one frozen evaluation, once acquisition/conversion and implementation checks finish.
`--verify` may only recompute and compare, never overwrite results or tune anything.
Features and detector states see warm-up; labels see the whole downloaded window; score
only labels whose peak-window onset is in [start,end), and alarms emitted in that interval,
as in `storm.backtest`. Keep all labels, including incidental storms in ordinary months.
Labels at the right edge are necessarily right censored; no extra post-window prices.
Use the unchanged verified calendar and label rules, with its content hash frozen above;
its 2026 entries do not provide historical watches. No retrospective calendar additions.

For USD pairs use unchanged `build_features`, `label_all`, `run_detector`, `score` and
`policy_backtest`. For EURCHF and AUDJPY the frozen core rejects `usd_sign(pair)`.
An OOS-only adapter calls `pair_features` and `label_all` with the positive-sign surrogate
`USDJPY`, then restores the actual pair/ID and sets derived `usd_z`/`usd_move_bp` unavailable.
This reuses exactly the same price-only volatility, window, merge and onset logic;
it invents no conversion rate. Set comove to zero for these crosses; frozen `w_comove=0`
makes all comove inputs inert. No monkey-patching of core constants or bindings.
Crosses remain in every price-only detector metric and total. The synthetic **USD** policy
backtest for these crosses is explicitly unsupported: the frozen engine cannot value
non-USD crosses without additional USD conversion prices. Do not download extra pairs,
pretend a cross is a USD pair for valuation, or classify this as broken source data.

## Exact endpoints and aggregation

Definitions are frozen from `docs/metrics.md` sections 1, 2, 4, 5, 6 and 8 and the current
`storm.evaluate` implementation. All comparisons, medians and classifications use unrounded
values; apply `for_display` only to final presentation. Report per window, per pair,
per labelled storm and total, including zero storms, misses, all false alarms and unusables.

- Label: 15-minute simple mid move at least max(30bp, 8 * prior sd_24h * sqrt(15)),
  at least 13 observed minutes; merge trigger windows no more than six hours apart.
  Onset is the strongest trigger's start, first_onset the first trigger's start;
  trough is the directional extreme from onset through the last trigger end.
- Alarmed: earliest direction-agnostic storm detection on the same pair in
  [onset-60min,trough], whose all-clear is absent or >= onset. Detection completes
  two consecutive minutes at the frozen storm threshold. No book direction in scoring.
- Caught: alarmed with >=50% of the onset-to-trough move still ahead, exact before rounding.
  Also report caught_first_onset under the same matching rule and the first-onset share.
- Share ahead: 100 if alarm<=onset, 0 if alarm>=trough, otherwise
  clip(100*(mid_alarm-mid_trough)/(mid_onset-mid_trough),0,100); undefined for a zero
  denominator. Repeat with first_onset and its mid. Unalarmed storms have null shares,
  null alarm times and caught=false; share/time medians include alarmed storms only.
- Minutes to alarm: alarm minus onset in whole minutes (negative is advance warning),
  repeated against first_onset. Report both medians and every storm's two values.
- False pair alarms: detections outside [onset-60min,end+60min] of every label on that
  pair. Episodes anchor a 15-minute inclusive grouping window at the first ungrouped
  false alarm across all pairs. Observed days = distinct observed minutes on any pair
  /1440, never calendar days or summed pair-days. Report counts, denominator and both
  rates. Also report all alarm/clear times, squalls and storm-state share.
- Totals: pool raw storm records (no averaging rounded medians), union observed minutes
  within each joint window, sum observed days over the disjoint windows, and group false
  episodes across the joint pairs. Publish events, ordinary months and all-window totals
  separately. Per-pair totals use that pair's own observed-day denominator. Missing pairs
  contribute no invented observations; list the full planned and usable counts.
- Policy: unchanged `exposure.book_for(usable USD pairs in each window)`: synthetic long
  USD $20m split equally across supported usable legs, $1m starting equity, 2.5%
  maintenance, cut 75% on book-aware alarm and restore on all-clear. Signal at close,
  fill next real bar open, side-correct bid/ask, unchanged margin ordering. No trades in
  warm-up. Report both ships' final equity, max dollar/percent drawdown, margin calls,
  cuts, restores, fills, spread costs and every prepared fill. For each USD pair also
  report a separate single-leg $20m policy for comparability. Changing pairs changes the
  portfolio and must be visible. Policy totals sum P&L, spread costs, fills and margin
  calls for independent reset books; no sum or average is presented as one continuous
  book's maximum drawdown. Report median/max per-window drawdowns instead.

## Deliverables and checks

`results.json` records this file's SHA-256 and its first commit, frozen config/code hashes,
raw and parquet SHA-256s, dataset statuses/reasons, exact and display metrics and policy
results. `results.md` is rendered deterministically from that JSON, with per-event tables,
a totals table and 3-5 plain sentences describing successes and limitations without a
price-prediction claim. An offline test fails if the files disagree. A one-shot run must
refuse overwriting results. Verification recomputes using local data only and compares all
recorded numerical results and data/config/code hashes, with no downloads. Missing data
must fail verification, not silently convert a previously usable sample to unusable.

Required checks: `cd backend && python -m pytest -q` and
`cd backend && python -m storm.oos.run --verify`. Data are never committed.
