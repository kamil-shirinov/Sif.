# Frozen FX out-of-sample results — registration 2

Status: **chronological_prefix**. Completed chronological months: 2025-01, 2025-02, 2025-03, 2025-04, 2025-05, 2025-06, 2025-07; end exclusive: 2025-08-01. Usable pair-months: 24 / 72.

Registration commit `5f39e4562e4d0b082655e9ce43d583bc4647fd0c`; base `3625e41f019551720b4c0e3f860aa48c9652d801`; config SHA-256 `30b930c4ffaf7705c1d0c9b3442a5bd7871c957045e8f47c9f7db9fdda8d67ae`.

Canonical results JSON SHA-256: `5d2d6692fe004cea215dbdc0cfe147994889fac4e157d736b1cd3496f4f106d8`.

A dash is unavailable, not zero. Monthly storms are assigned by peak onset; shares and minutes also refer to first onset where labelled. False-alarm classifications use all labels in the completed prefix.

Years present in the frozen verified calendar: 2026. No retrospective watch dates were added; weekly cuts follow the book-aware price alarm.

## Detector totals

| Metric | All six pairs | SGX pairs |
| --- | --- | --- |
| Storms | 38 | 29 |
| Alarmed | 32 | 24 |
| Caught (>=50% ahead) | 10 | 8 |
| Caught against first onset | 10 | 8 |
| Median share ahead (%) | 29.3 | 30.5 |
| Median minutes onset to alarm | 6.0 | 6.0 |
| Median share ahead, first onset (%) | 29.2 | 30.1 |
| Median minutes first onset to alarm | 15.0 | 15.0 |
| All storm detections | 97 | 78 |
| False pair alarms | 63 | 52 |
| False alert episodes | 49 | 43 |
| Observed days | 146.07 | 138.82 |
| False pair alarms / observed day | 0.43 | 0.37 |
| False episodes / observed day | 0.34 | 0.31 |
| Squalls / observed day | 1.44 | 1.17 |
| Storm-state minutes | 8253 | 6299 |
| Observed pair-minutes | 653599 | 490408 |
| Storm-state share (%) | 1.26 | 1.28 |

## Initial December warm-up eligibility

A valid warm-up interval is separate from January evaluation coverage; no substitute history is inferred for a missing initial warm-up.

| Pair | Warm-up status | Joined warm-up bars | Reason |
| --- | --- | --- | --- |
| EURUSD | usable | 4196 | — |
| USDJPY | usable | 4171 | — |
| USDSGD | usable | 2721 | — |
| GBPUSD | unusable | — | insufficient initial warm-up: 0 < 720 |
| AUDUSD | unusable | — | AUDUSD_ask_warmup.csv: empty candle file |
| USDCHF | usable | 4176 | — |

## Independent Monday-reset policy books

SYNTHETIC: each pair-week starts with $1M equity and a long-USD $20M leg; maintenance 2.5%, cut 75%, side-correct next-bar execution. Positive difference means prepared final equity exceeded unprepared final equity. These independent books do not constitute one continuous annual return. Active carry-in alarms are acted on after the first observed close, as registered. USD-base pairs are long the base; pairs ending USD are short the base. No true non-USD crosses were added.

| Group | usable_pair_weeks | unavailable_pair_weeks | helped | hurt | ties | helped_share_pct | median_difference_usd | total_difference_usd | margin_calls_avoided | margin_calls_induced | both_margin_called | neither_margin_called |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| All | 98 | 220 | 13 | 23 | 62 | 13.3 | 0 | -477177 | 1 | 0 | 9 | 88 |
| SGX | 73 | 86 | 10 | 19 | 44 | 13.7 | 0 | -444074 | 1 | 0 | 5 | 67 |
| EURUSD | 25 | 28 | 5 | 5 | 15 | 20.0 | 0 | -74543 | 0 | 0 | 3 | 22 |
| USDJPY | 24 | 29 | 4 | 5 | 15 | 16.7 | 0 | -125404 | 1 | 0 | 2 | 21 |
| USDSGD | 24 | 29 | 1 | 9 | 14 | 4.2 | 0 | -244126 | 0 | 0 | 0 | 24 |
| GBPUSD | 0 | 53 | 0 | 0 | 0 | — | — | 0 | 0 | 0 | 0 | 0 |
| AUDUSD | 0 | 53 | 0 | 0 | 0 | — | — | 0 | 0 | 0 | 0 | 0 |
| USDCHF | 25 | 28 | 3 | 4 | 18 | 12.0 | 0 | -33103 | 0 | 0 | 4 | 21 |

| Group | Ship | Spread USD | Margin calls | Cuts | Restores | Fills | Total P&L USD | Median book DD USD | Max book DD USD | Median book DD % | Max book DD % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| All | prepared | 79356 | 9 | 42 | 42 | 93 | -5413370 | 235918 | 838514 | 21.7 | 62.6 |
| All | unprepared | 7497 | 10 | 0 | 0 | 10 | -4936193 | 243514 | 838514 | 22.4 | 62.6 |
| SGX | prepared | 60300 | 5 | 34 | 34 | 73 | -3801580 | 229580 | 838514 | 21.4 | 61.0 |
| SGX | unprepared | 2841 | 6 | 0 | 0 | 6 | -3357507 | 249737 | 838514 | 22.3 | 61.0 |
| EURUSD | prepared | 12948 | 3 | 11 | 11 | 25 | -2005549 | 222262 | 653800 | 20.3 | 56.5 |
| EURUSD | unprepared | 1769 | 3 | 0 | 0 | 3 | -1931005 | 228047 | 653800 | 20.7 | 57.3 |
| USDJPY | prepared | 10765 | 2 | 12 | 12 | 26 | -751765 | 351310 | 838514 | 26.9 | 61.0 |
| USDJPY | unprepared | 1071 | 3 | 0 | 0 | 3 | -626360 | 357903 | 838514 | 26.9 | 61.0 |
| USDSGD | prepared | 36587 | 0 | 11 | 11 | 22 | -1044267 | 162290 | 607048 | 15.8 | 53.3 |
| USDSGD | unprepared | 0 | 0 | 0 | 0 | 0 | -800141 | 172459 | 587218 | 16.6 | 51.5 |
| GBPUSD | prepared | 0 | 0 | 0 | 0 | 0 | 0 | — | — | — | — |
| GBPUSD | unprepared | 0 | 0 | 0 | 0 | 0 | 0 | — | — | — | — |
| AUDUSD | prepared | 0 | 0 | 0 | 0 | 0 | 0 | — | — | — | — |
| AUDUSD | unprepared | 0 | 0 | 0 | 0 | 0 | 0 | — | — | — | — |
| USDCHF | prepared | 19057 | 4 | 8 | 8 | 20 | -1611790 | 238059 | 822710 | 22.9 | 62.6 |
| USDCHF | unprepared | 4656 | 4 | 0 | 0 | 4 | -1578686 | 238059 | 822710 | 22.9 | 62.6 |

## EURUSD — every planned month

| Month | Status | Reason | Storms | Alarmed | Caught | Caught first | Ahead % | Minutes | First ahead % | First minutes | Obs days | False pairs | False episodes | False pairs/day | False episodes/day | Storm state % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2025-01 | unusable | insufficient monthly weekday coverage: 0.3903381642512077 < 0.5 | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-02 | usable | — | 4 | 3 | 0 | 0 | 25.1 | 6.0 | 29.1 | 13.0 | 16.87 | 5 | 5 | 0.3 | 0.3 | 1.89 |
| 2025-03 | usable | — | 0 | 0 | 0 | 0 | — | — | — | — | 18.2 | 5 | 5 | 0.27 | 0.27 | 1.68 |
| 2025-04 | usable | — | 2 | 1 | 1 | 1 | 100.0 | -3.0 | 100.0 | 337.0 | 21.95 | 4 | 4 | 0.18 | 0.18 | 1.54 |
| 2025-05 | usable | — | 2 | 2 | 1 | 1 | 36.5 | 8.0 | 39.1 | 12.0 | 18.97 | 2 | 2 | 0.11 | 0.11 | 1.32 |
| 2025-06 | usable | — | 1 | 1 | 0 | 0 | 42.1 | 10.0 | 41.3 | 14.0 | 18.95 | 2 | 2 | 0.11 | 0.11 | 1.19 |
| 2025-07 | usable | — | 3 | 2 | 1 | 1 | 56.5 | -3.0 | 45.2 | 15.5 | 22.94 | 2 | 2 | 0.09 | 0.09 | 1.46 |
| 2025-08 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-09 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-10 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-11 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-12 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |

