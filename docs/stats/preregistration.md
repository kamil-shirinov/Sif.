# Statistical evidence preregistration

This is a secondary, retrospective statistical analysis of results that already exist, not a claim of preregistration before those experiments or a prospective validation. Dataset documents were inspected for schema, frozen configuration and provenance before this registration; no bootstrap, shuffle, sensitivity or new headline calculation has been run. Commit and push this file alone before calculation. Keep it immutable; any necessary correction is a separately dated amendment written before the affected calculation. No configuration selection, tuning, event substitution or headline replacement is permitted.

## Frozen calculation and inputs

The machine-readable block below freezes origin/main, the effective July-tuned detector, the current main policy implementation, calendar and runtime code fingerprint. The canonical configuration hash is SHA-256 of sorted compact JSON plus a newline. Source hashes provide an additional runtime-independent check. Synthetic FX policy: USD 1,000,000 equity, total USD 20,000,000 long-USD exposure split equally over supported USD pairs, 2.5% maintenance, 75% cuts at danger alarms and restoration at all-clear, next observed open with side-correct quotes, open-before-trade and close maintenance. No model calls or real portfolios.

Read only the following, never write or commit their data:

* SGX August 2026 test month: `~/Desktop/stormscore/data/processed`, including `metrics.json`, tuned configuration and three SPOT parquets. July is warm-up only. Compare unrounded reconstruction with the rounded saved results and record any difference.
* FX out-of-sample round 1: `docs/oos/results.json` on this base, acquisition and usable processed parquets in the `lane/cx-oos` worktree's `data/external`, discovered with `git worktree list`. Retain every registered event/ordinary window and exclusion. The historical FX policy predates a current-main valuation repair: report original results and current-main recomputation distinctly, never silently attribute a revised policy to the original experiment.
* Round 2: fetch `origin/lane/cx-oos2` every fifteen minutes until 07:45 UTC, include `docs/oos/results-2.json` as soon as it exists, with its preregistered served windows and read-only data in that worktree. Record fetched commit and document/data hashes. If absent at the cutoff, report unavailable, not zero storms. Do not await, demand or alter another lane's scoring. Any usable partial coverage stays labelled partial.
* Chips: `docs/chips/results.json`, original local acquisition in the `lane/cx-chips` worktree's `data/processed/chips`. Headline uses the thirteen new tickers; NVDA is excluded as in-sample. Report NVDA/all-ticker descriptive rows separately. These tickers share dates, sector exposure and the already seen shock week: they are not independent future-period evidence. Reuse session labels, bad-print handling and trailing volatility adapters. For full-period policy statistics use independent long-stock books per new ticker, each USD 1,000,000 equity, 4x initial exposure, 15% maintenance and 75% cuts, following the frozen equity simulator. This is an explicitly new secondary policy analysis, not a previously published full-period result. Yahoo lacks quotes; spread multiplier tests are unavailable for chips, not evidence of zero costs.

## Estimands and uncertainty

For each dataset and the pooled observations, compute: (a) alarmed share = number with a matching alarm / all labelled storms; (b) caught share = number with at least 50% onset-to-trough move remaining / all storms; (c) median percentage move ahead among alarmed storms with defined share; (d) median clock minutes alarm minus strongest-window onset among alarmed storms (negative means earlier); (e) anchored fifteen-minute false-alert episodes / observed days. Matching, false-alarm exclusion buffers and first-onset variants follow `storm.evaluate` unchanged. Show first-onset medians/caught share as an additional robustness check against retrospective strongest-window alignment.

Use 10,000 percentile bootstrap replicates, seed 20261115, 2.5th and 97.5th percentiles, resampling storms with replacement within dataset (all storm rows, then recompute each statistic, excluding undefined values only from conditional medians). Misses are never converted into early alarms. Report number of undefined-median replicates. For false episodes, identify episodes on the original uninterrupted timeline, assign to the opening day, and resample entire observed UTC days jointly across pairs; recompute total episodes divided by total union observed minutes / 1,440. Zero-episode days and partial days stay in. Chips additionally uses ET trading-date blocks and its original per-trading-day denominator. Pool independent dataset/window timelines by summing episodes and exposure, never by deduplicating across unrelated historical dates. Pooled headline rates use observed-day denominators for comparability; retain chips' trading-day rate beside it.

