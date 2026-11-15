# Frozen external FX holdout results

Generated from `results.json`; every displayed metric comes from code. A dash is undefined or unavailable, never a zero observation.

Registration commit: `a849bfeb07f994e8fc4625b39bd8982ea2a0e78b`. Frozen effective-config SHA-256: `30b930c4ffaf7705c1d0c9b3442a5bd7871c957045e8f47c9f7db9fdda8d67ae`.

Canonical results JSON SHA-256: `8ef700c2358a9250027d1f323e376e7637d8fb766697ecc42b9a3707c9349af8`.

## Totals

Observed days union minutes across pairs within a window, then sum the disjoint windows. Medians pool unrounded storm records and exclude misses. Planned/usable counts are pair-windows.

| Metric | Events | Ordinary months | All windows |
| --- | --- | --- | --- |
| Planned / usable pair-windows | 8 / 8 | 6 / 6 | 14 / 14 |
| Storms | 11 | 12 | 23 |
| Alarmed | 9 | 10 | 19 |
| Caught (>=50% ahead) | 5 | 4 | 9 |
| Caught against first onset | 5 | 4 | 9 |
| Median share ahead (%) | 57.3 | 42.8 | 43.4 |
| Median minutes onset to alarm | 5.0 | 7.0 | 5.0 |
| Median share ahead, first onset (%) | 56.3 | 41.2 | 41.3 |
| Median minutes first onset to alarm | 16.0 | 12.5 | 14.0 |
| All storm detections | 12 | 26 | 38 |
| False pair alarms | 3 | 16 | 19 |
| False alert episodes | 3 | 11 | 14 |
| Observed days | 22.63 | 42.16 | 64.79 |
| False pair alarms / observed day | 0.13 | 0.38 | 0.29 |
| False episodes / observed day | 0.13 | 0.26 | 0.22 |
| Squalls / observed day | 0.71 | 1.26 | 1.07 |
| Storm-state minutes | 1028 | 2491 | 3519 |
| Observed pair-minutes | 42389 | 181377 | 223766 |
| Storm-state share (%) | 2.43 | 1.37 | 1.57 |

### Policy totals: independent reset books

These are sums of independent book P&L and costs; drawdowns describe individual windows, rather than a continuous portfolio. Unsupported crosses have no invented USD result.

| Group | Reset books | Ship | pnl_usd | spread_cost_usd | fills | margin_calls | cuts | restores | median_window_max_drawdown_usd | max_window_drawdown_usd | median_window_max_drawdown_pct | max_window_drawdown_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Events | 6 | prepared | -802978 | 74723 | 19 | 3 | 8 | 8 | 648764 | 827332 | 50.4 | 70.5 |
| Events | 6 | unprepared | -1297798 | 56479 | 3 | 3 | 0 | 0 | 788718 | 855330 | 59.5 | 69.0 |
| Ordinary months | 2 | prepared | -340201 | 4746 | 44 | 0 | 22 | 22 | 498153 | 559406 | 46.1 | 50.3 |
| Ordinary months | 2 | unprepared | -332668 | 0 | 0 | 0 | 0 | 0 | 505426 | 558644 | 45.6 | 48.0 |
| All windows | 8 | prepared | -1143179 | 79470 | 63 | 3 | 30 | 30 | 582413 | 827332 | 46.1 | 70.5 |
| All windows | 8 | unprepared | -1630466 | 56479 | 3 | 3 | 0 | 0 | 729410 | 855330 | 57.3 | 69.0 |

### Per-pair pooled totals

Each pair uses its own observed-day denominator. A window with unusable data adds no fabricated observations.

| Pair | Planned / usable windows | Storms | Alarmed | Caught | Caught first onset | Ahead % | Minutes | First ahead % | First minutes | Days | False pairs/day | False episodes/day |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AUDJPY | 1 / 1 | 1 | 1 | 1 | 1 | 69.6 | 11.0 | 68.4 | 16.0 | 3.0 | 0.0 | 0.0 |
| EURCHF | 1 / 1 | 1 | 1 | 1 | 1 | 100.0 | -3.0 | 84.0 | 16.0 | 3.81 | 0.0 | 0.0 |
| EURUSD | 2 / 2 | 4 | 3 | 1 | 1 | 42.1 | 4.0 | 41.3 | 5.0 | 42.01 | 0.17 | 0.17 |
| GBPUSD | 3 / 3 | 4 | 4 | 1 | 1 | 25.3 | 12.0 | 24.5 | 14.5 | 44.81 | 0.07 | 0.07 |
| USDCHF | 1 / 1 | 1 | 1 | 1 | 1 | 100.0 | -2.0 | 85.8 | 16.0 | 3.91 | 0.26 | 0.26 |
| USDJPY | 6 / 6 | 12 | 9 | 4 | 4 | 43.4 | 5.0 | 41.1 | 14.0 | 57.85 | 0.14 | 0.14 |

## SNB floor removal (snb-2015)

UTC evaluation: [2015-01-13, 2015-01-17); warm-up from 2015-01-09. Usable pairs: 2 of 2.

| Pair | Status | Reason | Warm-up bars | Scored bars | Weekday coverage | Unmatched bid / ask | Largest gap min |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EURCHF | usable | — | 2688 | 5493 | 0.9536458333333333 | 0 / 0 | 2881.0 |
| USDCHF | usable | — | 2880 | 5636 | 0.9784722222222222 | 0 / 0 | 2881.0 |