Acquisition coverage and gap diagnostics (weekends and holidays are not filled):

| Month | Observed minutes | Warm-up | Weekday coverage | Missing-side bid / ask | Gaps >1m | Max gap min |
| --- | --- | --- | --- | --- | --- | --- |
| 2025-01 | 12928 | 4196 | 0.3903381642512077 | 11613 / 7063 | 35 | 7201.0 |
| 2025-02 | 24296 | 0 | 0.8436111111111111 | 0 / 4436 | 52 | 2883.0 |
| 2025-03 | 26207 | 0 | 0.8666335978835978 | 0 / 4139 | 52 | 4141.0 |
| 2025-04 | 31615 | 0 | 0.9979482323232324 | 0 / 0 | 48 | 2885.0 |
| 2025-05 | 27318 | 0 | 0.862310606060606 | 0 / 4138 | 37 | 5581.0 |
| 2025-06 | 27293 | 0 | 0.9025462962962963 | 3054 / 0 | 58 | 3061.0 |
| 2025-07 | 33040 | 0 | 0.9975845410628019 | 0 / 0 | 67 | 2885.0 |
| 2025-08 | — | — | — | — | — | — |
| 2025-09 | — | — | — | — | — | — |
| 2025-10 | — | — | — | — | — | — |
| 2025-11 | — | — | — | — | — | — |
| 2025-12 | — | — | — | — | — | — |

## USDJPY — every planned month

| Month | Status | Reason | Storms | Alarmed | Caught | Caught first | Ahead % | Minutes | First ahead % | First minutes | Obs days | False pairs | False episodes | False pairs/day | False episodes/day | Storm state % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2025-01 | unusable | insufficient monthly weekday coverage: 0.4797101449275362 < 0.5 | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-02 | usable | — | 1 | 1 | 0 | 0 | 16.9 | 6.0 | 16.4 | 16.0 | 15.86 | 2 | 2 | 0.13 | 0.13 | 0.81 |
| 2025-03 | usable | — | 0 | 0 | 0 | 0 | — | — | — | — | 17.24 | 3 | 3 | 0.17 | 0.17 | 0.99 |
| 2025-04 | usable | — | 2 | 2 | 2 | 2 | 79.5 | 2.0 | 83.5 | 5.5 | 21.86 | 1 | 1 | 0.05 | 0.05 | 0.92 |
| 2025-05 | usable | — | 1 | 0 | 0 | 0 | — | — | — | — | 15.95 | 2 | 2 | 0.13 | 0.13 | 0.65 |
| 2025-06 | usable | — | 1 | 1 | 0 | 0 | 43.4 | 10.0 | 41.1 | 14.0 | 18.94 | 3 | 3 | 0.16 | 0.16 | 1.25 |
| 2025-07 | usable | — | 3 | 2 | 0 | 0 | 14.5 | 8.5 | 14.5 | 16.0 | 22.88 | 4 | 4 | 0.17 | 0.17 | 1.17 |
| 2025-08 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-09 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-10 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-11 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-12 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |

Acquisition coverage and gap diagnostics (weekends and holidays are not filled):

| Month | Observed minutes | Warm-up | Weekday coverage | Missing-side bid / ask | Gaps >1m | Max gap min |
| --- | --- | --- | --- | --- | --- | --- |
| 2025-01 | 15888 | 4171 | 0.4797101449275362 | 11473 / 1428 | 46 | 4441.0 |
| 2025-02 | 22837 | 0 | 0.7929513888888889 | 2859 / 2985 | 50 | 2881.0 |
| 2025-03 | 24828 | 0 | 0.821031746031746 | 0 / 5393 | 109 | 7021.0 |
| 2025-04 | 31479 | 0 | 0.993655303030303 | 0 / 0 | 96 | 2883.0 |
| 2025-05 | 22962 | 0 | 0.7248106060606061 | 8434 / 0 | 56 | 14221.0 |
| 2025-06 | 27271 | 0 | 0.901818783068783 | 3033 / 0 | 58 | 3061.0 |
| 2025-07 | 32941 | 0 | 0.9945954106280194 | 0 / 0 | 117 | 2885.0 |
| 2025-08 | — | — | — | — | — | — |
| 2025-09 | — | — | — | — | — | — |
| 2025-10 | — | — | — | — | — | — |
| 2025-11 | — | — | — | — | — | — |
| 2025-12 | — | — | — | — | — | — |

## USDSGD — every planned month

| Month | Status | Reason | Storms | Alarmed | Caught | Caught first | Ahead % | Minutes | First ahead % | First minutes | Obs days | False pairs | False episodes | False pairs/day | False episodes/day | Storm state % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2025-01 | usable | — | 3 | 3 | 1 | 1 | 43.8 | 3.0 | 42.8 | 15.0 | 13.71 | 3 | 3 | 0.22 | 0.22 | 2.72 |
| 2025-02 | usable | — | 2 | 2 | 0 | 0 | 29.6 | 10.0 | 29.6 | 10.0 | 17.79 | 7 | 7 | 0.39 | 0.39 | 1.58 |
| 2025-03 | usable | — | 0 | 0 | 0 | 0 | — | — | — | — | 16.96 | 2 | 2 | 0.12 | 0.12 | 1.22 |
| 2025-04 | usable | — | 2 | 2 | 1 | 1 | 50.0 | 4.0 | 50.0 | 11.5 | 21.79 | 1 | 1 | 0.05 | 0.05 | 1.05 |
| 2025-05 | unusable | USDSGD_ask.csv: empty candle file | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-06 | usable | — | 0 | 0 | 0 | 0 | — | — | — | — | 16.87 | 3 | 3 | 0.18 | 0.18 | 1.13 |
| 2025-07 | usable | — | 2 | 2 | 1 | 1 | 50.0 | -14.0 | 50.0 | 5.0 | 22.82 | 1 | 1 | 0.04 | 0.04 | 0.93 |
| 2025-08 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-09 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-10 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-11 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-12 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |

Acquisition coverage and gap diagnostics (weekends and holidays are not filled):

| Month | Observed minutes | Warm-up | Weekday coverage | Missing-side bid / ask | Gaps >1m | Max gap min |
| --- | --- | --- | --- | --- | --- | --- |
| 2025-01 | 19747 | 2721 | 0.5962258454106281 | 4073 / 6030 | 97 | 7321.0 |
| 2025-02 | 25613 | 0 | 0.8893402777777778 | 0 / 2974 | 77 | 2881.0 |
| 2025-03 | 24429 | 0 | 0.8078373015873016 | 0 / 5740 | 94 | 7201.0 |
| 2025-04 | 31377 | 0 | 0.9904356060606061 | 0 / 0 | 118 | 2891.0 |
| 2025-05 | — | — | — | — | — | — |
| 2025-06 | 24290 | 0 | 0.8032407407407407 | 4260 / 1619 | 99 | 2881.0 |
| 2025-07 | 32865 | 0 | 0.9923007246376812 | 0 / 0 | 187 | 2881.0 |
| 2025-08 | — | — | — | — | — | — |
| 2025-09 | — | — | — | — | — | — |
| 2025-10 | — | — | — | — | — | — |
| 2025-11 | — | — | — | — | — | — |
| 2025-12 | — | — | — | — | — | — |

## GBPUSD — every planned month