Also show a conservative event-date block bootstrap (UTC storm onset date, joint across pairs; ET for chips) for caught share and alarmed share; this addresses obvious cross-pair dependence but cannot make chosen historical events independent. Pooled intervals stratify by dataset; weights are the actual storm/exposure counts, not equal dataset weights. Overlapping source/time/pair records across rounds are flagged and removed from the pooled headline using fixed priority SGX, round 1, round 2, chips; dataset-specific tables retain them. No unreported independence assumption.

## Chance null and baselines

Primary detection statistic is total caught storms, not the conditional median; higher is better. Primary policy statistic is the sum across independent reset books of final prepared equity minus final unprepared equity in USD, higher is better (including spreads, margin and adverse outcomes). Report maximum drawdown and margin-call differences descriptively; do not select the more favourable statistic. Pooled statistics sum counts and supported-book USD differences. Unsupported non-USD crosses remain in detection but not policy. Chips policy books are secondary and pooled FX-only policy is also shown.

Null: for every independent window and pair, translate its complete alarm train by a uniformly drawn integer-minute offset on the evaluation calendar ring. Use the same offset for its direction-agnostic and book-danger alarms, preserving each train's count, every episode's clock duration, relative timing within pair, danger alignment and closed/open status (open episodes are right-censored at evaluation end for duration). Reject offsets where an episode wraps over the evaluation boundary, an alarm starts off observed/risk-defined bars, or its noncensored clear is not an observed bar. Do not alter prices, labels, positions, execution or calendar watches. Offsets are independent across pairs, so contemporaneous cross-pair dependence is not preserved: state this limitation. This is a conditional timing randomization, not a claim of causal exchangeability, economic predictability or comparison with a deployable random trader. Preserve long calm periods and complete alarm trains rather than resampling labels. Publish feasible-offset counts; a single feasible offset gives no useful timing test and is labelled degenerate. Use inclusive endpoint durations and the existing clear >= onset matching rule exactly.

Use 10,000 fixed-seed shuffles for caught counts; use 1,000 policy shuffles because every path must retain minute-by-minute margin and cash valuation. Detection and policy use the same first 1,000 offset draws. Save full null arrays, observed statistic, null median/95% range, exceedances and one-sided Monte Carlo p = (1 + number(null >= observed)) / (B + 1). Report Monte Carlo binomial standard error sqrt(p*(1-p)/(B+1)). Higher prepared-minus-unprepared is favourable. Give raw and Holm-adjusted p-values across all per-dataset primary detection and policy tests that exist (pooled tests descriptive and separately labelled); do not present null significance as superiority over baselines. Check any accelerated simulator/statistic against the unmodified frozen scorer/simulator on deterministic synthetic paths and representative real shifts before trusting its output.

Run naive and v0 detection baselines on the same available features and splits using `storm.backtest.naive_alarms` and `v0_alarms`. Show their caught/alarmed/false-alert counts and rates plus paired storm-bootstrap 95% intervals for v1-minus-baseline caught share. Do not retrofit book-direction signals or pretend these are frozen baseline trading policies. For chips, naive uses its original gap/session feature handling; label limits of baseline session behavior. Baselines are available wherever their existing implementation accepts the features; retain unavailable reasons.

## Sensitivity (never headline selection)

One factor at a time around the frozen headline, no grid search: spread 1x/2x/3x by multiplying each bid/ask deviation from that bar's unchanged mid; fill delay 1/2/5 observed traded bars after the signal (apply to cuts and restores, next available open; no fills beyond window); cut fraction 50%/75%/100%; initial gross leverage 10x/20x/30x with unchanged equity/maintenance (chips headline remains 4x, so all requested values are stress cases); storm_on 0.70/0.80/0.90 with every other detector setting fixed. If 0.70 violates frozen squall_on=0.75, explicitly report invalid under the frozen ordering constraint rather than change squall_on or bypass validation. Spread has no effect on detection. Other trading changes do not relabel storms. Threshold changes rerun detector and policy, not labels. Report every requested value, invalid/unavailable rows, policy difference, drawdowns, margin calls, caught/alarmed shares and false-episode rate. Show whether the sign of policy benefit, detection caught-share advantage over naive, and chance-test direction survive available perturbations; sensitivity p-values are not rerun and not claimed. No favourable subset may replace the headline.

## Reporting and validation

