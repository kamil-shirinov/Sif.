# Frozen FX out-of-sample preregistration 2

Registered and pushed alone before any round-two feed download. Registration 1 and its
published artifacts remain immutable. This second test freezes the version on main now,
not the earlier calculation revision. No tuning, threshold changes, substitutions,
outlier trimming or selection based on detector/policy outcomes is permitted. Changes
require a separately dated amendment with its timing relative to the first scored run.

## Frozen execution specification

```json
{
  "schema_version": 2,
  "frozen_at_utc": "2026-11-15T04:05:11.032923+00:00",
  "base_commit": "3625e41f019551720b4c0e3f860aa48c9652d801",
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
    "exposure": "a094636c2aeb8ef3ecc903a103eac30cd2dbde28beb33b00f215a6ddca1b7f5f",
    "backtest": "bb8bbf73adb0fb890c1d38a3df1895c455e34e1b32bcdee100accebc136dfaee",
    "export": "82abd2eb62b8b39ee72b58b57c47ecf25e4a80c6ea803ce9b7d94a50a8349f11",
    "equity": "5a45bbce8b9188e8263c389564ee81f0b0854757efbf0afbcce8055f6f7ad0c6",
    "tune": "048572e45e14917b77736869721169d4ece57f8fbcf8a0538b0435ae729002d3"
  },
  "calendar_content_sha256": "a8bb611946afde82ccd66ce9ea472870e08e8cecad2ae12cf04f3b36d78cb794",
  "metrics_document_sha256": "72a63700d832a2dc21bc48a4dfb4970679e3622475867b9b8aaa432801943170",
  "runtime": {
    "implementation": "CPython",
    "python": "3.10.0",
    "numpy": "2.2.6",
    "pandas": "2.3.3",
    "pyarrow": "24.0.0"
  },
  "pairs": [
    "EURUSD",
    "USDJPY",
    "USDSGD",
    "GBPUSD",
    "AUDUSD",
    "USDCHF"
  ],
  "sgx_pairs": [
    "EURUSD",
    "USDJPY",
    "USDSGD"
  ],
  "months": [
    {
      "id": "2025-01",
      "start": "2025-01-01",
      "end_exclusive": "2025-02-01",
      "download_start": "2024-12-27"
    },
    {
      "id": "2025-02",
      "start": "2025-02-01",
      "end_exclusive": "2025-03-01",
      "download_start": "2025-02-01"
    },
    {
      "id": "2025-03",
      "start": "2025-03-01",
      "end_exclusive": "2025-04-01",
      "download_start": "2025-03-01"
    },
    {
      "id": "2025-04",
      "start": "2025-04-01",
      "end_exclusive": "2025-05-01",
      "download_start": "2025-04-01"
    },
    {
      "id": "2025-05",
      "start": "2025-05-01",
      "end_exclusive": "2025-06-01",
      "download_start": "2025-05-01"
    },
    {
      "id": "2025-06",
      "start": "2025-06-01",
      "end_exclusive": "2025-07-01",
      "download_start": "2025-06-01"
    },
    {
      "id": "2025-07",
      "start": "2025-07-01",
      "end_exclusive": "2025-08-01",
      "download_start": "2025-07-01"
    },
    {
      "id": "2025-08",
      "start": "2025-08-01",
      "end_exclusive": "2025-09-01",
      "download_start": "2025-08-01"
    },
    {
      "id": "2025-09",
      "start": "2025-09-01",
      "end_exclusive": "2025-10-01",
      "download_start": "2025-09-01"
    },
    {
      "id": "2025-10",
      "start": "2025-10-01",
      "end_exclusive": "2025-11-01",
      "download_start": "2025-10-01"
    },
    {
      "id": "2025-11",
      "start": "2025-11-01",
      "end_exclusive": "2025-12-01",
      "download_start": "2025-11-01"
    },
    {
      "id": "2025-12",
      "start": "2025-12-01",
      "end_exclusive": "2026-01-01",
      "download_start": "2025-12-01"
    }
  ],
  "downloader": {
    "package": "dukascopy-node",
    "version": "1.46.4",
    "published_utc": "2026-03-09T21:18:14.977Z",
    "integrity": "sha512-lpjEE/WG2Q/tpVQpvs2B2CMr2MKZHNAGFI7wHu9U7j3b3N0FdC0BoOUu2NxiUXTZF/HAptpjw6BMpwnPGFx9vQ==",
    "cli_sha256": "4aa0df08ab7e4e6ca22e3ed57b957d4669d1d4a1e31c5244afa91a4cd3ca40f8"
  },
  "deadline": {
    "timezone": "Europe/London",
    "deliver_by_utc": "2026-11-15T07:30:00Z",
    "last_new_month_start_utc": "2026-11-15T06:55:00Z",
    "hard_acquisition_stop_utc": "2026-11-15T07:05:00Z"
  },
  "weekly_book": {
    "synthetic": true,
    "equity_usd": 1000000.0,
    "maintenance_margin": 0.025,
    "cut_fraction": 0.75,
    "legs": [
      {
        "pair": "EURUSD",
        "usd_notional": 20000000.0
      }
    ]
  },
  "differences_from_registration_1": {
    "base_commit_before": "6e61ee4311d4c18c19def5d8b573d0fb67791ee0",
    "config_changed": false,
    "code_modules_changed": [
      "exposure",
      "export",
      "equity"
    ],
    "metrics_definitions_file_changed": true
  }
}
```