| Detector metric | Joint window | EURCHF | USDCHF |
| --- | --- | --- | --- |
| Storms | 2 | 1 | 1 |
| Alarmed | 2 | 1 | 1 |
| Caught (>=50% ahead) | 2 | 1 | 1 |
| Caught against first onset | 2 | 1 | 1 |
| Median share ahead (%) | 100.0 | 100.0 | 100.0 |
| Median minutes onset to alarm | -2.5 | -3.0 | -2.0 |
| Median share ahead, first onset (%) | 84.9 | 84.0 | 85.8 |
| Median minutes first onset to alarm | 16.0 | 16.0 | 16.0 |
| All storm detections | 3 | 1 | 2 |
| False pair alarms | 1 | 0 | 1 |
| False alert episodes | 1 | 0 | 1 |
| Observed days | 3.92 | 3.81 | 3.91 |
| False pair alarms / observed day | 0.26 | 0.0 | 0.26 |
| False episodes / observed day | 0.26 | 0.0 | 0.26 |
| Squalls / observed day | 0.26 | 0.0 | 0.26 |
| Storm-state minutes | 241 | 59 | 182 |
| Observed pair-minutes | 11129 | 5493 | 5636 |
| Storm-state share (%) | 2.17 | 1.07 | 3.23 |

### Every labelled storm

| Storm | Onset UTC | First onset UTC | Trough UTC | Move bp | Alarm UTC | Alarmed | Caught | Ahead % | Minutes | Caught first | First ahead % | First minutes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| usdchf-2015-01-15 | 2015-01-15T09:33:00+00:00 | 2015-01-15T09:15:00+00:00 | 2015-01-15T09:49:00+00:00 | -2431.8 | 2015-01-15 09:31 | yes | yes | 100.0 | -2 | yes | 85.8 | 16 |
| eurchf-2015-01-15 | 2015-01-15T09:34:00+00:00 | 2015-01-15T09:15:00+00:00 | 2015-01-15T09:48:00+00:00 | -2568.4 | 2015-01-15 09:31 | yes | yes | 100.0 | -3 | yes | 84.0 | 16 |

### Every false pair alarm

| Pair | Alarm UTC | All-clear UTC |
| --- | --- | --- |
| USDCHF | 2015-01-14T13:31:00+00:00 | 2015-01-14T15:33:00+00:00 |

### Joint-window policy

Synthetic USD book: long USD 20,000,000 via USDCHF; equity $1000000; maintenance 0.025; cut 0.75.

USD policy unsupported for: EURCHF.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 346121 | 363481 |
| max_drawdown_usd | 827332 | 809972 |
| max_drawdown_pct | 70.5 | 69.0 |
| margin_calls | 1 | 1 |
| margin_call_utc | 2015-01-15 09:30 | 2015-01-15 09:30 |
| cuts | 1 | 0 |
| restores | 1 | 0 |
| fills | 3 | 1 |
| spread_cost_usd | 28893 | 27714 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 2 |
| squalls | 2 |
| fair_winds | 1 |
| all_clears | 2 |

### Comparable single-pair policies

**EURCHF**

Policy: unsupported. Frozen USD policy engine has no USD valuation for this non-USD cross; no extra conversion pair was registered.

**USDCHF**

Synthetic USD book: long USD 20,000,000 via USDCHF; equity $1000000; maintenance 0.025; cut 0.75.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 346121 | 363481 |
| max_drawdown_usd | 827332 | 809972 |
| max_drawdown_pct | 70.5 | 69.0 |
| margin_calls | 1 | 1 |
| margin_call_utc | 2015-01-15 09:30 | 2015-01-15 09:30 |
| cuts | 1 | 0 |
| restores | 1 | 0 |
| fills | 3 | 1 |
| spread_cost_usd | 28893 | 27714 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 2 |
| squalls | 2 |
| fair_winds | 1 |
| all_clears | 2 |

## Sterling flash crash (gbp-flash-2016)

UTC evaluation: [2016-10-05, 2016-10-09); warm-up from 2016-10-03. Usable pairs: 1 of 1.

| Pair | Status | Reason | Warm-up bars | Scored bars | Weekday coverage | Unmatched bid / ask | Largest gap min |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GBPUSD | usable | — | 2880 | 4140 | 0.9583333333333334 | 0 / 0 | 1.0 |

| Detector metric | Joint window | GBPUSD |
| --- | --- | --- |
| Storms | 1 | 1 |
| Alarmed | 1 | 1 |
| Caught (>=50% ahead) | 0 | 0 |
| Caught against first onset | 0 | 0 |
| Median share ahead (%) | 17.2 | 17.2 |
| Median minutes onset to alarm | 14.0 | 14.0 |
| Median share ahead, first onset (%) | 17.1 | 17.1 |
| Median minutes first onset to alarm | 16.0 | 16.0 |
| All storm detections | 1 | 1 |
| False pair alarms | 0 | 0 |
| False alert episodes | 0 | 0 |
| Observed days | 2.88 | 2.88 |
| False pair alarms / observed day | 0.0 | 0.0 |
| False episodes / observed day | 0.0 | 0.0 |
| Squalls / observed day | 0.35 | 0.35 |
| Storm-state minutes | 37 | 37 |
| Observed pair-minutes | 4140 | 4140 |
| Storm-state share (%) | 0.89 | 0.89 |

### Every labelled storm

| Storm | Onset UTC | First onset UTC | Trough UTC | Move bp | Alarm UTC | Alarmed | Caught | Ahead % | Minutes | Caught first | First ahead % | First minutes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gbpusd-2016-10-06 | 2016-10-06T22:54:00+00:00 | 2016-10-06T22:52:00+00:00 | 2016-10-06T23:09:00+00:00 | -529.4 | 2016-10-06 23:08 | yes | no | 17.2 | 14 | no | 17.1 | 16 |