| Month | Status | Reason | Storms | Alarmed | Caught | Caught first | Ahead % | Minutes | First ahead % | First minutes | Obs days | False pairs | False episodes | False pairs/day | False episodes/day | Storm state % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2025-01 | unusable | insufficient initial warm-up: 0 < 720 | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-02 | unusable | pair has insufficient initial warm-up; no inferred history | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-03 | unusable | pair has insufficient initial warm-up; no inferred history | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-04 | unusable | pair has insufficient initial warm-up; no inferred history | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-05 | unusable | insufficient monthly weekday coverage: 0.4512941919191919 < 0.5 | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-06 | unusable | GBPUSD_ask.csv: empty candle file | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-07 | unusable | pair has insufficient initial warm-up; no inferred history | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-08 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-09 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-10 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-11 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-12 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |

Acquisition coverage and gap diagnostics (weekends and holidays are not filled):

| Month | Observed minutes | Warm-up | Weekday coverage | Missing-side bid / ask | Gaps >1m | Max gap min |
| --- | --- | --- | --- | --- | --- | --- |
| 2025-01 | 24523 | 0 | 0.7404287439613526 | 6946 / 4305 | 55 | 2883.0 |
| 2025-02 | 24388 | 0 | 0.8468055555555556 | 0 / 4298 | 61 | 4321.0 |
| 2025-03 | 27402 | 0 | 0.9061507936507937 | 2862 / 0 | 93 | 2885.0 |
| 2025-04 | 31485 | 0 | 0.993844696969697 | 0 / 0 | 105 | 2886.0 |
| 2025-05 | 14297 | 0 | 0.4512941919191919 | 15573 / 1438 | 72 | 14401.0 |
| 2025-06 | — | — | — | — | — | — |
| 2025-07 | 24547 | 0 | 0.7411533816425121 | 8444 / 0 | 90 | 5585.0 |
| 2025-08 | — | — | — | — | — | — |
| 2025-09 | — | — | — | — | — | — |
| 2025-10 | — | — | — | — | — | — |
| 2025-11 | — | — | — | — | — | — |
| 2025-12 | — | — | — | — | — | — |

## AUDUSD — every planned month

| Month | Status | Reason | Storms | Alarmed | Caught | Caught first | Ahead % | Minutes | First ahead % | First minutes | Obs days | False pairs | False episodes | False pairs/day | False episodes/day | Storm state % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2025-01 | unusable | AUDUSD_ask.csv: empty candle file | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-02 | unusable | pair has insufficient initial warm-up; no inferred history | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-03 | unusable | pair has insufficient initial warm-up; no inferred history | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-04 | unusable | AUDUSD_ask.csv: empty candle file | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-05 | unusable | pair has insufficient initial warm-up; no inferred history | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-06 | unusable | pair has insufficient initial warm-up; no inferred history | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-07 | unusable | AUDUSD_ask.csv: empty candle file | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-08 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-09 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-10 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-11 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-12 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |

Acquisition coverage and gap diagnostics (weekends and holidays are not filled):

| Month | Observed minutes | Warm-up | Weekday coverage | Missing-side bid / ask | Gaps >1m | Max gap min |
| --- | --- | --- | --- | --- | --- | --- |
| 2025-01 | — | — | — | — | — | — |
| 2025-02 | 19948 | 0 | 0.6926388888888889 | 4391 / 4305 | 68 | 4441.0 |
| 2025-03 | 28832 | 0 | 0.9534391534391534 | 0 / 1434 | 113 | 2881.0 |
| 2025-04 | — | — | — | — | — | — |
| 2025-05 | 29588 | 0 | 0.9339646464646465 | 0 / 1742 | 78 | 3061.0 |
| 2025-06 | 28646 | 0 | 0.9472883597883598 | 0 / 1601 | 104 | 2883.0 |
| 2025-07 | — | — | — | — | — | — |
| 2025-08 | — | — | — | — | — | — |
| 2025-09 | — | — | — | — | — | — |
| 2025-10 | — | — | — | — | — | — |
| 2025-11 | — | — | — | — | — | — |
| 2025-12 | — | — | — | — | — | — |

## USDCHF — every planned month

| Month | Status | Reason | Storms | Alarmed | Caught | Caught first | Ahead % | Minutes | First ahead % | First minutes | Obs days | False pairs | False episodes | False pairs/day | False episodes/day | Storm state % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2025-01 | usable | — | 3 | 3 | 0 | 0 | 13.9 | 12.0 | 13.8 | 15.0 | 17.93 | 3 | 3 | 0.17 | 0.17 | 1.46 |
| 2025-02 | usable | — | 1 | 1 | 0 | 0 | 24.1 | 6.0 | 26.0 | 14.0 | 14.94 | 2 | 2 | 0.13 | 0.13 | 0.71 |
| 2025-03 | usable | — | 0 | 0 | 0 | 0 | — | — | — | — | 19.9 | 1 | 1 | 0.05 | 0.05 | 0.7 |
| 2025-04 | usable | — | 1 | 1 | 0 | 0 | 45.3 | 4.0 | 48.1 | 14.0 | 20.73 | 2 | 2 | 0.1 | 0.1 | 1.82 |
| 2025-05 | unusable | USDCHF_ask.csv: empty candle file | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-06 | usable | — | 1 | 1 | 1 | 1 | 56.0 | 10.0 | 55.2 | 11.0 | 17.91 | 3 | 3 | 0.17 | 0.17 | 1.83 |
| 2025-07 | usable | — | 3 | 2 | 1 | 1 | 57.7 | -8.0 | 58.4 | 4.5 | 21.91 | 0 | 0 | 0.0 | 0.0 | 0.66 |
| 2025-08 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-09 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-10 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-11 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| 2025-12 | not_completed_by_deadline | month not started before cutoff | — | — | — | — | — | — | — | — | — | — | — | — | — | — |

Acquisition coverage and gap diagnostics (weekends and holidays are not filled):

| Month | Observed minutes | Warm-up | Weekday coverage | Missing-side bid / ask | Gaps >1m | Max gap min |
| --- | --- | --- | --- | --- | --- | --- |
| 2025-01 | 25825 | 4176 | 0.7797403381642513 | 1544 / 2868 | 86 | 4321.0 |
| 2025-02 | 21511 | 0 | 0.7469097222222222 | 0 / 4300 | 69 | 5761.0 |
| 2025-03 | 28657 | 0 | 0.9476521164021164 | 1542 / 0 | 136 | 2885.0 |
| 2025-04 | 29857 | 0 | 0.9424558080808081 | 0 / 1602 | 108 | 3061.0 |
| 2025-05 | — | — | — | — | — | — |
| 2025-06 | 25788 | 0 | 0.8527777777777777 | 0 / 4484 | 80 | 4501.0 |
| 2025-07 | 31553 | 0 | 0.9526871980676328 | 0 / 1433 | 100 | 2883.0 |
| 2025-08 | — | — | — | — | — | — |
| 2025-09 | — | — | — | — | — | — |
| 2025-10 | — | — | — | — | — | — |
| 2025-11 | — | — | — | — | — | — |
| 2025-12 | — | — | — | — | — | — |

## Ten largest labelled storms in the completed 2025 interval

Ranked by absolute unrounded move_bp, then onset UTC and pair; no named-event substitutions.