Hashes and canonical configuration serialization have exactly the meanings in registration
1: SHA-256; effective config JSON with sorted keys, compact separators and a final newline.
The original tuned file is read only to capture its current config and file hash; no SGX
prices, keys, caps or ledgers are read. `code_fingerprint` comes directly from the current
`storm.backtest.code_fingerprint()`. Execute under the exact recorded runtime. Before
scoring, commit the OOS implementation and record its source hashes and commit. Verification
rebuilds this base and that original runner from local Git objects, irrespective of later
main changes, and makes no downloads. Runtime-sensitive fingerprint tests may skip on
other runtimes with explicit version differences; full verification stays strict.

## Differences from registration 1

The detector configuration is unchanged, including zero comove weight; there is no new
calibration. The machine-readable differences identify the changed calculation modules.
The new main incorporates CC-L's window fix: exposure adds cut_since; export and equity
avoid opening replays within a pre-existing danger alarm, and export refines report facts.
The metric document's worked replay example changed. Features, labels, detector,
detector_v0, evaluate, backtest and tune are unchanged. Registration 2 tests an entire
chronological year and six USD-leg pairs, instead of selected famous events and two
ordinary months. Weekly policy books replace the previous independent event/month books.

## Data, order, conversion and quality

Acquire 1-minute spot bid and ask candles from Dukascopy's free historical feed, using the
exact downloader above (published more than two weeks ago). Use its existing official
HTTP datafeed endpoint and the already documented acquisition-only transport preload;
HTTP has no TLS authentication, so retain and hash every response. Set m1, UTC offset 0,
volumes=true and ignoreFlats=true. Independently exclude zero-volume placeholders before
joining exact minute timestamps; no interpolation or synthetic weekend quotes. The
pinned CLI's volume-output requirement was established in registration 1, before this test.
Three retries per failed artifact, 60-second socket timeout, at most six simultaneous
pair jobs with five requests per downloader batch and one second between batches.

Store all raw bid/ask CSVs, volume metadata, compressed daily .bi5 responses, status logs,
quality diagnostics, manifests and parquets under gitignored `data/external/round2/`.
Do not reuse the round-one June 2025 USDJPY/EURUSD/GBPUSD downloads: download the complete
second dataset afresh, retaining independent provenance. June 2025 on those three pairs
is a **known overlap with registration 1**, not newly unseen observations. Report that
limitation; do not exclude or treat the overlapping month as a new discovery. Other
2025 scheduled or famous events are not manually added to the calendar or selected out.

Attempt months January through December in order. Within each month attempt all six
pairs in listed order, concurrently if useful, and bid then ask per pair. January includes
2024-12-27 through 2024-12-31 as warm-up; subsequent files contain only their calendar
month. A structural source problem (duplicate/non-minute timestamps, invalid OHLC,
nonfinite/nonpositive prices, negative open/close spread, invalid volume) makes that
pair-month unusable; never repair it using another source or dropping price outliers.
Record all reasons. Require at least 50% of nominal Monday-Friday evaluation minutes
joined in each pair-month; require at least 720 joined warm-up bars before 2025 for each
pair. Holidays are permitted by this coarse rule; gaps and actual coverage remain visible.
No price-magnitude rejection. Bid/ask mid OHLC is the arithmetic average of each side's
matching OHLC field, not reconstructed tick extrema. settlement_date is the UTC date,
a schema placeholder. Write the ingest-compatible `<PAIR>_SPOT.parquet` files unchanged.
Unusable pair-months remain in all planned tables and contribute no invented observations.

Concatenate usable monthly files chronologically per pair, with January's warm-up. Features
see all preceding usable observations; missing months stay gaps. Labels use the unchanged
rule on the whole selected prefix, not independent monthly relabelling. No scored bar
precedes 2025-01-01. No supplemental USD conversion pairs or alternative years/vendors.
All six planned instruments have a USD leg: USDxxx books are long the base, xxxUSD books
short the base (long USD). True non-USD crosses are not part of this registration and
would remain unsupported for USD policy valuation rather than receiving invented rates.

## Deadline and missing-data rule, fixed in advance

07:30 UK time on 15 November 2026 is 07:30 UTC. Stop starting months at 06:55 UTC and
terminate any unfinished acquisition at 07:05 UTC, reserving time to score, check, commit
and push. Each CLI side has at most 600 seconds, further limited by the hard stop. Retain
all interrupted diagnostics. A month is completed for deadline purposes only when all
six pair attempts have reached a usable or source-unusable terminal status before the
hard stop. Transport/source failures are reported as unusable, with actual errors; a job
interrupted by the hard cutoff is not evidence of a broken feed.

