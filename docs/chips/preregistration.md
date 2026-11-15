# Chip-sector preregistration

This file is committed and pushed alone before any chip acquisition. The frozen base is origin/main at the commit below; no detector tuning, thresholds, calendar selection, data-dependent universe changes, or reruns after inspecting scores are allowed. NVDA is in-sample because its bars were used to build the equity path. The other thirteen tickers (including the two ETFs) are the new cross-ticker test; sector correlation and the previously seen shock week mean this is not an independent future-period test.

## Acquisition and equity rules

Acquire every Yahoo one-minute bar available in the most recent thirty calendar days, in nonoverlapping requests of at most seven calendar days (Yahoo limits intraday request spans). This tests the user's approximate seven-trading-day retention assumption rather than truncating available history to it. Fix end exclusive to 16 November 2026; stop at the fixed oldest boundary. Record empty responses, unavailable ranges, exceptions and actual served bounds for every ticker. No alternate provider, synthetic replacement or selective removal. Retry only failed transport requests with the same bounds, before evaluation; retain original failures. Save all returned OHLCV locally with hashes, request provenance and package versions; never commit bars. One evaluation of the completed snapshot, with no threshold changes.

Use storm.equity's rules: ET weekdays 04:00 through 19:59, with pre-market, regular and after-hours bars. Keep flagged bad prints in the data: at least a 2% close jump whose next open retraces to within a quarter of the log jump, neighbours no more than five minutes away. Features and detector see that print at its own minute and exclude it from later windows only after its reversal is observed. Baselines require 720 defined returns in the preceding 1,440 observed bars; no return/window spans a session change or a missing exact minute. A session outside the original module's hardcoded November 9–13 slice is retained by a lane-local input adapter using the same session_ids and bad_prints functions. All source modules remain untouched.

The replay book is synthetic: long $4,000,000 on $1,000,000 equity, 15% maintenance, cut 75% on danger alarm, restore on all-clear, next observed bar open execution and open-before-trade/close margin checks. Yahoo prices are trades: no measured spread, fees or slippage. The frozen comove coefficient is zero; stock-only comove is descriptive and the ETFs do not enter it. No verified equity event calendar is supplied, so all labels are unscheduled and scheduled-watch metrics are not applicable.

## Labels and metrics

Apply docs/metrics.md's fifteen-minute labels to every served ticker, retaining the trailing full-history volatility but labelling separately inside each ET session so labels cannot span a closure. Retrospective labels use unflagged prices, as storm.equity does for its close and low. Run storm.labels.label_all on those session slices; preserve its 30 bp floor, 8-sigma threshold, 13/15 observed-minute requirement, six-hour merging, strongest-window onset, first onset and close-price extremum. Never treat every ticker as a storm merely because a particular day fell. Zero-storm and unavailable tickers remain in the table. The November 11 close-to-November 12 low shock facts are reported separately where available; they do not replace or add to the automatic label counts.

Score once with storm.evaluate.score: direction-agnostic storm detections; earliest matching alarm in [onset - 60 minutes, trough] still active at onset; caught iff at least 50% of the move remains; report alarmed, caught, first-onset variants, median share remaining and median clock minutes to alarm. List every storm (including misses), every detection and false detection. For each ticker and pooled, include counts, storm-state share over observed ticker-minutes, and both false pair alarms and anchored fifteen-minute false-alert episodes.

The requested false-alert denominator is the number of distinct ET trading dates with at least one returned in-hours bar, using the union of dates for pooled rows. Label these rates per trading day. Also retain docs/metrics.md's observed-day denominator (union of observed UTC minutes / 1,440) and both original rates, so neither meaning of a day is hidden. Pooled summaries are recomputed from all storms and alarm times, not averages of ticker medians/rates. Publish separate NVDA in-sample, thirteen-new-ticker pooled, and all-ticker descriptive rows. The earliest bars are warm-up, not silently removed: report raw, in-hours, flagged, warmed-up and risk-defined counts plus all observed session dates.

## Replays, database, and AI

Rank all labelled new-ticker storms by absolute unrounded move_bp, descending (ties by onset UTC then ticker). Choose the first three, irrespective of whether caught, direction or ship outcome. Reuse storm.equity.build_bundle through a lane-local in-memory parameter adapter for symbol, book, ID/title, and selected onset/trough facts. Its frozen detector, grid, execution, margin and policy remain the implementation. Override the NVDA-specific label text with the actual selected dates. Stress candidates are labels recomputed as of the exposure snapshot with only reversals observable by then, and only troughs before it; no future shock-low stress facts. Expand replay start backwards if necessary to include an already-active danger alarm. Validate each finished bundle with storm.validate. Write only local bundles to the user's main web/public/bundles and append with storm.export.write_index, keeping all prior entries, order and index metrics.