### Every false pair alarm

| Pair | Alarm UTC | All-clear UTC |
| --- | --- | --- |

### Joint-window policy

Synthetic USD book: long USD 20,000,000 via GBPUSD; equity $1000000; maintenance 0.025; cut 0.75.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 1541563 | 1461772 |
| max_drawdown_usd | 759603 | 839393 |
| max_drawdown_pct | 34.1 | 37.6 |
| margin_calls | 0 | 0 |
| margin_call_utc | — | — |
| cuts | 1 | 0 |
| restores | 1 | 0 |
| fills | 2 | 0 |
| spread_cost_usd | 6129 | 0 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 1 |
| squalls | 1 |
| fair_winds | 1 |
| all_clears | 1 |

### Comparable single-pair policies

**GBPUSD**

Synthetic USD book: long USD 20,000,000 via GBPUSD; equity $1000000; maintenance 0.025; cut 0.75.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 1541563 | 1461772 |
| max_drawdown_usd | 759603 | 839393 |
| max_drawdown_pct | 34.1 | 37.6 |
| margin_calls | 0 | 0 |
| margin_call_utc | — | — |
| cuts | 1 | 0 |
| restores | 1 | 0 |
| fills | 2 | 0 |
| spread_cost_usd | 6129 | 0 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 1 |
| squalls | 1 |
| fair_winds | 1 |
| all_clears | 1 |

## Yen flash crash (jpy-flash-2019)

UTC evaluation: [2019-01-01, 2019-01-05); warm-up from 2018-12-28. Usable pairs: 2 of 2.

| Pair | Status | Reason | Warm-up bars | Scored bars | Weekday coverage | Unmatched bid / ask | Largest gap min |
| --- | --- | --- | --- | --- | --- | --- | --- |
| USDJPY | usable | — | 2756 | 4317 | 0.7494791666666667 | 0 / 0 | 2881.0 |
| AUDJPY | usable | — | 2759 | 4320 | 0.75 | 0 / 0 | 2881.0 |

| Detector metric | Joint window | USDJPY | AUDJPY |
| --- | --- | --- | --- |
| Storms | 2 | 1 | 1 |
| Alarmed | 2 | 1 | 1 |
| Caught (>=50% ahead) | 2 | 1 | 1 |
| Caught against first onset | 2 | 1 | 1 |
| Median share ahead (%) | 63.4 | 57.3 | 69.6 |
| Median minutes onset to alarm | 11.5 | 12.0 | 11.0 |
| Median share ahead, first onset (%) | 62.4 | 56.3 | 68.4 |
| Median minutes first onset to alarm | 16.0 | 16.0 | 16.0 |
| All storm detections | 2 | 1 | 1 |
| False pair alarms | 0 | 0 | 0 |
| False alert episodes | 0 | 0 | 0 |
| Observed days | 3.0 | 3.0 | 3.0 |
| False pair alarms / observed day | 0.0 | 0.0 | 0.0 |
| False episodes / observed day | 0.0 | 0.0 | 0.0 |
| Squalls / observed day | 1.33 | 0.33 | 1.0 |
| Storm-state minutes | 186 | 109 | 77 |
| Observed pair-minutes | 8637 | 4317 | 4320 |
| Storm-state share (%) | 2.15 | 2.52 | 1.78 |

### Every labelled storm

| Storm | Onset UTC | First onset UTC | Trough UTC | Move bp | Alarm UTC | Alarmed | Caught | Ahead % | Minutes | Caught first | First ahead % | First minutes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| usdjpy-2019-01-02 | 2019-01-02T22:23:00+00:00 | 2019-01-02T22:19:00+00:00 | 2019-01-02T22:38:00+00:00 | -333.3 | 2019-01-02 22:35 | yes | yes | 57.3 | 12 | yes | 56.3 | 16 |
| audjpy-2019-01-02 | 2019-01-02T22:24:00+00:00 | 2019-01-02T22:19:00+00:00 | 2019-01-02T22:39:00+00:00 | -659.8 | 2019-01-02 22:35 | yes | yes | 69.6 | 11 | yes | 68.4 | 16 |

### Every false pair alarm

| Pair | Alarm UTC | All-clear UTC |
| --- | --- | --- |

### Joint-window policy

Synthetic USD book: long USD 20,000,000 via USDJPY; equity $1000000; maintenance 0.025; cut 0.75.

USD policy unsupported for: AUDJPY.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 406393 | 406393 |
| max_drawdown_usd | 603086 | 603086 |
| max_drawdown_pct | 59.7 | 59.7 |
| margin_calls | 1 | 1 |
| margin_call_utc | 2019-01-02 22:36 | 2019-01-02 22:36 |
| cuts | 0 | 0 |
| restores | 0 | 0 |
| fills | 1 | 1 |
| spread_cost_usd | 27941 | 27941 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 1 |
| squalls | 2 |
| fair_winds | 1 |
| all_clears | 2 |

### Comparable single-pair policies

**USDJPY**

Synthetic USD book: long USD 20,000,000 via USDJPY; equity $1000000; maintenance 0.025; cut 0.75.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 406393 | 406393 |
| max_drawdown_usd | 603086 | 603086 |
| max_drawdown_pct | 59.7 | 59.7 |
| margin_calls | 1 | 1 |
| margin_call_utc | 2019-01-02 22:36 | 2019-01-02 22:36 |
| cuts | 0 | 0 |
| restores | 0 | 0 |
| fills | 1 | 1 |
| spread_cost_usd | 27941 | 27941 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 1 |
| squalls | 2 |
| fair_winds | 1 |
| all_clears | 2 |