Select the longest contiguous completed prefix starting in January, even when a completed
month has unusable pairs. An incomplete boundary month and every later month are shown
as not completed by deadline and excluded from scoring as a whole, never chosen pair by
pair or based on returns. Do not start detector scoring while downloading to choose this
prefix. If no month completes, report the study unassessed, not a zero-storm success. If
the full year completes early, use all twelve months. Any scoring/check failure is
reported explicitly; do not silently publish fewer months to evade it.

## Detector and monthly endpoints

Definitions are registration 1's exact labels, onset/first_onset, earliest matched
alarm, share ahead, >=50% caught, observed days, anchored 15-minute false episodes, and
storm-state share from the unchanged scorer. Use the frozen verified calendar as-is;
its 2026 rows do not create historical watches. No retrospective calendar supplementation.
Compute all comparisons/classifications and aggregates unrounded, display with for_display.

Run the detector once per pair over the full selected history with its long-USD exposure.
Its direction-agnostic storm_alarms/episodes give the same detector scoring as exposure=0;
its book-aware events also drive every weekly policy below without re-running detection
for each week. Retain all alarm/clear times. Label whole history, score storms with peak
onset in [2025-01-01,selected_end) and alarms emitted in that interval. Matching is exactly
registration 1 (same pair, onset-60 min through trough, clear absent or >= onset).

Publish yearly/prefix totals for all six pairs and separately SGX's three pairs, plus
per-pair totals and twelve monthly rows per pair. Assign every labelled storm to its
peak-onset calendar month: storms per pair-month is its raw count, including zero.
All monthly share/time medians pool the annual per-storm records on that assignment;
false pair alarms inherit the annual scorer's classification against all scored labels,
so proximity to a month boundary cannot manufacture a false alarm. Assign each anchored
false-alert episode to the month of its opening alarm; cross-month groups are not counted
twice. Other alarms and storm-state minutes follow their actual minute. Monthly observed
days use that pair's own observed minutes /1440; joint totals union minutes across their
pairs, never sum pair-days. Report completed/usable/planned denominators explicitly.

## Independent weekly synthetic policy books

Each pair has its own long-USD $20m book and $1m starting equity (20x), 2.5% maintenance,
75% cut on book-aware danger alarm and restore on all-clear. Reset independently at
Monday 00:00 UTC, clipped to the selected calendar-year interval, with partial first
and final weeks labelled. The initial position is booked at the first observed bar's
close mid; no cost is invented for that starting position. No compounding or equity
transfer between weeks or pairs. Quotes are real observed bid/ask; unchanged aligned_quotes,
policy_actions and ships/simulate_book implement execution and margin ordering. Signals
at close fill at the next real open on the correct side; liquidation and spread costs
use the unchanged engine. At least two bars and 50% nominal weekday-minute coverage
are needed for a usable paired week; list all unavailable weeks with reasons.

An alarm already active at the first observed bar is not forgotten at the reset: inspect
cut_since through that bar's close. If its originating alarm precedes the first bar,
insert a tagged carry-in danger signal at that first close, filled next observed open.
Do not insert it if an all-clear has already occurred by that close, or duplicate a
new alarm at that first bar. Record the original alarm time. This explicit reset convention
extends registration 1's in-window filtering and implements the window-fix intent without
changing another lane's modules. Both books start at full size; a carry-in cut still
pays spread and cannot avoid a breach at the first bar's close.

For every usable pair-week retain both ships' final equity, max dollar/percent drawdown,
margin-call time, cuts/restores/fills, spread costs and all fills with side, price, mid,
USD cost and signal/fill time. Difference = prepared final equity - unprepared final equity,
unrounded; helped iff difference > 0, hurt iff < 0, tie iff exactly 0. Publish share of
usable weeks helped, median and total weekly difference, and sum of spread costs per
ship, per pair, SGX subset and all books. Classify each pair-week as margin call avoided
(unprepared only), induced (prepared only), both called, or neither; do not claim a
saved margin call when both ships were called. These are independent reset books, not
an annual continuous-book return or forecast of profit. Summed P&L uses independent
starting equities; aggregate drawdowns are median/max per-book statistics, not summed
continuous-portfolio drawdown. Pair-month policy groups, when shown, assign a week to
the month of its clipped reset date (first partial week belongs to January).

## Reports and checks

Write results-2.json with all exact and display results, full input hashes, original
registration commit/hash, frozen config/core fingerprints, runtime and committed wrapper
revision/source hashes. results-2.md is deterministically generated from that JSON and
includes a monthly table per pair, weekly policy summaries, the ten largest labelled
storms by abs(move_bp) (ties by onset UTC, then pair), every primary miss (caught=false,
including late alarmed storms and storms with no alarm), and 3-5 plain sentences on
strengths and limits, explicitly noting the round-one overlap and no prediction claim.
Unavailable months/pairs/weeks remain visible. Every labelled storm and every false alarm
remain in JSON even when absent from the top-ten table. A consistency test fails if either
report differs from its deterministic JSON rendering. Refuse a second primary evaluation.

Required: whole backend `python -m pytest -q` and `python -m storm.oos.run --verify`
cover both registrations from their respective rebuilt historical snapshots. No data/
file, key, cap, ledger, shared dependency or another lane's source is committed.