Publish deterministic `docs/stats/results.json` and `results.md`, full null distributions in JSON under docs/stats, SVG charts, a provenance inventory of all input hashes, versions, commits, seeds and exact command. Include five to eight short judge-facing sentences containing calculated numbers and weaknesses. Null/undefined intervals stay null. Pooled FX and all-domain numbers are descriptive cross-domain mixtures, not forecast accuracy. Save derivations sufficient to audit bootstrap rows, daily exposure, offsets and policy reset windows. A test must reconstruct Markdown from JSON byte-for-byte and validate counts, p-values, configuration and sensitivity coverage. Run the complete backend pytest suite. Commit/push each finished step to lane/cx-stats, only backend/storm/stats, backend/tests/stats, docs/stats. No data committed, no dependency/shared-file edits, no credentials, no provider/database calls. Continue monitoring round 2 on the registered schedule and finish by 08:45 UK (UTC on this date).

## Machine-readable freeze

```json
{
  "schema_version": 1,
  "registered_at_utc": "2026-11-15T05:07:45.333381+00:00",
  "base_commit": "8f88b342da6eecc4c41ef05df15ddb053ce1067c",
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
  "source_sha256": {
    "backend/storm/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "backend/storm/backtest.py": "730c08dd60d17a27819d61df8da70b4e56f2daf81f39f8c6d934d49c3127d38d",
    "backend/storm/detector.py": "78b1d3dcfa888c1573228086168f20678564065a8ade5cf6b97b49967f10dfdc",
    "backend/storm/detector_v0.py": "0d66bbef6d949a2eb4a6a30c21cba47238edf5aa8b4efd57fa4d0d08bf59c89d",
    "backend/storm/equity.py": "b41a9a895306d8878dd1b74d075537a75b0371a83fbc9604eacfa15e76e509c4",
    "backend/storm/evaluate.py": "6a139da401b6be60e8693df4e3b2271329512418ba42ef41ca10ceaf3ce5e057",
    "backend/storm/export.py": "13c1df13fec7dbbb39bbcbf9c5fed0dfa9238bd684cd82945c70a30f764bd5c6",
    "backend/storm/exposure.py": "46962e57f552be79605b3f145c4e9552e1253a097426bd87d33c29dd6239e512",
    "backend/storm/features.py": "6bb736e0f97b4414f18652dbd2cc0739958d441bd78941dbfdeeb9dec29fa24b",
    "backend/storm/ingest.py": "32eed415ea27dc933127f9fba9ee9d5c7d0666fcb047e9729a70511ade8bfb72",
    "backend/storm/labels.py": "d5d5c049fc58b3d449013c47ffe9847b3ced5236116bcec2f91f951bc6f3c70c",
    "backend/storm/paths.py": "1a8bdb417063dd079beb3d069cc0cf5d768a2c54ac38212753f7a6a55b1e99e3",
    "backend/storm/tune.py": "8cb2fe13a36feaca2bd0d53b824d17b699edf454000699389cdaa40482d10d6b",
    "backend/storm/validate.py": "af83086280e66387756ceca46f65579ffe7a8c2daeca7553c0ad548592d407d1"
  },
  "input_documents_sha256": {
    "docs/oos/results.json": "70746e0f36e60663f0d934b703ef5ea2b3687b32bf9f847fe65f3ef45d9e489d",
    "docs/chips/results.json": "f4135e49aa7fd63fcd82fdfeb694b94638ec20a8b7052bed3a98a8f9dd24793e",
    "docs/metrics.md": "72a63700d832a2dc21bc48a4dfb4970679e3622475867b9b8aaa432801943170"
  },
  "sgx_metrics_sha256": "f8790fb3446df787c303528332cafbb92699dfb5f198863424f4f074b759c45d",
  "seed": 20261115,
  "bootstrap_replicates": 10000,
  "detection_shuffles": 10000,
  "policy_shuffles": 1000,
  "sensitivity": {
    "spread_multiplier": [
      1,
      2,
      3
    ],
    "fill_delay_bars": [
      1,
      2,
      5
    ],
    "cut_fraction": [
      0.5,
      0.75,
      1.0
    ],
    "leverage": [
      10,
      20,
      30
    ],
    "storm_on": [
      0.7,
      0.8,
      0.9
    ]
  },
  "round2_poll_interval_minutes": 15,
  "round2_cutoff_utc": "2026-11-15T07:45:00+00:00",
  "finish_by_utc": "2026-11-15T08:45:00+00:00"
}
```