**AUDJPY**

Policy: unsupported. Frozen USD policy engine has no USD valuation for this non-USD cross; no extra conversion pair was registered.

## September intervention (intervention-sep-2022)

UTC evaluation: [2022-09-20, 2022-09-24); warm-up from 2022-09-16. Usable pairs: 1 of 1.

| Pair | Status | Reason | Warm-up bars | Scored bars | Weekday coverage | Unmatched bid / ask | Largest gap min |
| --- | --- | --- | --- | --- | --- | --- | --- |
| USDJPY | usable | — | 2850 | 5566 | 0.9663194444444444 | 0 / 0 | 2881.0 |

| Detector metric | Joint window | USDJPY |
| --- | --- | --- |
| Storms | 2 | 2 |
| Alarmed | 2 | 2 |
| Caught (>=50% ahead) | 1 | 1 |
| Caught against first onset | 1 | 1 |
| Median share ahead (%) | 52.3 | 52.3 |
| Median minutes onset to alarm | 2.5 | 2.5 |
| Median share ahead, first onset (%) | 54.1 | 54.1 |
| Median minutes first onset to alarm | 6.5 | 6.5 |
| All storm detections | 3 | 3 |
| False pair alarms | 1 | 1 |
| False alert episodes | 1 | 1 |
| Observed days | 3.87 | 3.87 |
| False pair alarms / observed day | 0.26 | 0.26 |
| False episodes / observed day | 0.26 | 0.26 |
| Squalls / observed day | 0.52 | 0.52 |
| Storm-state minutes | 211 | 211 |
| Observed pair-minutes | 5566 | 5566 |
| Storm-state share (%) | 3.79 | 3.79 |

### Every labelled storm

| Storm | Onset UTC | First onset UTC | Trough UTC | Move bp | Alarm UTC | Alarmed | Caught | Ahead % | Minutes | Caught first | First ahead % | First minutes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| usdjpy-2022-09-21 | 2022-09-21T18:31:00+00:00 | 2022-09-21T18:28:00+00:00 | 2022-09-21T18:46:00+00:00 | -61.5 | 2022-09-21 18:34 | yes | no | 35.7 | 3 | no | 38.5 | 6 |
| usdjpy-2022-09-22 | 2022-09-22T08:02:00+00:00 | 2022-09-22T07:57:00+00:00 | 2022-09-22T08:43:00+00:00 | -337.9 | 2022-09-22 08:04 | yes | yes | 68.8 | 2 | yes | 69.6 | 7 |

### Every false pair alarm

| Pair | Alarm UTC | All-clear UTC |
| --- | --- | --- |
| USDJPY | 2022-09-22T02:52:00+00:00 | 2022-09-22T03:50:00+00:00 |

### Joint-window policy

Synthetic USD book: long USD 20,000,000 via USDJPY; equity $1000000; maintenance 0.025; cut 0.75.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 1205660 | 1031817 |
| max_drawdown_usd | 561740 | 767464 |
| max_drawdown_pct | 41.4 | 55.4 |
| margin_calls | 0 | 0 |
| margin_call_utc | — | — |
| cuts | 3 | 0 |
| restores | 3 | 0 |
| fills | 6 | 0 |
| spread_cost_usd | 4951 | 0 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 3 |
| squalls | 5 |
| fair_winds | 1 |
| all_clears | 5 |

### Comparable single-pair policies

**USDJPY**

Synthetic USD book: long USD 20,000,000 via USDJPY; equity $1000000; maintenance 0.025; cut 0.75.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 1205660 | 1031817 |
| max_drawdown_usd | 561740 | 767464 |
| max_drawdown_pct | 41.4 | 55.4 |
| margin_calls | 0 | 0 |
| margin_call_utc | — | — |
| cuts | 3 | 0 |
| restores | 3 | 0 |
| fills | 6 | 0 |
| spread_cost_usd | 4951 | 0 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 3 |
| squalls | 5 |
| fair_winds | 1 |
| all_clears | 5 |

## October interventions (intervention-oct-2022)

UTC evaluation: [2022-10-19, 2022-10-25); warm-up from 2022-10-17. Usable pairs: 1 of 1.

| Pair | Status | Reason | Warm-up bars | Scored bars | Weekday coverage | Unmatched bid / ask | Largest gap min |
| --- | --- | --- | --- | --- | --- | --- | --- |
| USDJPY | usable | — | 2871 | 5726 | 0.9940972222222222 | 0 / 0 | 2886.0 |

| Detector metric | Joint window | USDJPY |
| --- | --- | --- |
| Storms | 2 | 2 |
| Alarmed | 1 | 1 |
| Caught (>=50% ahead) | 0 | 0 |
| Caught against first onset | 0 | 0 |
| Median share ahead (%) | 35.2 | 35.2 |
| Median minutes onset to alarm | 10.0 | 10.0 |
| Median share ahead, first onset (%) | 35.3 | 35.3 |
| Median minutes first onset to alarm | 15.0 | 15.0 |
| All storm detections | 2 | 2 |
| False pair alarms | 1 | 1 |
| False alert episodes | 1 | 1 |
| Observed days | 3.98 | 3.98 |
| False pair alarms / observed day | 0.25 | 0.25 |
| False episodes / observed day | 0.25 | 0.25 |
| Squalls / observed day | 1.26 | 1.26 |
| Storm-state minutes | 294 | 294 |
| Observed pair-minutes | 5726 | 5726 |
| Storm-state share (%) | 5.13 | 5.13 |

### Every labelled storm