| Pair | Storm | Onset UTC | First onset UTC | Move bp | Alarm UTC | Caught | Ahead % | Minutes | First ahead % | First minutes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| USDJPY | usdjpy-2025-04-09 | 2025-04-09T17:17:00+00:00 | 2025-04-09T17:10:00+00:00 | 170.3 | 2025-04-09 17:20 | yes | 65.6 | 3 | 73.6 | 10 |
| USDCHF | usdchf-2025-04-09 | 2025-04-09T17:19:00+00:00 | 2025-04-09T17:09:00+00:00 | 134.5 | 2025-04-09 17:23 | no | 45.3 | 4 | 48.1 | 14 |
| EURUSD | eurusd-2025-04-11 | 2025-04-11T00:17:00+00:00 | 2025-04-11T00:17:00+00:00 | 103.7 | — | no | — | — | — | — |
| USDJPY | usdjpy-2025-07-16 | 2025-07-16T15:02:00+00:00 | 2025-07-16T15:01:00+00:00 | -98.3 | 2025-07-16 15:17 | no | 13.7 | 15 | 12.9 | 16 |
| USDCHF | usdchf-2025-07-16 | 2025-07-16T15:15:00+00:00 | 2025-07-16T15:01:00+00:00 | -90.0 | 2025-07-16 14:55 | yes | 100.0 | -20 | 100.0 | -6 |
| USDJPY | usdjpy-2025-07-03 | 2025-07-03T12:29:00+00:00 | 2025-07-03T12:15:00+00:00 | 83.5 | 2025-07-03 12:31 | no | 15.3 | 2 | 16.0 | 16 |
| EURUSD | eurusd-2025-04-02 | 2025-04-02T20:17:00+00:00 | 2025-04-02T14:37:00+00:00 | -83.5 | 2025-04-02 20:14 | yes | 100.0 | -3 | 100.0 | 337 |
| EURUSD | eurusd-2025-07-16 | 2025-07-16T15:15:00+00:00 | 2025-07-16T14:42:00+00:00 | 82.0 | 2025-07-16 14:57 | yes | 100.0 | -18 | 76.4 | 15 |
| USDJPY | usdjpy-2025-04-02 | 2025-04-02T20:13:00+00:00 | 2025-04-02T20:13:00+00:00 | -67.0 | 2025-04-02 20:14 | yes | 93.3 | 1 | 93.3 | 1 |
| USDCHF | usdchf-2025-01-20 | 2025-01-20T13:19:00+00:00 | 2025-01-20T13:16:00+00:00 | -66.6 | 2025-01-20 13:31 | no | 27.2 | 12 | 28.2 | 15 |

## Every primary miss

Includes every caught=false storm: both absent alarms and alarms with less than half the peak-onset move ahead.

| Pair | Storm | Onset UTC | First onset UTC | Move bp | Alarm UTC | Caught | Ahead % | Minutes | First ahead % | First minutes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| USDCHF | usdchf-2025-01-06 | 2025-01-06T14:05:00+00:00 | 2025-01-06T14:01:00+00:00 | 53.1 | 2025-01-06 14:16 | no | 0.0 | 11 | 0.0 | 15 |
| USDSGD | usdsgd-2025-01-10 | 2025-01-10T13:19:00+00:00 | 2025-01-10T13:15:00+00:00 | 54.1 | 2025-01-10 13:30 | no | 15.9 | 11 | 16.6 | 15 |
| USDCHF | usdchf-2025-01-15 | 2025-01-15T13:17:00+00:00 | 2025-01-15T13:15:00+00:00 | -38.2 | 2025-01-15 13:31 | no | 13.9 | 14 | 13.8 | 16 |
| USDCHF | usdchf-2025-01-20 | 2025-01-20T13:19:00+00:00 | 2025-01-20T13:16:00+00:00 | -66.6 | 2025-01-20 13:31 | no | 27.2 | 12 | 28.2 | 15 |
| USDSGD | usdsgd-2025-01-21 | 2025-01-21T00:48:00+00:00 | 2025-01-21T00:37:00+00:00 | 46.5 | 2025-01-21 00:51 | no | 43.8 | 3 | 42.8 | 14 |
| EURUSD | eurusd-2025-02-07 | 2025-02-07T15:50:00+00:00 | 2025-02-07T15:42:00+00:00 | -51.3 | 2025-02-07 15:54 | no | 24.6 | 4 | 29.1 | 12 |
| USDSGD | usdsgd-2025-02-07 | 2025-02-07T15:50:00+00:00 | 2025-02-07T15:50:00+00:00 | 32.4 | 2025-02-07 15:54 | no | 28.3 | 4 | 28.3 | 4 |
| USDSGD | usdsgd-2025-02-12 | 2025-02-12T13:15:00+00:00 | 2025-02-12T13:15:00+00:00 | 39.6 | 2025-02-12 13:31 | no | 30.9 | 16 | 30.9 | 16 |
| EURUSD | eurusd-2025-02-12 | 2025-02-12T13:25:00+00:00 | 2025-02-12T13:15:00+00:00 | -47.7 | 2025-02-12 13:31 | no | 30.2 | 6 | 29.3 | 16 |
| USDCHF | usdchf-2025-02-12 | 2025-02-12T13:25:00+00:00 | 2025-02-12T13:17:00+00:00 | 38.2 | 2025-02-12 13:31 | no | 24.1 | 6 | 26.0 | 14 |
| USDJPY | usdjpy-2025-02-12 | 2025-02-12T13:25:00+00:00 | 2025-02-12T13:15:00+00:00 | 59.3 | 2025-02-12 13:31 | no | 16.9 | 6 | 16.4 | 16 |
| EURUSD | eurusd-2025-02-13 | 2025-02-13T18:28:00+00:00 | 2025-02-13T18:28:00+00:00 | -42.1 | 2025-02-13 18:41 | no | 25.1 | 13 | 25.1 | 13 |
| EURUSD | eurusd-2025-02-27 | 2025-02-27T13:42:00+00:00 | 2025-02-27T13:42:00+00:00 | -38.1 | — | no | — | — | — | — |
| USDCHF | usdchf-2025-04-09 | 2025-04-09T17:19:00+00:00 | 2025-04-09T17:09:00+00:00 | 134.5 | 2025-04-09 17:23 | no | 45.3 | 4 | 48.1 | 14 |
| USDSGD | usdsgd-2025-04-09 | 2025-04-09T17:31:00+00:00 | 2025-04-09T17:31:00+00:00 | -56.1 | 2025-04-09 17:46 | no | 0.0 | 15 | 0.0 | 15 |
| EURUSD | eurusd-2025-04-11 | 2025-04-11T00:17:00+00:00 | 2025-04-11T00:17:00+00:00 | 103.7 | — | no | — | — | — | — |
| USDJPY | usdjpy-2025-05-28 | 2025-05-28T00:54:00+00:00 | 2025-05-28T00:54:00+00:00 | 49.5 | — | no | — | — | — | — |
| EURUSD | eurusd-2025-05-28 | 2025-05-28T23:29:00+00:00 | 2025-05-28T23:23:00+00:00 | -52.8 | 2025-05-28 23:38 | no | 21.9 | 9 | 22.2 | 15 |
| EURUSD | eurusd-2025-06-11 | 2025-06-11T12:21:00+00:00 | 2025-06-11T12:17:00+00:00 | 45.8 | 2025-06-11 12:31 | no | 42.1 | 10 | 41.3 | 14 |
| USDJPY | usdjpy-2025-06-11 | 2025-06-11T12:21:00+00:00 | 2025-06-11T12:17:00+00:00 | -60.0 | 2025-06-11 12:31 | no | 43.4 | 10 | 41.1 | 14 |
| USDSGD | usdsgd-2025-07-03 | 2025-07-03T12:16:00+00:00 | 2025-07-03T12:16:00+00:00 | 34.4 | 2025-07-03 12:31 | no | 0.0 | 15 | 0.0 | 15 |
| EURUSD | eurusd-2025-07-03 | 2025-07-03T12:19:00+00:00 | 2025-07-03T12:15:00+00:00 | -53.8 | 2025-07-03 12:31 | no | 13.1 | 12 | 14.0 | 16 |
| USDCHF | usdchf-2025-07-03 | 2025-07-03T12:27:00+00:00 | 2025-07-03T12:16:00+00:00 | 53.4 | 2025-07-03 12:31 | no | 15.3 | 4 | 16.8 | 15 |
| USDJPY | usdjpy-2025-07-03 | 2025-07-03T12:29:00+00:00 | 2025-07-03T12:15:00+00:00 | 83.5 | 2025-07-03 12:31 | no | 15.3 | 2 | 16.0 | 16 |
| USDJPY | usdjpy-2025-07-16 | 2025-07-16T15:02:00+00:00 | 2025-07-16T15:01:00+00:00 | -98.3 | 2025-07-16 15:17 | no | 13.7 | 15 | 12.9 | 16 |
| EURUSD | eurusd-2025-07-30 | 2025-07-30T18:35:00+00:00 | 2025-07-30T18:34:00+00:00 | -62.6 | — | no | — | — | — | — |
| USDCHF | usdchf-2025-07-30 | 2025-07-30T18:35:00+00:00 | 2025-07-30T18:34:00+00:00 | 58.4 | — | no | — | — | — | — |
| USDJPY | usdjpy-2025-07-30 | 2025-07-30T18:35:00+00:00 | 2025-07-30T18:34:00+00:00 | 50.5 | — | no | — | — | — | — |