Load every acquired bar (including flagged observations) into equity_1m through storm.live.db helpers, never rendering the connection URL or secrets. Use a non-destructive ticker/time primary key, verify exact per-ticker counts for the acquired slice, a five-minute continuous aggregate, a compression policy and measured manual compression. Record server compression bytes/ratio and a timed sample query with SQL and returned row count. Do not replace any FX tables.

Run the exact same three bundles through the default GLM writer / Kimi inspector using storm.ai.report and only storm.ai.llm.complete for inference. Retain those reports in the replays. Then run the all-private crew using the existing Modal app/weights; record numeric first-draft verification separately from accepted-first-draft prose, retry/fallback outcomes, inspector flags, elapsed latency and cost. Fireworks task cap is $10 with the existing 75% warning/90% refusal guard; never change caps/ledger. Bound Modal runtime conservatively below $10, include startup/idle overhead, record token cost (zero) separately from runtime estimate/metrics, and stop the app in a finally cleanup. No provider fallback in private mode. Failures are reported, not silently turned into successes.

## Reporting and checks

Publish docs/chips/results.json with provenance, all per-ticker/pooled/individual rows, replay selection, both AI rows and Tiger statistics; render results.md deterministically from that JSON, including three to five plain interpretation sentences. A test compares the full rendered Markdown to the checked-in Markdown and checks pooled totals and the NVDA split. Run python -m pytest -q in backend and existing validators on new bundles and the refreshed index. Commit/push only backend/storm/chips, backend/tests/chips and docs/chips. No shared modules, dependencies, credentials, data or bundles are committed. Finish before 07:30 UK on 15 November 2026, recording any blocked components honestly.

## Frozen machine-readable specification

```json
{
  "registered_at_utc": "2026-11-15T04:01:26.274494+00:00",
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
  "config_file_sha256": "63d95f3ebf11e3e46b458a9621ff6c934be260d22cf96491aa54a79551082e1b",
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
  "source_sha256": {
    "backend/storm/equity.py": "b41a9a895306d8878dd1b74d075537a75b0371a83fbc9604eacfa15e76e509c4",
    "backend/storm/export.py": "13c1df13fec7dbbb39bbcbf9c5fed0dfa9238bd684cd82945c70a30f764bd5c6",
    "backend/storm/live/db.py": "3d05e827cc09511f5095782e9bd78fcd60fc97bca268fe5bd0f5ea92f4d44166",
    "backend/storm/live/tiger.py": "887b1b7577493311d68abdc89ccbd26b4eb45f64efeeb8c16b166432084b1446",
    "backend/storm/ai/report.py": "cfd73b30362a5b84d8041f3251cb6cbf79fe764f80e05d4c4c44149892f87283",
    "backend/storm/ai/llm.py": "2a64d9fb51dac4bb891c3aae60c589eedd96c10b4670c06b54e92810dbfc1952",
    "backend/storm/ai/inspector.py": "eafa40145e894bfaf8c241bae33c95b235ed4a0c2ce463e3cd9adfbec18ba919",
    "backend/storm/ai/budget.py": "41f5532efe147265f2cadc720e85d9b1d290e883e86ed060fcbf715dc17d93a6",
    "docs/metrics.md": "72a63700d832a2dc21bc48a4dfb4970679e3622475867b9b8aaa432801943170"
  },
  "tickers": [
    "NVDA",
    "AMD",
    "AVGO",
    "TSM",
    "MU",
    "ARM",
    "SMCI",
    "INTC",
    "QCOM",
    "MRVL",
    "AMAT",
    "LRCX",
    "SMH",
    "SOXX"
  ],
  "in_sample": [
    "NVDA"
  ],
  "acquisition": {
    "provider": "Yahoo Finance via yfinance",
    "interval": "1m",
    "prepost": true,
    "auto_adjust": false,
    "actions": false,
    "lookback_calendar_days": 30,
    "max_request_calendar_days": 7,
    "end_date_exclusive": "2026-11-16",
    "overlap_deduplication": "ticker + UTC timestamp; conflicts are errors"
  },
  "budgets_usd": {
    "fireworks": 10,
    "modal": 10
  },
  "deadline_uk": "2026-11-15T07:30:00+00:00"
}
```