| Storm | Onset UTC | First onset UTC | Trough UTC | Move bp | Alarm UTC | Alarmed | Caught | Ahead % | Minutes | Caught first | First ahead % | First minutes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| usdjpy-2022-10-21 | 2022-10-21T15:06:00+00:00 | 2022-10-21T12:46:00+00:00 | 2022-10-21T15:54:00+00:00 | -225.8 | — | no | no | — | — | no | — | — |
| usdjpy-2022-10-23 | 2022-10-23T23:28:00+00:00 | 2022-10-23T23:23:00+00:00 | 2022-10-23T23:43:00+00:00 | -260.3 | 2022-10-23 23:38 | yes | no | 35.2 | 10 | no | 35.3 | 15 |

### Every false pair alarm

| Pair | Alarm UTC | All-clear UTC |
| --- | --- | --- |
| USDJPY | 2022-10-21T12:59:00+00:00 | 2022-10-21T17:05:00+00:00 |

### Joint-window policy

Synthetic USD book: long USD 20,000,000 via USDJPY; equity $1000000; maintenance 0.025; cut 0.75.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 1224290 | 962657 |
| max_drawdown_usd | 409078 | 855330 |
| max_drawdown_pct | 27.6 | 62.7 |
| margin_calls | 0 | 0 |
| margin_call_utc | — | — |
| cuts | 2 | 0 |
| restores | 2 | 0 |
| fills | 4 | 0 |
| spread_cost_usd | 5478 | 0 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 2 |
| squalls | 5 |
| fair_winds | 1 |
| all_clears | 5 |

### Comparable single-pair policies

**USDJPY**

Synthetic USD book: long USD 20,000,000 via USDJPY; equity $1000000; maintenance 0.025; cut 0.75.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 1224290 | 962657 |
| max_drawdown_usd | 409078 | 855330 |
| max_drawdown_pct | 27.6 | 62.7 |
| margin_calls | 0 | 0 |
| margin_call_utc | — | — |
| cuts | 2 | 0 |
| restores | 2 | 0 |
| fills | 4 | 0 |
| spread_cost_usd | 5478 | 0 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 2 |
| squalls | 5 |
| fair_winds | 1 |
| all_clears | 5 |

## Carry-trade unwind (carry-2024)

UTC evaluation: [2024-08-01, 2024-08-08); warm-up from 2024-07-30. Usable pairs: 1 of 1.

| Pair | Status | Reason | Warm-up bars | Scored bars | Weekday coverage | Unmatched bid / ask | Largest gap min |
| --- | --- | --- | --- | --- | --- | --- | --- |
| USDJPY | usable | — | 2876 | 7191 | 0.99875 | 0 / 0 | 2884.0 |

| Detector metric | Joint window | USDJPY |
| --- | --- | --- |
| Storms | 2 | 2 |
| Alarmed | 1 | 1 |
| Caught (>=50% ahead) | 0 | 0 |
| Caught against first onset | 0 | 0 |
| Median share ahead (%) | 25.0 | 25.0 |
| Median minutes onset to alarm | 5.0 | 5.0 |
| Median share ahead, first onset (%) | 26.3 | 26.3 |
| Median minutes first onset to alarm | 16.0 | 16.0 |
| All storm detections | 1 | 1 |
| False pair alarms | 0 | 0 |
| False alert episodes | 0 | 0 |
| Observed days | 4.99 | 4.99 |
| False pair alarms / observed day | 0.0 | 0.0 |
| False episodes / observed day | 0.0 | 0.0 |
| Squalls / observed day | 0.6 | 0.6 |
| Storm-state minutes | 59 | 59 |
| Observed pair-minutes | 7191 | 7191 |
| Storm-state share (%) | 0.82 | 0.82 |

### Every labelled storm

| Storm | Onset UTC | First onset UTC | Trough UTC | Move bp | Alarm UTC | Alarmed | Caught | Ahead % | Minutes | Caught first | First ahead % | First minutes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| usdjpy-2024-08-02 | 2024-08-02T12:26:00+00:00 | 2024-08-02T12:15:00+00:00 | 2024-08-02T12:41:00+00:00 | -129.5 | 2024-08-02 12:31 | yes | no | 25.0 | 5 | no | 26.3 | 16 |
| usdjpy-2024-08-07 | 2024-08-07T01:31:00+00:00 | 2024-08-07T01:30:00+00:00 | 2024-08-07T01:46:00+00:00 | 161.7 | — | no | no | — | — | no | — | — |

### Every false pair alarm

| Pair | Alarm UTC | All-clear UTC |
| --- | --- | --- |

### Joint-window policy

Synthetic USD book: long USD 20,000,000 via USDJPY; equity $1000000; maintenance 0.025; cut 0.75.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 472995 | 476081 |
| max_drawdown_usd | 694443 | 691356 |
| max_drawdown_pct | 59.5 | 59.2 |
| margin_calls | 1 | 1 |
| margin_call_utc | 2024-08-04 23:31 | 2024-08-04 23:31 |
| cuts | 1 | 0 |
| restores | 1 | 0 |
| fills | 3 | 1 |
| spread_cost_usd | 1331 | 823 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 1 |
| squalls | 2 |
| fair_winds | 0 |
| all_clears | 2 |

### Comparable single-pair policies

**USDJPY**

Synthetic USD book: long USD 20,000,000 via USDJPY; equity $1000000; maintenance 0.025; cut 0.75.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 472995 | 476081 |
| max_drawdown_usd | 694443 | 691356 |
| max_drawdown_pct | 59.5 | 59.2 |
| margin_calls | 1 | 1 |
| margin_call_utc | 2024-08-04 23:31 | 2024-08-04 23:31 |
| cuts | 1 | 0 |
| restores | 1 | 0 |
| fills | 3 | 1 |
| spread_cost_usd | 1331 | 823 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 1 |
| squalls | 2 |
| fair_winds | 0 |
| all_clears | 2 |