## Every independent pair-week

| Pair | From UTC | To UTC | Status | Reason | Carry-in alarm UTC | Difference USD | Helped | Margin outcome | Prepared spread USD | Unprepared spread USD | Prepared final equity | Unprepared final equity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD | 2025-01-01T00:00:00+00:00 | 2025-01-06T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| EURUSD | 2025-01-06T00:00:00+00:00 | 2025-01-13T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| EURUSD | 2025-01-13T00:00:00+00:00 | 2025-01-20T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| EURUSD | 2025-01-20T00:00:00+00:00 | 2025-01-27T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| EURUSD | 2025-01-27T00:00:00+00:00 | 2025-02-03T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| EURUSD | 2025-02-03T00:00:00+00:00 | 2025-02-10T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| EURUSD | 2025-02-10T00:00:00+00:00 | 2025-02-17T00:00:00+00:00 | usable | — | — | -20221 | no | neither | 946 | 0 | 635585 | 655806 |
| EURUSD | 2025-02-17T00:00:00+00:00 | 2025-02-24T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1026316 | 1026316 |
| EURUSD | 2025-02-24T00:00:00+00:00 | 2025-03-03T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1116108 | 1116108 |
| EURUSD | 2025-03-03T00:00:00+00:00 | 2025-03-10T00:00:00+00:00 | usable | — | — | 0 | no | both | 672 | 672 | 504510 | 504510 |
| EURUSD | 2025-03-10T00:00:00+00:00 | 2025-03-17T00:00:00+00:00 | usable | — | — | 3040 | yes | neither | 829 | 0 | 960669 | 957629 |
| EURUSD | 2025-03-17T00:00:00+00:00 | 2025-03-24T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1150573 | 1150573 |
| EURUSD | 2025-03-24T00:00:00+00:00 | 2025-03-31T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1019844 | 1019844 |
| EURUSD | 2025-03-31T00:00:00+00:00 | 2025-04-07T00:00:00+00:00 | usable | — | — | 14642 | yes | both | 2494 | 277 | 477836 | 463195 |
| EURUSD | 2025-04-07T00:00:00+00:00 | 2025-04-14T00:00:00+00:00 | usable | — | — | 0 | no | both | 820 | 820 | 504322 | 504322 |
| EURUSD | 2025-04-14T00:00:00+00:00 | 2025-04-21T00:00:00+00:00 | usable | — | — | 13880 | yes | neither | 1983 | 0 | 833567 | 819686 |
| EURUSD | 2025-04-21T00:00:00+00:00 | 2025-04-28T00:00:00+00:00 | usable | — | — | -393 | no | neither | 1048 | 0 | 1189326 | 1189719 |
| EURUSD | 2025-04-28T00:00:00+00:00 | 2025-05-05T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1046354 | 1046354 |
| EURUSD | 2025-05-05T00:00:00+00:00 | 2025-05-12T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1161228 | 1161228 |
| EURUSD | 2025-05-12T00:00:00+00:00 | 2025-05-19T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 835096 | 835096 |
| EURUSD | 2025-05-19T00:00:00+00:00 | 2025-05-26T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 667616 | 667616 |
| EURUSD | 2025-05-26T00:00:00+00:00 | 2025-06-02T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1046750 | 1046750 |
| EURUSD | 2025-06-02T00:00:00+00:00 | 2025-06-09T00:00:00+00:00 | usable | — | — | -41214 | no | neither | 528 | 0 | 887982 | 929196 |
| EURUSD | 2025-06-09T00:00:00+00:00 | 2025-06-16T00:00:00+00:00 | usable | — | — | 7232 | yes | neither | 855 | 0 | 778610 | 771377 |
| EURUSD | 2025-06-16T00:00:00+00:00 | 2025-06-23T00:00:00+00:00 | usable | — | — | -3640 | no | neither | 780 | 0 | 1062835 | 1066475 |
| EURUSD | 2025-06-23T00:00:00+00:00 | 2025-06-30T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 612121 | 612121 |
| EURUSD | 2025-06-30T00:00:00+00:00 | 2025-07-07T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 910469 | 910469 |
| EURUSD | 2025-07-07T00:00:00+00:00 | 2025-07-14T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1165028 | 1165028 |
| EURUSD | 2025-07-14T00:00:00+00:00 | 2025-07-21T00:00:00+00:00 | usable | — | — | -51609 | no | neither | 1220 | 0 | 1041253 | 1092863 |
| EURUSD | 2025-07-21T00:00:00+00:00 | 2025-07-28T00:00:00+00:00 | usable | — | — | 3740 | yes | neither | 774 | 0 | 788182 | 784441 |
| EURUSD | 2025-07-28T00:00:00+00:00 | 2025-08-01T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1572272 | 1572272 |
| EURUSD | 2025-08-04T00:00:00+00:00 | 2025-08-11T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-08-11T00:00:00+00:00 | 2025-08-18T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-08-18T00:00:00+00:00 | 2025-08-25T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-08-25T00:00:00+00:00 | 2025-09-01T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-09-01T00:00:00+00:00 | 2025-09-08T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-09-08T00:00:00+00:00 | 2025-09-15T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-09-15T00:00:00+00:00 | 2025-09-22T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-09-22T00:00:00+00:00 | 2025-09-29T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-09-29T00:00:00+00:00 | 2025-10-06T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-10-06T00:00:00+00:00 | 2025-10-13T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-10-13T00:00:00+00:00 | 2025-10-20T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-10-20T00:00:00+00:00 | 2025-10-27T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-10-27T00:00:00+00:00 | 2025-11-03T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-11-03T00:00:00+00:00 | 2025-11-10T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-11-10T00:00:00+00:00 | 2025-11-17T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-11-17T00:00:00+00:00 | 2025-11-24T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-11-24T00:00:00+00:00 | 2025-12-01T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-12-01T00:00:00+00:00 | 2025-12-08T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-12-08T00:00:00+00:00 | 2025-12-15T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-12-15T00:00:00+00:00 | 2025-12-22T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-12-22T00:00:00+00:00 | 2025-12-29T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| EURUSD | 2025-12-29T00:00:00+00:00 | 2026-01-01T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-01-01T00:00:00+00:00 | 2025-01-06T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDJPY | 2025-01-06T00:00:00+00:00 | 2025-01-13T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDJPY | 2025-01-13T00:00:00+00:00 | 2025-01-20T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDJPY | 2025-01-20T00:00:00+00:00 | 2025-01-27T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDJPY | 2025-01-27T00:00:00+00:00 | 2025-02-03T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDJPY | 2025-02-03T00:00:00+00:00 | 2025-02-10T00:00:00+00:00 | usable | — | — | 0 | no | both | 595 | 595 | 486409 | 486409 |
| USDJPY | 2025-02-10T00:00:00+00:00 | 2025-02-17T00:00:00+00:00 | usable | — | — | 15196 | yes | neither | 640 | 0 | 1036247 | 1021051 |
| USDJPY | 2025-02-17T00:00:00+00:00 | 2025-02-24T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 652688 | 652688 |
| USDJPY | 2025-02-24T00:00:00+00:00 | 2025-03-03T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1189774 | 1189774 |
| USDJPY | 2025-03-03T00:00:00+00:00 | 2025-03-10T00:00:00+00:00 | usable | — | — | 97623 | yes | avoided | 1765 | 340 | 593977 | 496354 |
| USDJPY | 2025-03-10T00:00:00+00:00 | 2025-03-17T00:00:00+00:00 | usable | — | — | 18875 | yes | neither | 1169 | 0 | 1151979 | 1133104 |
| USDJPY | 2025-03-17T00:00:00+00:00 | 2025-03-24T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1151472 | 1151472 |
| USDJPY | 2025-03-24T00:00:00+00:00 | 2025-03-31T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDJPY | 2025-03-31T00:00:00+00:00 | 2025-04-07T00:00:00+00:00 | usable | — | — | 5290 | yes | both | 1889 | 137 | 499467 | 494177 |
| USDJPY | 2025-04-07T00:00:00+00:00 | 2025-04-14T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 760186 | 760186 |
| USDJPY | 2025-04-14T00:00:00+00:00 | 2025-04-21T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 721878 | 721878 |
| USDJPY | 2025-04-21T00:00:00+00:00 | 2025-04-28T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1332978 | 1332978 |
| USDJPY | 2025-04-28T00:00:00+00:00 | 2025-05-05T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1225432 | 1225432 |
| USDJPY | 2025-05-05T00:00:00+00:00 | 2025-05-12T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDJPY | 2025-05-12T00:00:00+00:00 | 2025-05-19T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 918616 | 918616 |
| USDJPY | 2025-05-19T00:00:00+00:00 | 2025-05-26T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 656090 | 656090 |
| USDJPY | 2025-05-26T00:00:00+00:00 | 2025-06-02T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1141381 | 1141381 |
| USDJPY | 2025-06-02T00:00:00+00:00 | 2025-06-09T00:00:00+00:00 | usable | — | — | -69373 | no | neither | 1932 | 0 | 1085043 | 1154416 |
| USDJPY | 2025-06-09T00:00:00+00:00 | 2025-06-16T00:00:00+00:00 | usable | — | — | -14422 | no | neither | 622 | 0 | 970568 | 984990 |
| USDJPY | 2025-06-16T00:00:00+00:00 | 2025-06-23T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1228296 | 1228296 |
| USDJPY | 2025-06-23T00:00:00+00:00 | 2025-06-30T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 767761 | 767761 |
| USDJPY | 2025-06-30T00:00:00+00:00 | 2025-07-07T00:00:00+00:00 | usable | — | — | -27615 | no | neither | 469 | 0 | 967610 | 995225 |
| USDJPY | 2025-07-07T00:00:00+00:00 | 2025-07-14T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1384328 | 1384328 |
| USDJPY | 2025-07-14T00:00:00+00:00 | 2025-07-21T00:00:00+00:00 | usable | — | — | -100535 | no | neither | 559 | 0 | 1058839 | 1159374 |
| USDJPY | 2025-07-21T00:00:00+00:00 | 2025-07-28T00:00:00+00:00 | usable | — | — | -50445 | no | neither | 1126 | 0 | 863011 | 913456 |
| USDJPY | 2025-07-28T00:00:00+00:00 | 2025-08-01T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1404208 | 1404208 |
| USDJPY | 2025-08-04T00:00:00+00:00 | 2025-08-11T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-08-11T00:00:00+00:00 | 2025-08-18T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-08-18T00:00:00+00:00 | 2025-08-25T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-08-25T00:00:00+00:00 | 2025-09-01T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-09-01T00:00:00+00:00 | 2025-09-08T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-09-08T00:00:00+00:00 | 2025-09-15T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-09-15T00:00:00+00:00 | 2025-09-22T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-09-22T00:00:00+00:00 | 2025-09-29T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-09-29T00:00:00+00:00 | 2025-10-06T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-10-06T00:00:00+00:00 | 2025-10-13T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-10-13T00:00:00+00:00 | 2025-10-20T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-10-20T00:00:00+00:00 | 2025-10-27T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-10-27T00:00:00+00:00 | 2025-11-03T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-11-03T00:00:00+00:00 | 2025-11-10T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-11-10T00:00:00+00:00 | 2025-11-17T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-11-17T00:00:00+00:00 | 2025-11-24T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-11-24T00:00:00+00:00 | 2025-12-01T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-12-01T00:00:00+00:00 | 2025-12-08T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-12-08T00:00:00+00:00 | 2025-12-15T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-12-15T00:00:00+00:00 | 2025-12-22T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-12-22T00:00:00+00:00 | 2025-12-29T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDJPY | 2025-12-29T00:00:00+00:00 | 2026-01-01T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-01-01T00:00:00+00:00 | 2025-01-06T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDSGD | 2025-01-06T00:00:00+00:00 | 2025-01-13T00:00:00+00:00 | usable | — | — | 46811 | yes | neither | 2148 | 0 | 1055196 | 1008385 |
| USDSGD | 2025-01-13T00:00:00+00:00 | 2025-01-20T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDSGD | 2025-01-20T00:00:00+00:00 | 2025-01-27T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 901440 | 901440 |
| USDSGD | 2025-01-27T00:00:00+00:00 | 2025-02-03T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1053622 | 1053622 |
| USDSGD | 2025-02-03T00:00:00+00:00 | 2025-02-10T00:00:00+00:00 | usable | — | — | -29399 | no | neither | 1921 | 0 | 806071 | 835470 |
| USDSGD | 2025-02-10T00:00:00+00:00 | 2025-02-17T00:00:00+00:00 | usable | — | — | -13997 | no | neither | 1996 | 0 | 725474 | 739471 |
| USDSGD | 2025-02-17T00:00:00+00:00 | 2025-02-24T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 947980 | 947980 |
| USDSGD | 2025-02-24T00:00:00+00:00 | 2025-03-03T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1206700 | 1206700 |
| USDSGD | 2025-03-03T00:00:00+00:00 | 2025-03-10T00:00:00+00:00 | usable | — | — | -18500 | no | neither | 2087 | 0 | 676853 | 695353 |
| USDSGD | 2025-03-10T00:00:00+00:00 | 2025-03-17T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1056313 | 1056313 |
| USDSGD | 2025-03-17T00:00:00+00:00 | 2025-03-24T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1021425 | 1021425 |
| USDSGD | 2025-03-24T00:00:00+00:00 | 2025-03-31T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDSGD | 2025-03-31T00:00:00+00:00 | 2025-04-07T00:00:00+00:00 | usable | — | — | -97906 | no | neither | 3398 | 0 | 962464 | 1060370 |
| USDSGD | 2025-04-07T00:00:00+00:00 | 2025-04-14T00:00:00+00:00 | usable | — | — | -19767 | no | neither | 3581 | 0 | 597689 | 617456 |
| USDSGD | 2025-04-14T00:00:00+00:00 | 2025-04-21T00:00:00+00:00 | usable | — | — | -8605 | no | neither | 12818 | 0 | 840244 | 848849 |
| USDSGD | 2025-04-21T00:00:00+00:00 | 2025-04-28T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1127939 | 1127939 |
| USDSGD | 2025-04-28T00:00:00+00:00 | 2025-05-05T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 853888 | 853888 |
| USDSGD | 2025-05-05T00:00:00+00:00 | 2025-05-12T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDSGD | 2025-05-12T00:00:00+00:00 | 2025-05-19T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDSGD | 2025-05-19T00:00:00+00:00 | 2025-05-26T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDSGD | 2025-05-26T00:00:00+00:00 | 2025-06-02T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDSGD | 2025-06-02T00:00:00+00:00 | 2025-06-09T00:00:00+00:00 | usable | — | — | -43423 | no | neither | 2273 | 0 | 948583 | 992006 |
| USDSGD | 2025-06-09T00:00:00+00:00 | 2025-06-16T00:00:00+00:00 | usable | — | — | -19411 | no | neither | 2394 | 0 | 892110 | 911521 |
| USDSGD | 2025-06-16T00:00:00+00:00 | 2025-06-23T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1078731 | 1078731 |
| USDSGD | 2025-06-23T00:00:00+00:00 | 2025-06-30T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 821203 | 821203 |
| USDSGD | 2025-06-30T00:00:00+00:00 | 2025-07-07T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1051088 | 1051088 |
| USDSGD | 2025-07-07T00:00:00+00:00 | 2025-07-14T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1094032 | 1094032 |
| USDSGD | 2025-07-14T00:00:00+00:00 | 2025-07-21T00:00:00+00:00 | usable | — | — | -39928 | no | neither | 3972 | 0 | 1031834 | 1071762 |
| USDSGD | 2025-07-21T00:00:00+00:00 | 2025-07-28T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 940360 | 940360 |
| USDSGD | 2025-07-28T00:00:00+00:00 | 2025-08-01T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1264497 | 1264497 |
| USDSGD | 2025-08-04T00:00:00+00:00 | 2025-08-11T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-08-11T00:00:00+00:00 | 2025-08-18T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-08-18T00:00:00+00:00 | 2025-08-25T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-08-25T00:00:00+00:00 | 2025-09-01T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-09-01T00:00:00+00:00 | 2025-09-08T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-09-08T00:00:00+00:00 | 2025-09-15T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-09-15T00:00:00+00:00 | 2025-09-22T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-09-22T00:00:00+00:00 | 2025-09-29T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-09-29T00:00:00+00:00 | 2025-10-06T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-10-06T00:00:00+00:00 | 2025-10-13T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-10-13T00:00:00+00:00 | 2025-10-20T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-10-20T00:00:00+00:00 | 2025-10-27T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-10-27T00:00:00+00:00 | 2025-11-03T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-11-03T00:00:00+00:00 | 2025-11-10T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-11-10T00:00:00+00:00 | 2025-11-17T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-11-17T00:00:00+00:00 | 2025-11-24T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-11-24T00:00:00+00:00 | 2025-12-01T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-12-01T00:00:00+00:00 | 2025-12-08T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-12-08T00:00:00+00:00 | 2025-12-15T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-12-15T00:00:00+00:00 | 2025-12-22T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-12-22T00:00:00+00:00 | 2025-12-29T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDSGD | 2025-12-29T00:00:00+00:00 | 2026-01-01T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-01-01T00:00:00+00:00 | 2025-01-06T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-01-06T00:00:00+00:00 | 2025-01-13T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-01-13T00:00:00+00:00 | 2025-01-20T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-01-20T00:00:00+00:00 | 2025-01-27T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-01-27T00:00:00+00:00 | 2025-02-03T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-02-03T00:00:00+00:00 | 2025-02-10T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-02-10T00:00:00+00:00 | 2025-02-17T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-02-17T00:00:00+00:00 | 2025-02-24T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-02-24T00:00:00+00:00 | 2025-03-03T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-03-03T00:00:00+00:00 | 2025-03-10T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-03-10T00:00:00+00:00 | 2025-03-17T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-03-17T00:00:00+00:00 | 2025-03-24T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-03-24T00:00:00+00:00 | 2025-03-31T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-03-31T00:00:00+00:00 | 2025-04-07T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-04-07T00:00:00+00:00 | 2025-04-14T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-04-14T00:00:00+00:00 | 2025-04-21T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-04-21T00:00:00+00:00 | 2025-04-28T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-04-28T00:00:00+00:00 | 2025-05-05T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-05-05T00:00:00+00:00 | 2025-05-12T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-05-12T00:00:00+00:00 | 2025-05-19T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-05-19T00:00:00+00:00 | 2025-05-26T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-05-26T00:00:00+00:00 | 2025-06-02T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-06-02T00:00:00+00:00 | 2025-06-09T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-06-09T00:00:00+00:00 | 2025-06-16T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-06-16T00:00:00+00:00 | 2025-06-23T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-06-23T00:00:00+00:00 | 2025-06-30T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-06-30T00:00:00+00:00 | 2025-07-07T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-07-07T00:00:00+00:00 | 2025-07-14T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-07-14T00:00:00+00:00 | 2025-07-21T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-07-21T00:00:00+00:00 | 2025-07-28T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-07-28T00:00:00+00:00 | 2025-08-01T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-08-04T00:00:00+00:00 | 2025-08-11T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-08-11T00:00:00+00:00 | 2025-08-18T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-08-18T00:00:00+00:00 | 2025-08-25T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-08-25T00:00:00+00:00 | 2025-09-01T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-09-01T00:00:00+00:00 | 2025-09-08T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-09-08T00:00:00+00:00 | 2025-09-15T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-09-15T00:00:00+00:00 | 2025-09-22T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-09-22T00:00:00+00:00 | 2025-09-29T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-09-29T00:00:00+00:00 | 2025-10-06T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-10-06T00:00:00+00:00 | 2025-10-13T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-10-13T00:00:00+00:00 | 2025-10-20T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-10-20T00:00:00+00:00 | 2025-10-27T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-10-27T00:00:00+00:00 | 2025-11-03T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-11-03T00:00:00+00:00 | 2025-11-10T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-11-10T00:00:00+00:00 | 2025-11-17T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-11-17T00:00:00+00:00 | 2025-11-24T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-11-24T00:00:00+00:00 | 2025-12-01T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-12-01T00:00:00+00:00 | 2025-12-08T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-12-08T00:00:00+00:00 | 2025-12-15T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-12-15T00:00:00+00:00 | 2025-12-22T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-12-22T00:00:00+00:00 | 2025-12-29T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| GBPUSD | 2025-12-29T00:00:00+00:00 | 2026-01-01T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-01-01T00:00:00+00:00 | 2025-01-06T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-01-06T00:00:00+00:00 | 2025-01-13T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-01-13T00:00:00+00:00 | 2025-01-20T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-01-20T00:00:00+00:00 | 2025-01-27T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-01-27T00:00:00+00:00 | 2025-02-03T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-02-03T00:00:00+00:00 | 2025-02-10T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-02-10T00:00:00+00:00 | 2025-02-17T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-02-17T00:00:00+00:00 | 2025-02-24T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-02-24T00:00:00+00:00 | 2025-03-03T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-03-03T00:00:00+00:00 | 2025-03-10T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-03-10T00:00:00+00:00 | 2025-03-17T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-03-17T00:00:00+00:00 | 2025-03-24T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-03-24T00:00:00+00:00 | 2025-03-31T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-03-31T00:00:00+00:00 | 2025-04-07T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-04-07T00:00:00+00:00 | 2025-04-14T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-04-14T00:00:00+00:00 | 2025-04-21T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-04-21T00:00:00+00:00 | 2025-04-28T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-04-28T00:00:00+00:00 | 2025-05-05T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-05-05T00:00:00+00:00 | 2025-05-12T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-05-12T00:00:00+00:00 | 2025-05-19T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-05-19T00:00:00+00:00 | 2025-05-26T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-05-26T00:00:00+00:00 | 2025-06-02T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-06-02T00:00:00+00:00 | 2025-06-09T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-06-09T00:00:00+00:00 | 2025-06-16T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-06-16T00:00:00+00:00 | 2025-06-23T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-06-23T00:00:00+00:00 | 2025-06-30T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-06-30T00:00:00+00:00 | 2025-07-07T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-07-07T00:00:00+00:00 | 2025-07-14T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-07-14T00:00:00+00:00 | 2025-07-21T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-07-21T00:00:00+00:00 | 2025-07-28T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-07-28T00:00:00+00:00 | 2025-08-01T00:00:00+00:00 | unavailable | pair lacks registered initial warm-up/data | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-08-04T00:00:00+00:00 | 2025-08-11T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-08-11T00:00:00+00:00 | 2025-08-18T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-08-18T00:00:00+00:00 | 2025-08-25T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-08-25T00:00:00+00:00 | 2025-09-01T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-09-01T00:00:00+00:00 | 2025-09-08T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-09-08T00:00:00+00:00 | 2025-09-15T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-09-15T00:00:00+00:00 | 2025-09-22T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-09-22T00:00:00+00:00 | 2025-09-29T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-09-29T00:00:00+00:00 | 2025-10-06T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-10-06T00:00:00+00:00 | 2025-10-13T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-10-13T00:00:00+00:00 | 2025-10-20T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-10-20T00:00:00+00:00 | 2025-10-27T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-10-27T00:00:00+00:00 | 2025-11-03T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-11-03T00:00:00+00:00 | 2025-11-10T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-11-10T00:00:00+00:00 | 2025-11-17T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-11-17T00:00:00+00:00 | 2025-11-24T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-11-24T00:00:00+00:00 | 2025-12-01T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-12-01T00:00:00+00:00 | 2025-12-08T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-12-08T00:00:00+00:00 | 2025-12-15T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-12-15T00:00:00+00:00 | 2025-12-22T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-12-22T00:00:00+00:00 | 2025-12-29T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| AUDUSD | 2025-12-29T00:00:00+00:00 | 2026-01-01T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-01-01T00:00:00+00:00 | 2025-01-06T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDCHF | 2025-01-06T00:00:00+00:00 | 2025-01-13T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1054051 | 1054051 |
| USDCHF | 2025-01-13T00:00:00+00:00 | 2025-01-20T00:00:00+00:00 | usable | — | — | -26243 | no | neither | 2144 | 0 | 921708 | 947951 |
| USDCHF | 2025-01-20T00:00:00+00:00 | 2025-01-27T00:00:00+00:00 | usable | — | — | 26960 | yes | neither | 3136 | 0 | 857921 | 830961 |
| USDCHF | 2025-01-27T00:00:00+00:00 | 2025-02-03T00:00:00+00:00 | usable | — | — | -1475 | no | neither | 1819 | 0 | 1175436 | 1176911 |
| USDCHF | 2025-02-03T00:00:00+00:00 | 2025-02-10T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDCHF | 2025-02-10T00:00:00+00:00 | 2025-02-17T00:00:00+00:00 | usable | — | — | -9501 | no | neither | 1479 | 0 | 745815 | 755316 |
| USDCHF | 2025-02-17T00:00:00+00:00 | 2025-02-24T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 967502 | 967502 |
| USDCHF | 2025-02-24T00:00:00+00:00 | 2025-03-03T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1124363 | 1124363 |
| USDCHF | 2025-03-03T00:00:00+00:00 | 2025-03-10T00:00:00+00:00 | usable | — | — | 0 | no | both | 1022 | 1022 | 497715 | 497715 |
| USDCHF | 2025-03-10T00:00:00+00:00 | 2025-03-17T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1152345 | 1152345 |
| USDCHF | 2025-03-17T00:00:00+00:00 | 2025-03-24T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 977461 | 977461 |
| USDCHF | 2025-03-24T00:00:00+00:00 | 2025-03-31T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 949712 | 949712 |
| USDCHF | 2025-03-31T00:00:00+00:00 | 2025-04-07T00:00:00+00:00 | usable | — | — | 0 | no | both | 931 | 931 | 497829 | 497829 |
| USDCHF | 2025-04-07T00:00:00+00:00 | 2025-04-14T00:00:00+00:00 | usable | — | — | 0 | no | both | 1324 | 1324 | 491129 | 491129 |
| USDCHF | 2025-04-14T00:00:00+00:00 | 2025-04-21T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 871755 | 871755 |
| USDCHF | 2025-04-21T00:00:00+00:00 | 2025-04-28T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1447081 | 1447081 |
| USDCHF | 2025-04-28T00:00:00+00:00 | 2025-05-05T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 940687 | 940687 |
| USDCHF | 2025-05-05T00:00:00+00:00 | 2025-05-12T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDCHF | 2025-05-12T00:00:00+00:00 | 2025-05-19T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDCHF | 2025-05-19T00:00:00+00:00 | 2025-05-26T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDCHF | 2025-05-26T00:00:00+00:00 | 2025-06-02T00:00:00+00:00 | unavailable | weekly coverage below registered minimum (2 bars and 50% weekday minutes) | — | — | — | — | — | — | — | — |
| USDCHF | 2025-06-02T00:00:00+00:00 | 2025-06-09T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1004500 | 1004500 |
| USDCHF | 2025-06-09T00:00:00+00:00 | 2025-06-16T00:00:00+00:00 | usable | — | — | 7575 | yes | neither | 1463 | 0 | 772821 | 765246 |
| USDCHF | 2025-06-16T00:00:00+00:00 | 2025-06-23T00:00:00+00:00 | usable | — | — | 40718 | yes | neither | 2294 | 0 | 1135850 | 1095132 |
| USDCHF | 2025-06-23T00:00:00+00:00 | 2025-06-30T00:00:00+00:00 | usable | — | — | 0 | no | both | 1380 | 1380 | 489492 | 489492 |
| USDCHF | 2025-06-30T00:00:00+00:00 | 2025-07-07T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 892217 | 892217 |
| USDCHF | 2025-07-07T00:00:00+00:00 | 2025-07-14T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1065513 | 1065513 |
| USDCHF | 2025-07-14T00:00:00+00:00 | 2025-07-21T00:00:00+00:00 | usable | — | — | -71138 | no | neither | 2067 | 0 | 1040935 | 1112073 |
| USDCHF | 2025-07-21T00:00:00+00:00 | 2025-07-28T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 854676 | 854676 |
| USDCHF | 2025-07-28T00:00:00+00:00 | 2025-08-01T00:00:00+00:00 | usable | — | — | 0 | no | neither | 0 | 0 | 1459697 | 1459697 |
| USDCHF | 2025-08-04T00:00:00+00:00 | 2025-08-11T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-08-11T00:00:00+00:00 | 2025-08-18T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-08-18T00:00:00+00:00 | 2025-08-25T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-08-25T00:00:00+00:00 | 2025-09-01T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-09-01T00:00:00+00:00 | 2025-09-08T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-09-08T00:00:00+00:00 | 2025-09-15T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-09-15T00:00:00+00:00 | 2025-09-22T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-09-22T00:00:00+00:00 | 2025-09-29T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-09-29T00:00:00+00:00 | 2025-10-06T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-10-06T00:00:00+00:00 | 2025-10-13T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-10-13T00:00:00+00:00 | 2025-10-20T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-10-20T00:00:00+00:00 | 2025-10-27T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-10-27T00:00:00+00:00 | 2025-11-03T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-11-03T00:00:00+00:00 | 2025-11-10T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-11-10T00:00:00+00:00 | 2025-11-17T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-11-17T00:00:00+00:00 | 2025-11-24T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-11-24T00:00:00+00:00 | 2025-12-01T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-12-01T00:00:00+00:00 | 2025-12-08T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-12-08T00:00:00+00:00 | 2025-12-15T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-12-15T00:00:00+00:00 | 2025-12-22T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-12-22T00:00:00+00:00 | 2025-12-29T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |
| USDCHF | 2025-12-29T00:00:00+00:00 | 2026-01-01T00:00:00+00:00 | not_completed_by_deadline | outside selected chronological prefix | — | — | — | — | — | — | — | — |

## Strengths and limits

Across 24 usable pair-months, the frozen detector alarmed on 32 of 38 storms and caught 10 with at least half the move ahead. It produced 49 false alert episodes over 146.07 observed days, and every labelled miss remains listed; missing source intervals can conceal unlabelled storms. Following the alarms helped in 13 of 98 usable independent pair-weeks, with median weekly difference $0 and total difference $-477177; spread costs and both-sided margin-call outcomes are included. The planned June 2025 EURUSD, USDJPY and GBPUSD series overlap registration 1; June lies in the selected prefix and is not newly unseen evidence. This frozen historical evaluation measures detection and synthetic book outcomes, not prospective prediction of unscheduled prices.

Full exact results, every labelled storm/false alarm, every weekly fill, and raw/parquet/source hashes are in `results-2.json`. Recompute both registrations with `cd backend && python -m storm.oos.run --verify`, using the recorded runtime and local acquisition directories.