## Ordinary March 2024 (ordinary-mar-2024)

UTC evaluation: [2024-03-01, 2024-04-01); warm-up from 2024-02-28. Usable pairs: 3 of 3.

| Pair | Status | Reason | Warm-up bars | Scored bars | Weekday coverage | Unmatched bid / ask | Largest gap min |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD | usable | — | 2874 | 30143 | 0.9967923280423281 | 0 / 0 | 2881.0 |
| USDJPY | usable | — | 2874 | 30202 | 0.9987433862433862 | 0 / 0 | 2884.0 |
| GBPUSD | usable | — | 2873 | 30142 | 0.9967592592592592 | 0 / 0 | 2885.0 |

| Detector metric | Joint window | EURUSD | USDJPY | GBPUSD |
| --- | --- | --- | --- | --- |
| Storms | 8 | 2 | 4 | 2 |
| Alarmed | 7 | 2 | 3 | 2 |
| Caught (>=50% ahead) | 4 | 1 | 2 | 1 |
| Caught against first onset | 4 | 1 | 2 | 1 |
| Median share ahead (%) | 64.2 | 66.8 | 64.2 | 50.0 |
| Median minutes onset to alarm | 4.0 | -14.5 | 4.0 | -9.0 |
| Median share ahead, first onset (%) | 66.7 | 65.9 | 66.7 | 50.0 |
| Median minutes first onset to alarm | 5.0 | -13.5 | 11.0 | -8.0 |
| All storm detections | 17 | 7 | 6 | 4 |
| False pair alarms | 10 | 5 | 3 | 2 |
| False alert episodes | 7 | 5 | 3 | 2 |
| Observed days | 21.04 | 20.93 | 20.97 | 20.93 |
| False pair alarms / observed day | 0.48 | 0.24 | 0.14 | 0.1 |
| False episodes / observed day | 0.33 | 0.24 | 0.14 | 0.1 |
| Squalls / observed day | 1.09 | 0.29 | 0.38 | 0.43 |
| Storm-state minutes | 1534 | 728 | 492 | 314 |
| Observed pair-minutes | 90487 | 30143 | 30202 | 30142 |
| Storm-state share (%) | 1.7 | 2.42 | 1.63 | 1.04 |

### Every labelled storm

| Storm | Onset UTC | First onset UTC | Trough UTC | Move bp | Alarm UTC | Alarmed | Caught | Ahead % | Minutes | Caught first | First ahead % | First minutes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gbpusd-2024-03-08 | 2024-03-08T13:16:00+00:00 | 2024-03-08T13:16:00+00:00 | 2024-03-08T13:31:00+00:00 | 30.9 | 2024-03-08 13:31 | yes | no | 0.0 | 15 | no | 0.0 | 15 |
| eurusd-2024-03-08 | 2024-03-08T13:27:00+00:00 | 2024-03-08T13:26:00+00:00 | 2024-03-08T13:42:00+00:00 | 31.0 | 2024-03-08 13:31 | yes | no | 33.6 | 4 | no | 31.9 | 5 |
| usdjpy-2024-03-12 | 2024-03-12T12:30:00+00:00 | 2024-03-12T12:30:00+00:00 | 2024-03-12T12:40:00+00:00 | -40.6 | — | no | no | — | — | no | — | — |
| usdjpy-2024-03-19 | 2024-03-19T03:25:00+00:00 | 2024-03-19T03:25:00+00:00 | 2024-03-19T03:40:00+00:00 | 38.8 | 2024-03-19 03:36 | yes | yes | 90.9 | 11 | yes | 90.9 | 11 |
| usdjpy-2024-03-20 | 2024-03-20T18:32:00+00:00 | 2024-03-20T18:22:00+00:00 | 2024-03-20T18:45:00+00:00 | -57.9 | 2024-03-20 18:36 | yes | yes | 64.2 | 4 | yes | 66.7 | 14 |
| eurusd-2024-03-20 | 2024-03-20T18:34:00+00:00 | 2024-03-20T18:33:00+00:00 | 2024-03-20T18:55:00+00:00 | 45.5 | 2024-03-20 18:01 | yes | yes | 100.0 | -33 | yes | 100.0 | -32 |
| gbpusd-2024-03-20 | 2024-03-20T18:34:00+00:00 | 2024-03-20T18:32:00+00:00 | 2024-03-20T18:48:00+00:00 | 40.8 | 2024-03-20 18:01 | yes | yes | 100.0 | -33 | yes | 100.0 | -31 |
| usdjpy-2024-03-27 | 2024-03-27T09:00:00+00:00 | 2024-03-27T08:59:00+00:00 | 2024-03-27T09:15:00+00:00 | -34.3 | 2024-03-27 09:02 | yes | no | 35.9 | 2 | no | 36.0 | 3 |

### Every false pair alarm

| Pair | Alarm UTC | All-clear UTC |
| --- | --- | --- |
| EURUSD | 2024-03-01T15:01:00+00:00 | 2024-03-01T16:12:00+00:00 |
| USDJPY | 2024-03-01T15:01:00+00:00 | 2024-03-01T16:07:00+00:00 |
| EURUSD | 2024-03-05T15:01:00+00:00 | 2024-03-05T15:37:00+00:00 |
| GBPUSD | 2024-03-05T15:01:00+00:00 | 2024-03-05T15:37:00+00:00 |
| USDJPY | 2024-03-05T15:01:00+00:00 | 2024-03-05T15:48:00+00:00 |
| EURUSD | 2024-03-07T13:16:00+00:00 | 2024-03-07T16:18:00+00:00 |
| GBPUSD | 2024-03-12T07:02:00+00:00 | 2024-03-12T07:48:00+00:00 |
| EURUSD | 2024-03-12T12:31:00+00:00 | 2024-03-12T14:35:00+00:00 |
| USDJPY | 2024-03-27T03:13:00+00:00 | 2024-03-27T03:55:00+00:00 |
| EURUSD | 2024-03-28T13:01:00+00:00 | 2024-03-28T14:37:00+00:00 |

### Joint-window policy

Synthetic USD book: long USD 6,666,667 via EURUSD (short EUR); long USD 6,666,667 via USDJPY; long USD 6,666,667 via GBPUSD; equity $1000000; maintenance 0.025; cut 0.75.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 1104864 | 1059383 |
| max_drawdown_usd | 436899 | 452208 |
| max_drawdown_pct | 41.9 | 43.3 |
| margin_calls | 0 | 0 |
| margin_call_utc | — | — |
| cuts | 13 | 0 |
| restores | 13 | 0 |
| fills | 26 | 0 |
| spread_cost_usd | 2555 | 0 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 13 |
| squalls | 30 |
| fair_winds | 4 |
| all_clears | 32 |

### Comparable single-pair policies

**EURUSD**

Synthetic USD book: long USD 20,000,000 via EURUSD (short EUR); equity $1000000; maintenance 0.025; cut 0.75.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 1078383 | 1023413 |
| max_drawdown_usd | 292319 | 331950 |
| max_drawdown_pct | 28.8 | 32.8 |
| margin_calls | 0 | 0 |
| margin_call_utc | — | — |
| cuts | 5 | 0 |
| restores | 5 | 0 |
| fills | 10 | 0 |
| spread_cost_usd | 1596 | 0 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 5 |
| squalls | 10 |
| fair_winds | 2 |
| all_clears | 11 |

**USDJPY**

Synthetic USD book: long USD 20,000,000 via USDJPY; equity $1000000; maintenance 0.025; cut 0.75.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 1217793 | 1173508 |
| max_drawdown_usd | 565705 | 571798 |
| max_drawdown_pct | 52.1 | 52.9 |
| margin_calls | 0 | 0 |
| margin_call_utc | — | — |
| cuts | 5 | 0 |
| restores | 5 | 0 |
| fills | 10 | 0 |
| spread_cost_usd | 3278 | 0 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 5 |
| squalls | 12 |
| fair_winds | 1 |
| all_clears | 12 |

**GBPUSD**

Synthetic USD book: long USD 20,000,000 via GBPUSD; equity $1000000; maintenance 0.025; cut 0.75.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 1018415 | 981229 |
| max_drawdown_usd | 464685 | 457715 |
| max_drawdown_pct | 44.7 | 44.0 |
| margin_calls | 0 | 0 |
| margin_call_utc | — | — |
| cuts | 3 | 0 |
| restores | 3 | 0 |
| fills | 6 | 0 |
| spread_cost_usd | 2792 | 0 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 3 |
| squalls | 8 |
| fair_winds | 1 |
| all_clears | 9 |

## Ordinary June 2025 (ordinary-jun-2025)

UTC evaluation: [2025-06-01, 2025-07-01); warm-up from 2025-05-29. Usable pairs: 3 of 3.

| Pair | Status | Reason | Warm-up bars | Scored bars | Weekday coverage | Unmatched bid / ask | Largest gap min |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD | usable | — | 2695 | 30347 | 1.0035383597883598 | 0 / 0 | 2884.0 |
| USDJPY | usable | — | 2697 | 30304 | 1.0021164021164022 | 0 / 0 | 2885.0 |
| GBPUSD | usable | — | 2685 | 30239 | 0.9999669312169313 | 0 / 0 | 2883.0 |

| Detector metric | Joint window | EURUSD | USDJPY | GBPUSD |
| --- | --- | --- | --- | --- |
| Storms | 4 | 2 | 1 | 1 |
| Alarmed | 3 | 1 | 1 | 1 |
| Caught (>=50% ahead) | 0 | 0 | 0 | 0 |
| Caught against first onset | 0 | 0 | 0 | 0 |
| Median share ahead (%) | 42.1 | 42.1 | 43.4 | 33.4 |
| Median minutes onset to alarm | 10.0 | 10.0 | 10.0 | 10.0 |
| Median share ahead, first onset (%) | 41.1 | 41.3 | 41.1 | 31.9 |
| Median minutes first onset to alarm | 14.0 | 14.0 | 14.0 | 14.0 |
| All storm detections | 9 | 3 | 4 | 2 |
| False pair alarms | 6 | 2 | 3 | 1 |
| False alert episodes | 4 | 2 | 3 | 1 |
| Observed days | 21.12 | 21.07 | 21.04 | 21.0 |
| False pair alarms / observed day | 0.28 | 0.09 | 0.14 | 0.05 |
| False episodes / observed day | 0.19 | 0.09 | 0.14 | 0.05 |
| Squalls / observed day | 1.42 | 0.52 | 0.57 | 0.33 |
| Storm-state minutes | 957 | 326 | 341 | 290 |
| Observed pair-minutes | 90890 | 30347 | 30304 | 30239 |
| Storm-state share (%) | 1.05 | 1.07 | 1.13 | 0.96 |

### Every labelled storm

| Storm | Onset UTC | First onset UTC | Trough UTC | Move bp | Alarm UTC | Alarmed | Caught | Ahead % | Minutes | Caught first | First ahead % | First minutes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eurusd-2025-06-05 | 2025-06-05T13:07:00+00:00 | 2025-06-05T13:03:00+00:00 | 2025-06-05T13:23:00+00:00 | 47.9 | — | no | no | — | — | no | — | — |
| eurusd-2025-06-11 | 2025-06-11T12:21:00+00:00 | 2025-06-11T12:17:00+00:00 | 2025-06-11T12:36:00+00:00 | 45.8 | 2025-06-11 12:31 | yes | no | 42.1 | 10 | no | 41.3 | 14 |
| gbpusd-2025-06-11 | 2025-06-11T12:21:00+00:00 | 2025-06-11T12:17:00+00:00 | 2025-06-11T12:36:00+00:00 | 39.7 | 2025-06-11 12:31 | yes | no | 33.4 | 10 | no | 31.9 | 14 |
| usdjpy-2025-06-11 | 2025-06-11T12:21:00+00:00 | 2025-06-11T12:17:00+00:00 | 2025-06-11T12:36:00+00:00 | -60.0 | 2025-06-11 12:31 | yes | no | 43.4 | 10 | no | 41.1 | 14 |

### Every false pair alarm

| Pair | Alarm UTC | All-clear UTC |
| --- | --- | --- |
| USDJPY | 2025-06-04T12:16:00+00:00 | 2025-06-04T13:02:00+00:00 |
| USDJPY | 2025-06-05T12:31:00+00:00 | 2025-06-05T13:59:00+00:00 |
| EURUSD | 2025-06-06T12:33:00+00:00 | 2025-06-06T15:49:00+00:00 |
| GBPUSD | 2025-06-06T12:33:00+00:00 | 2025-06-06T15:29:00+00:00 |
| USDJPY | 2025-06-06T12:33:00+00:00 | 2025-06-06T13:54:00+00:00 |
| EURUSD | 2025-06-18T14:04:00+00:00 | 2025-06-18T15:25:00+00:00 |

### Joint-window policy

Synthetic USD book: long USD 6,666,667 via EURUSD (short EUR); long USD 6,666,667 via USDJPY; long USD 6,666,667 via GBPUSD; equity $1000000; maintenance 0.025; cut 0.75.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 554935 | 607949 |
| max_drawdown_usd | 559406 | 558644 |
| max_drawdown_pct | 50.3 | 48.0 |
| margin_calls | 0 | 0 |
| margin_call_utc | — | — |
| cuts | 9 | 0 |
| restores | 9 | 0 |
| fills | 18 | 0 |
| spread_cost_usd | 2191 | 0 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 9 |
| squalls | 30 |
| fair_winds | 1 |
| all_clears | 30 |

### Comparable single-pair policies

**EURUSD**

Synthetic USD book: long USD 20,000,000 via EURUSD (short EUR); equity $1000000; maintenance 0.025; cut 0.75.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 472388 | 506358 |
| max_drawdown_usd | 531313 | 497343 |
| max_drawdown_pct | 52.9 | 49.6 |
| margin_calls | 1 | 1 |
| margin_call_utc | 2025-06-12 12:30 | 2025-06-12 12:30 |
| cuts | 2 | 0 |
| restores | 2 | 0 |
| fills | 5 | 1 |
| spread_cost_usd | 2093 | 705 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 3 |
| squalls | 13 |
| fair_winds | 0 |
| all_clears | 13 |

**USDJPY**

Synthetic USD book: long USD 20,000,000 via USDJPY; equity $1000000; maintenance 0.025; cut 0.75.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 908176 | 992559 |
| max_drawdown_usd | 572638 | 570233 |
| max_drawdown_pct | 38.8 | 36.6 |
| margin_calls | 0 | 0 |
| margin_call_utc | — | — |
| cuts | 4 | 0 |
| restores | 4 | 0 |
| fills | 8 | 0 |
| spread_cost_usd | 2553 | 0 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 4 |
| squalls | 11 |
| fair_winds | 1 |
| all_clears | 11 |

**GBPUSD**

Synthetic USD book: long USD 20,000,000 via GBPUSD; equity $1000000; maintenance 0.025; cut 0.75.

| Policy metric | Prepared | Unprepared |
| --- | --- | --- |
| final_equity_usd | 510347 | 604446 |
| max_drawdown_usd | 589767 | 589841 |
| max_drawdown_pct | 53.6 | 51.9 |
| margin_calls | 1 | 0 |
| margin_call_utc | 2025-06-26 16:39 | — |
| cuts | 2 | 0 |
| restores | 2 | 0 |
| fills | 5 | 0 |
| spread_cost_usd | 2209 | 0 |

| Book-aware alert | Count |
| --- | --- |
| danger_alarms | 2 |
| squalls | 6 |
| fair_winds | 0 |
| all_clears | 6 |

## What the test shows

The frozen detector alarmed on 19 of 23 labelled storms and caught 9 with at least half the peak-onset move still ahead. Against the first onset, it caught 9; misses and late alarms remain in the tables. The ordinary-month sample produced 11 false alert episodes over 42.16 observed days. Data were usable for 14 of 14 planned pair-windows; non-USD crosses have no supported USD policy valuation in the frozen engine. This historical stress selection measures rapid detection on another feed and period, and does not demonstrate advance prediction of unscheduled prices.

All acquisition artifacts and per-fill policy records are hashed or recorded in `results.json`. Recompute locally with `cd backend && python -m storm.oos.run --verify`; this requires the original gitignored `data/external/` artifacts and performs no downloads.
