# Chip-sector frozen detector results

Status: **complete**. Base `3625e41f019551720b4c0e3f860aa48c9652d801`; preregistration `573ec7a318f248a1d70e320b3d4702c0bc9bda7c`.

The frozen detector caught 6 of 19 storms across the thirteen new tickers, with 47 false pair alerts over 20 observed trading dates (2.35 per trading day). NVDA is reported separately because it was used to build the equity path. Yahoo served more history than the approximate seven-day expectation, so the registered full-retention probe includes October and the three largest new moves occur there. The results include misses and zero-storm tickers, and do not establish advance price prediction.

## Full served window: per ticker

Rates use distinct ET trading dates with bars; pooled dates are a union, not ticker-days. Medians include alarmed storms only and use unrounded classifications.

| Ticker | Role | Bars | Days | Storms | Alarmed | Caught | False alerts | False/day | Ahead median % | Alarm median min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NVDA | in-sample | 18,467 | 20 | 2 | 1 | 1 | 6 | 0.30 | 100.00 | -16.00 |
| AMD | new | 16,668 | 20 | 3 | 2 | 1 | 3 | 0.15 | 40.94 | 12.50 |
| AVGO | new | 16,184 | 20 | 1 | 0 | 0 | 4 | 0.20 | — | — |
| TSM | new | 16,275 | 20 | 2 | 2 | 0 | 9 | 0.45 | 1.65 | 1.00 |
| MU | new | 18,597 | 20 | 3 | 3 | 1 | 4 | 0.20 | 49.83 | 8.00 |
| ARM | new | 11,785 | 20 | 1 | 1 | 1 | 1 | 0.05 | 59.74 | 6.00 |
| SMCI | new | 16,114 | 20 | 3 | 2 | 1 | 4 | 0.20 | 36.15 | 7.50 |
| INTC | new | 18,648 | 20 | 1 | 1 | 0 | 4 | 0.20 | 24.62 | 10.00 |
| QCOM | new | 10,346 | 20 | 1 | 1 | 0 | 1 | 0.05 | 0.00 | 12.00 |
| MRVL | new | 15,867 | 20 | 1 | 1 | 0 | 3 | 0.15 | 7.84 | 10.00 |
| AMAT | new | 11,610 | 20 | 0 | 0 | 0 | 2 | 0.10 | — | — |
| LRCX | new | 11,452 | 20 | 1 | 1 | 1 | 1 | 0.05 | 54.55 | 5.00 |
| SMH | new | 13,748 | 20 | 1 | 1 | 0 | 3 | 0.15 | 25.80 | 12.00 |
| SOXX | new | 16,187 | 20 | 1 | 1 | 1 | 8 | 0.40 | 61.49 | 11.00 |

## Pooled metrics

| Pool | Storms | Alarmed | Caught | First-onset caught | Detections | False | Days | False/day | False episodes/day | Ahead median % | Alarm median min | Storm-state % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| new_tickers | 19 | 16 | 6 | 7 | 63 | 47 | 20 | 2.35 | 1.75 | 25.21 | 10.00 | 3.85 |
| nvda_in_sample | 2 | 1 | 1 | 1 | 7 | 6 | 20 | 0.30 | 0.30 | 100.00 | -16.00 | 2.18 |
| all_descriptive | 21 | 17 | 7 | 8 | 70 | 53 | 20 | 2.65 | 1.90 | 25.80 | 10.00 | 3.71 |

| Pool | Observed days (union minutes / 1,440) | False/observed day | Episodes/observed day | First-onset ahead median % | First-onset alarm median min |
| --- | --- | --- | --- | --- | --- |
| new_tickers | 13.22 | 3.56 | 2.65 | 36.31 | 14.00 |
| nvda_in_sample | 12.82 | 0.47 | 0.47 | 100.00 | -16.00 |
| all_descriptive | 13.22 | 4.01 | 2.87 | 46.51 | 14.00 |

## Requested Nvidia shock week, November 9–13

Descriptive slice of the sole full-history run, with its original alarm/label context; no retuning or detector restart.

| Ticker/pool | Storms | Alarmed | Caught | Detections | False | Days | False/day |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NVDA | 2 | 1 | 1 | 1 | 0 | 5 | 0.00 |
| AMD | 0 | 0 | 0 | 0 | 0 | 5 | 0.00 |
| AVGO | 0 | 0 | 0 | 1 | 1 | 5 | 0.20 |
| TSM | 0 | 0 | 0 | 1 | 1 | 5 | 0.20 |
| MU | 0 | 0 | 0 | 0 | 0 | 5 | 0.00 |
| ARM | 0 | 0 | 0 | 0 | 0 | 5 | 0.00 |
| SMCI | 1 | 1 | 1 | 1 | 0 | 5 | 0.00 |
| INTC | 0 | 0 | 0 | 0 | 0 | 5 | 0.00 |
| QCOM | 0 | 0 | 0 | 0 | 0 | 5 | 0.00 |
| MRVL | 0 | 0 | 0 | 1 | 1 | 5 | 0.20 |
| AMAT | 0 | 0 | 0 | 1 | 1 | 5 | 0.20 |
| LRCX | 0 | 0 | 0 | 0 | 0 | 5 | 0.00 |
| SMH | 0 | 0 | 0 | 2 | 2 | 5 | 0.40 |
| SOXX | 0 | 0 | 0 | 4 | 4 | 5 | 0.80 |
| new_tickers | 1 | 1 | 1 | 11 | 10 | 5 | 2.00 |
| nvda_in_sample | 2 | 1 | 1 | 1 | 0 | 5 | 0.00 |
| all_descriptive | 3 | 2 | 2 | 12 | 10 | 5 | 2.00 |

## Every labelled storm, including misses

Matching: alarm in [onset − 60 min, trough], active at onset. Caught: at least 50% remains. All times UTC; label prices are closes. First onset is the earliest triggering window in the merged episode.

| Storm | Onset UTC | First onset UTC | Trough UTC | Move bp | Alarm UTC | Minutes | Ahead % | First-onset minutes | First-onset ahead % | Caught |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| nvda-2026-11-11 | 2026-11-11 22:13:00+00:00 | 2026-11-11 22:13:00+00:00 | 2026-11-11 22:28:00+00:00 | -645.70 | 2026-11-11 21:57 | -16 | 100.00 | -16 | 100.00 | yes |
| nvda-2026-11-12 | 2026-11-12 14:27:00+00:00 | 2026-11-12 14:26:00+00:00 | 2026-11-12 14:41:00+00:00 | 772.07 | — | — | — | — | — | no |
| amd-2026-10-29 | 2026-10-29 19:50:00+00:00 | 2026-10-29 19:49:00+00:00 | 2026-10-29 20:05:00+00:00 | -638.75 | 2026-10-29 20:02 | 12 | 57.98 | 13 | 59.46 | yes |
| amd-2026-11-03 | 2026-11-03 14:30:00+00:00 | 2026-11-03 14:30:00+00:00 | 2026-11-03 14:45:00+00:00 | 481.39 | — | — | — | — | — | no |
| amd-2026-11-03-2 | 2026-11-03 21:03:00+00:00 | 2026-11-03 21:01:00+00:00 | 2026-11-03 21:23:00+00:00 | 787.39 | 2026-11-03 21:16 | 13 | 23.91 | 15 | 25.39 | no |
| avgo-2026-10-29 | 2026-10-29 20:00:00+00:00 | 2026-10-29 20:00:00+00:00 | 2026-10-29 20:15:00+00:00 | -338.86 | — | — | — | — | — | no |
| tsm-2026-10-20 | 2026-10-20 21:16:00+00:00 | 2026-10-20 21:01:00+00:00 | 2026-10-20 21:19:00+00:00 | 484.39 | 2026-10-20 21:17 | 1 | 1.05 | 16 | 60.00 | no |
| tsm-2026-10-22 | 2026-10-22 21:00:00+00:00 | 2026-10-22 20:45:00+00:00 | 2026-10-22 21:15:00+00:00 | 734.49 | 2026-10-22 21:01 | 1 | 2.24 | 16 | 100.00 | no |
| mu-2026-10-21 | 2026-10-21 13:28:00+00:00 | 2026-10-21 13:23:00+00:00 | 2026-10-21 13:43:00+00:00 | -353.99 | 2026-10-21 13:36 | 8 | 49.83 | 13 | 46.51 | no |
| mu-2026-10-29 | 2026-10-29 19:52:00+00:00 | 2026-10-29 19:50:00+00:00 | 2026-10-29 20:06:00+00:00 | -418.51 | 2026-10-29 20:05 | 13 | 5.28 | 15 | 5.40 | no |
| mu-2026-11-05 | 2026-11-05 16:06:00+00:00 | 2026-11-05 14:32:00+00:00 | 2026-11-05 16:21:00+00:00 | 646.62 | 2026-11-05 15:11 | -55 | 100.00 | 39 | 0.00 | yes |
| arm-2026-10-29 | 2026-10-29 19:56:00+00:00 | 2026-10-29 19:50:00+00:00 | 2026-10-29 20:06:00+00:00 | -731.84 | 2026-10-29 20:02 | 6 | 59.74 | 12 | 64.90 | yes |
| smci-2026-10-20 | 2026-10-20 20:27:00+00:00 | 2026-10-20 20:27:00+00:00 | 2026-10-20 20:40:00+00:00 | 1,318.46 | — | — | — | — | — | no |
| smci-2026-11-03 | 2026-11-03 20:55:00+00:00 | 2026-11-03 20:55:00+00:00 | 2026-11-03 21:10:00+00:00 | 613.22 | 2026-11-03 21:07 | 12 | 14.50 | 12 | 14.50 | no |
| smci-2026-11-12 | 2026-11-12 16:22:00+00:00 | 2026-11-12 16:22:00+00:00 | 2026-11-12 16:37:00+00:00 | -821.92 | 2026-11-12 16:25 | 3 | 57.81 | 3 | 57.81 | yes |
| intc-2026-10-29 | 2026-10-29 19:52:00+00:00 | 2026-10-29 19:46:00+00:00 | 2026-10-29 20:07:00+00:00 | -2,175.38 | 2026-10-29 20:02 | 10 | 24.62 | 16 | 24.91 | no |
| qcom-2026-11-04 | 2026-11-04 13:23:00+00:00 | 2026-11-04 13:23:00+00:00 | 2026-11-04 13:35:00+00:00 | 586.17 | 2026-11-04 13:35 | 12 | 0.00 | 12 | 0.00 | no |
| mrvl-2026-10-28 | 2026-10-28 20:56:00+00:00 | 2026-10-28 20:50:00+00:00 | 2026-10-28 21:11:00+00:00 | -1,079.19 | 2026-10-28 21:06 | 10 | 7.84 | 16 | 8.26 | no |
| lrcx-2026-10-21 | 2026-10-21 20:01:00+00:00 | 2026-10-21 19:52:00+00:00 | 2026-10-21 20:16:00+00:00 | -839.69 | 2026-10-21 20:06 | 5 | 54.55 | 14 | 53.88 | yes |
| smh-2026-10-29 | 2026-10-29 19:52:00+00:00 | 2026-10-29 19:50:00+00:00 | 2026-10-29 20:06:00+00:00 | -309.79 | 2026-10-29 20:04 | 12 | 25.80 | 14 | 26.11 | no |
| soxx-2026-10-29 | 2026-10-29 19:51:00+00:00 | 2026-10-29 19:50:00+00:00 | 2026-10-29 20:06:00+00:00 | -399.66 | 2026-10-29 20:02 | 11 | 61.49 | 12 | 60.26 | yes |

## Every direction-agnostic detection

| Ticker | Alarm UTC | All-clear UTC | False against labels |
| --- | --- | --- | --- |
| NVDA | 2026-10-22 20:48:00+00:00 | 2026-10-22 21:12:00+00:00 | yes |
| NVDA | 2026-10-28 08:06:00+00:00 | 2026-10-28 08:30:00+00:00 | yes |
| NVDA | 2026-10-29 20:06:00+00:00 | 2026-10-29 20:29:00+00:00 | yes |
| NVDA | 2026-11-02 13:06:00+00:00 | 2026-11-02 15:16:00+00:00 | yes |
| NVDA | 2026-11-04 14:34:00+00:00 | 2026-11-04 16:30:00+00:00 | yes |
| NVDA | 2026-11-06 09:08:00+00:00 | 2026-11-06 09:32:00+00:00 | yes |
| NVDA | 2026-11-11 21:57:00+00:00 | 2026-11-11 23:58:00+00:00 | no |
| AMD | 2026-10-20 21:28:00+00:00 | 2026-10-20 21:52:00+00:00 | yes |
| AMD | 2026-10-29 20:02:00+00:00 | 2026-10-29 20:43:00+00:00 | no |
| AMD | 2026-11-03 09:07:00+00:00 | 2026-11-03 11:02:00+00:00 | yes |
| AMD | 2026-11-03 21:16:00+00:00 | 2026-11-03 22:11:00+00:00 | no |
| AMD | 2026-11-04 14:40:00+00:00 | 2026-11-04 15:18:00+00:00 | yes |
| AVGO | 2026-11-03 09:12:00+00:00 | 2026-11-03 15:30:00+00:00 | yes |
| AVGO | 2026-11-03 21:29:00+00:00 | 2026-11-03 21:53:00+00:00 | yes |
| AVGO | 2026-11-03 22:18:00+00:00 | 2026-11-04 12:32:00+00:00 | yes |
| AVGO | 2026-11-13 21:40:00+00:00 | — | yes |
| TSM | 2026-10-20 21:17:00+00:00 | 2026-10-20 22:20:00+00:00 | no |
| TSM | 2026-10-22 21:01:00+00:00 | 2026-10-23 11:28:00+00:00 | no |
| TSM | 2026-10-23 21:09:00+00:00 | 2026-10-26 12:02:00+00:00 | yes |
| TSM | 2026-10-26 21:12:00+00:00 | 2026-10-27 13:50:00+00:00 | yes |
| TSM | 2026-10-29 20:08:00+00:00 | 2026-10-29 21:14:00+00:00 | yes |
| TSM | 2026-10-30 21:00:00+00:00 | 2026-11-02 09:20:00+00:00 | yes |
| TSM | 2026-11-02 21:50:00+00:00 | 2026-11-03 13:41:00+00:00 | yes |
| TSM | 2026-11-03 21:55:00+00:00 | 2026-11-03 22:16:00+00:00 | yes |
| TSM | 2026-11-04 21:59:00+00:00 | 2026-11-05 00:07:00+00:00 | yes |
| TSM | 2026-11-06 21:51:00+00:00 | 2026-11-09 09:20:00+00:00 | yes |
| TSM | 2026-11-09 21:45:00+00:00 | 2026-11-10 00:37:00+00:00 | yes |
| MU | 2026-10-21 13:36:00+00:00 | 2026-10-21 14:51:00+00:00 | no |
| MU | 2026-10-22 21:54:00+00:00 | 2026-10-22 22:18:00+00:00 | yes |
| MU | 2026-10-26 08:04:00+00:00 | 2026-10-26 08:30:00+00:00 | yes |
| MU | 2026-10-29 20:05:00+00:00 | 2026-10-29 21:02:00+00:00 | no |
| MU | 2026-10-30 08:11:00+00:00 | 2026-10-30 08:35:00+00:00 | yes |
| MU | 2026-11-03 09:12:00+00:00 | 2026-11-03 09:36:00+00:00 | yes |
| MU | 2026-11-05 15:11:00+00:00 | 2026-11-05 19:12:00+00:00 | no |
| ARM | 2026-10-29 20:02:00+00:00 | 2026-10-30 14:00:00+00:00 | no |
| ARM | 2026-11-04 21:04:00+00:00 | 2026-11-04 21:47:00+00:00 | yes |
| SMCI | 2026-10-21 08:07:00+00:00 | 2026-10-21 08:32:00+00:00 | yes |
| SMCI | 2026-10-28 13:32:00+00:00 | 2026-10-28 14:43:00+00:00 | yes |
| SMCI | 2026-10-28 20:28:00+00:00 | 2026-10-28 22:51:00+00:00 | yes |
| SMCI | 2026-10-30 08:08:00+00:00 | 2026-10-30 11:43:00+00:00 | yes |
| SMCI | 2026-11-03 21:07:00+00:00 | 2026-11-03 22:04:00+00:00 | no |
| SMCI | 2026-11-12 16:25:00+00:00 | 2026-11-12 17:22:00+00:00 | no |
| INTC | 2026-10-26 08:04:00+00:00 | 2026-10-26 08:28:00+00:00 | yes |
| INTC | 2026-10-29 08:10:00+00:00 | 2026-10-29 08:53:00+00:00 | yes |
| INTC | 2026-10-29 20:02:00+00:00 | 2026-10-29 20:57:00+00:00 | no |
| INTC | 2026-11-03 09:12:00+00:00 | 2026-11-03 09:36:00+00:00 | yes |
| INTC | 2026-11-04 17:21:00+00:00 | 2026-11-04 18:07:00+00:00 | yes |
| QCOM | 2026-11-04 13:35:00+00:00 | 2026-11-04 15:45:00+00:00 | no |
| QCOM | 2026-11-04 21:03:00+00:00 | 2026-11-05 13:18:00+00:00 | yes |
| MRVL | 2026-10-26 08:04:00+00:00 | 2026-10-26 14:33:00+00:00 | yes |
| MRVL | 2026-10-28 21:06:00+00:00 | 2026-10-28 21:48:00+00:00 | no |
| MRVL | 2026-11-02 12:09:00+00:00 | 2026-11-02 15:23:00+00:00 | yes |
| MRVL | 2026-11-10 18:01:00+00:00 | 2026-11-10 18:25:00+00:00 | yes |
| AMAT | 2026-11-03 21:21:00+00:00 | 2026-11-04 15:14:00+00:00 | yes |
| AMAT | 2026-11-12 21:03:00+00:00 | 2026-11-12 22:02:00+00:00 | yes |
| LRCX | 2026-10-21 20:06:00+00:00 | 2026-10-22 13:04:00+00:00 | no |
| LRCX | 2026-11-03 21:29:00+00:00 | 2026-11-04 15:13:00+00:00 | yes |
| SMH | 2026-10-29 20:04:00+00:00 | 2026-10-30 11:22:00+00:00 | no |
| SMH | 2026-11-06 09:08:00+00:00 | 2026-11-06 11:41:00+00:00 | yes |
| SMH | 2026-11-09 09:09:00+00:00 | 2026-11-09 12:44:00+00:00 | yes |
| SMH | 2026-11-10 18:01:00+00:00 | 2026-11-10 18:25:00+00:00 | yes |
| SOXX | 2026-10-21 22:46:00+00:00 | 2026-10-22 11:30:00+00:00 | yes |
| SOXX | 2026-10-23 12:24:00+00:00 | 2026-10-23 14:22:00+00:00 | yes |
| SOXX | 2026-10-29 20:02:00+00:00 | 2026-10-29 21:09:00+00:00 | no |
| SOXX | 2026-11-03 09:06:00+00:00 | 2026-11-03 13:16:00+00:00 | yes |
| SOXX | 2026-11-04 09:08:00+00:00 | 2026-11-04 10:48:00+00:00 | yes |
| SOXX | 2026-11-09 09:09:00+00:00 | 2026-11-09 12:11:00+00:00 | yes |
| SOXX | 2026-11-10 13:06:00+00:00 | 2026-11-10 14:20:00+00:00 | yes |
| SOXX | 2026-11-11 13:57:00+00:00 | 2026-11-11 14:21:00+00:00 | yes |
| SOXX | 2026-11-11 23:58:00+00:00 | 2026-11-12 00:22:00+00:00 | yes |

## Three new replays

Ranked by absolute unrounded labelled move, including upward moves and misses. Default-crew reports are stored in the local bundles.

| Replay | Move bp | Caught | Ahead % | Frames | Stress scenarios | Prepared final $ | Unprepared final $ | Prepared margin UTC | Unprepared margin UTC |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| intc-2026-10-29 | -2,175.38 | no | 24.62 | 361 | 6 | 517,728.86 | 517,728.86 | 2026-10-29 20:01:00+00:00 | 2026-10-29 20:01:00+00:00 |
| smci-2026-10-20 | 1,318.46 | no | — | 361 | 0 | 1,682,100.80 | 1,682,100.80 | — | — |
| mrvl-2026-10-28 | -1,079.19 | no | 7.84 | 361 | 5 | 632,426.96 | 519,133.10 | — | 2026-10-28 21:11:00+00:00 |

Existing index entries preserved: 15; new entries: 3; order preserved: yes; original metrics preserved: yes.

## Real AI crew comparison, identical bundle facts

| Crew | Writer | Inspector | Completed | Numeric first try | Accepted first try | Fallbacks | Flags | Errors | Mean total s | Mean writer s | Total token $ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| default | accounts/fireworks/models/glm-5p3 | accounts/fireworks/models/kimi-k3p1-pro | 3 | 3 | 3 | 0 | 0 | 0 | 4.43 | 2.03 | 0.0127946 |
| private | openai/gpt-oss-120b | openai/gpt-oss-120b | 3 | 3 | 3 | 0 | 0 | 0 | 5.63 | 3.11 | 0.0000000 |

| default replay | Outcome | Latency s | Token $ | Fact SHA-256 |
| --- | --- | --- | --- | --- |
| intc-2026-10-29 | passed_first_try | 4.18 | 0.0045208 | 1d6af48f54ebb2b084e523e925e53ddeb8c0e786655f290d9a301964e97ec8b8 |
| smci-2026-10-20 | passed_first_try | 3.49 | 0.0034528 | cf0dca4b15385a3f003824f2186825ea957359200ec237ffabc5340bc340c76f |
| mrvl-2026-10-28 | passed_first_try | 5.62 | 0.0048210 | 5a3dbd4f5bbcbff685a733eb1eea0418912ba5a77d1f2af3306adc82ad4d5686 |

| private replay | Outcome | Latency s | Token $ | Fact SHA-256 |
| --- | --- | --- | --- | --- |
| intc-2026-10-29 | passed_first_try | 4.91 | 0.0000000 | 1d6af48f54ebb2b084e523e925e53ddeb8c0e786655f290d9a301964e97ec8b8 |
| smci-2026-10-20 | passed_first_try | 6.16 | 0.0000000 | cf0dca4b15385a3f003824f2186825ea957359200ec237ffabc5340bc340c76f |
| mrvl-2026-10-28 | passed_first_try | 5.83 | 0.0000000 | 5a3dbd4f5bbcbff685a733eb1eea0418912ba5a77d1f2af3306adc82ad4d5686 |

Modal cold wake/model discovery: 71.34 s; local wall time including deploy, startup and stop command: 93.48 s; billing window through server-confirmed termination: 97.76 s; conservative runtime cost estimate: $0.1955 at $0.002/s; stop exit code: 0; observed final state: stopped; running tasks: 0. Token cost is separate from GPU runtime, and this estimate is not an invoice.

| Modal allocation metric | Observed GPU minutes | Missing buckets |
| --- | --- | --- |
| gpu_count_h100_avg | 1.45 | 0 |

Allocation window: 2026-11-15T04:09:00+00:00 through 2026-11-15T04:11:00+00:00; bucket size 60.0 seconds. Allocated GPU count integrated over returned complete buckets; uncovered time and missing buckets are unknown. No GPU was woken to retrieve metrics.

## Tiger Data

| Statistic | Value |
| --- | --- |
| Status | complete |
| Hypertable | equity_1m |
| Verified snapshot rows | 211,948 |
| 5-minute aggregate rows | 49,817 |
| Chunks compressed | 5 |
| Bytes before compression | 31,309,824 |
| Bytes after compression | 5,480,448 |
| Compression ratio | 5.71 |
| Sample query ms including network | 16.77 |
| Sample query result rows | 12 |

```sql
SELECT bucket, symbol, open, high, low, close, volume, bars
FROM equity_5m WHERE symbol = %s AND bucket >= %s AND bucket < %s ORDER BY bucket
```

Query parameters: `{"end_utc": "2026-11-15 00:00:00+00:00", "start_utc": "2026-11-14 00:00:00+00:00", "symbol": "NVDA"}`.

## Retention, warm-up and provenance

| Ticker | First UTC | Last UTC | In-hours rows | Bad prints | SD-defined rows | Risk-defined rows | Raw SHA-256 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NVDA | 2026-10-19 08:00:00+00:00 | 2026-11-14 00:59:00+00:00 | 18,467 | 1 | 17,740 | 17,362 | 753fd2d93ce72612849fc1149786d2615a6a45623cdfb7d3d2fe746a695f0361 |
| AMD | 2026-10-19 08:00:00+00:00 | 2026-11-14 00:59:00+00:00 | 16,668 | 1 | 15,769 | 14,834 | 8562d357a1d188b69e2d6d3b0a217a0609792f0ee847d3f29669bef103af462f |
| AVGO | 2026-10-19 08:00:00+00:00 | 2026-11-14 00:58:00+00:00 | 16,184 | 2 | 15,350 | 13,844 | b6b279747b8308a433f6d27861898a1dfbcff51d38b38f3d9773d890c8f9278f |
| TSM | 2026-10-19 08:00:00+00:00 | 2026-11-14 00:59:00+00:00 | 16,275 | 48 | 15,412 | 13,962 | 286cd5871392735ffacd4f32ea122f72febc9321f33719037a9eb03e6dd654fa |
| MU | 2026-10-19 08:00:00+00:00 | 2026-11-14 00:59:00+00:00 | 18,597 | 3 | 17,857 | 17,560 | 9798623921d43484d722d0b15fd7b3ff73f1e5bc86515aafd3d60bf7360ed065 |
| ARM | 2026-10-19 08:00:00+00:00 | 2026-11-14 00:54:00+00:00 | 11,785 | 4 | 10,941 | 9,184 | 040a84c119fe2b75a48f611b73bc2e8d649a70e91b526e4a7fb4a1e870167996 |
| SMCI | 2026-10-19 08:00:00+00:00 | 2026-11-14 00:59:00+00:00 | 16,114 | 3 | 15,251 | 13,868 | b7fed879e027f83cd5f365e4c4f3b6921bdb4ba76760f9381f627fd94954a9b7 |
| INTC | 2026-10-19 08:00:00+00:00 | 2026-11-14 00:59:00+00:00 | 18,648 | 3 | 17,924 | 17,655 | 1699bc6e4c91a3c9001bfbe28a03ea27ee29b274e0fe0c4be29e6455aa610636 |
| QCOM | 2026-10-19 08:00:00+00:00 | 2026-11-14 00:45:00+00:00 | 10,346 | 0 | 9,530 | 8,182 | ebbbd0493383c0cfbf74f11d8fbdf556f994b565c943f4c4bb0a52aab15fa4ce |
| MRVL | 2026-10-19 08:00:00+00:00 | 2026-11-14 00:59:00+00:00 | 15,867 | 3 | 14,976 | 13,558 | 34c97ca57f3b6375c03c17f19c99facf324af916e2bb1a3ffab124fa358810e9 |
| AMAT | 2026-10-19 08:00:00+00:00 | 2026-11-14 00:57:00+00:00 | 11,610 | 7 | 10,738 | 8,962 | 2a649380244d1f0e065436dfd66b27d64fdcd9ae10aac9373d4fc73bf4e2cafe |
| LRCX | 2026-10-19 08:01:00+00:00 | 2026-11-14 00:56:00+00:00 | 11,452 | 6 | 10,631 | 9,011 | 4c572ac8299f6e924d81475963b96ebf35cd0cd8bc542d4370bce2a2047e8998 |
| SMH | 2026-10-19 08:00:00+00:00 | 2026-11-14 00:59:00+00:00 | 13,748 | 3 | 12,876 | 11,034 | ef3844235c755fc6270eb75bb35d9abb7dd51b0ffc956b57bb82faef8716abad |
| SOXX | 2026-10-19 08:00:00+00:00 | 2026-11-14 00:59:00+00:00 | 16,187 | 2 | 15,339 | 13,978 | 49df32397ebaf837a0ec94d3e1760253b294a0f11631da847517d43a421a6bf9 |

| Ticker | Requested start ET | End ET exclusive | Status | Type | Details |
| --- | --- | --- | --- | --- | --- |
| NVDA | 2026-10-17 | 2026-10-19 | error | YFPricesMissingError | $NVDA: possibly delisted; no price data found  (1m 2026-10-17 -> 2026-10-19) |
| AMD | 2026-10-17 | 2026-10-19 | error | YFPricesMissingError | $AMD: possibly delisted; no price data found  (1m 2026-10-17 -> 2026-10-19) |
| AVGO | 2026-10-17 | 2026-10-19 | error | YFPricesMissingError | $AVGO: possibly delisted; no price data found  (1m 2026-10-17 -> 2026-10-19) |
| TSM | 2026-10-17 | 2026-10-19 | error | YFPricesMissingError | $TSM: possibly delisted; no price data found  (1m 2026-10-17 -> 2026-10-19) |
| MU | 2026-10-17 | 2026-10-19 | error | YFPricesMissingError | $MU: possibly delisted; no price data found  (1m 2026-10-17 -> 2026-10-19) |
| ARM | 2026-10-17 | 2026-10-19 | error | YFPricesMissingError | $ARM: possibly delisted; no price data found  (1m 2026-10-17 -> 2026-10-19) |
| SMCI | 2026-10-17 | 2026-10-19 | error | YFPricesMissingError | $SMCI: possibly delisted; no price data found  (1m 2026-10-17 -> 2026-10-19) |
| INTC | 2026-10-17 | 2026-10-19 | error | YFPricesMissingError | $INTC: possibly delisted; no price data found  (1m 2026-10-17 -> 2026-10-19) |
| QCOM | 2026-10-17 | 2026-10-19 | error | YFPricesMissingError | $QCOM: possibly delisted; no price data found  (1m 2026-10-17 -> 2026-10-19) |
| MRVL | 2026-10-17 | 2026-10-19 | error | YFPricesMissingError | $MRVL: possibly delisted; no price data found  (1m 2026-10-17 -> 2026-10-19) |
| AMAT | 2026-10-17 | 2026-10-19 | error | YFPricesMissingError | $AMAT: possibly delisted; no price data found  (1m 2026-10-17 -> 2026-10-19) |
| LRCX | 2026-10-17 | 2026-10-19 | error | YFPricesMissingError | $LRCX: possibly delisted; no price data found  (1m 2026-10-17 -> 2026-10-19) |
| SMH | 2026-10-17 | 2026-10-19 | error | YFPricesMissingError | $SMH: possibly delisted; no price data found  (1m 2026-10-17 -> 2026-10-19) |
| SOXX | 2026-10-17 | 2026-10-19 | error | YFPricesMissingError | $SOXX: possibly delisted; no price data found  (1m 2026-10-17 -> 2026-10-19) |

Packages: `{"numpy": "2.2.6", "pandas": "2.3.3", "pyarrow": "25.0.1", "yfinance": "1.8.0"}`. Config: `{"calm_minutes":20,"calm_off":0.25,"comove_min":2,"max_bar_gap_minutes":5,"move_windows":[1,3,5],"squall_on":0.75,"storm_minutes":2,"storm_on":0.8,"strength_full":10.0,"version":1,"w_comove":0.0,"watch_after_minutes":15,"watch_lead_minutes":30}`.

Config/source fingerprints, all request outcomes, exact unrounded rows, fact fingerprints and local bundle hashes are in results.json; preregistration and run_started.json establish ordering. No bars, bundles, secrets or ledger are committed.

## November 11 regular close to November 12 low, separate descriptive facts

| Ticker | Close UTC | Close | Low UTC | Low | Move bp |
| --- | --- | --- | --- | --- | --- |
| NVDA | 2026-11-11 20:59:00+00:00 | 173.85 | 2026-11-12 14:31:00+00:00 | 148.80 | -1,440.90 |
| AMD | 2026-11-11 20:59:00+00:00 | 552.96 | 2026-11-12 14:13:00+00:00 | 550.65 | -41.78 |
| AVGO | 2026-11-11 20:59:00+00:00 | 345.45 | 2026-11-12 13:22:00+00:00 | 344.36 | -31.64 |
| TSM | 2026-11-11 20:59:00+00:00 | 413.30 | 2026-11-12 14:14:00+00:00 | 393.39 | -481.85 |
| MU | 2026-11-11 20:59:00+00:00 | 812.00 | 2026-11-12 14:02:00+00:00 | 760.26 | -637.19 |
| ARM | 2026-11-11 20:59:00+00:00 | 203.38 | 2026-11-12 14:23:00+00:00 | 189.09 | -702.63 |
| SMCI | 2026-11-11 20:59:00+00:00 | 30.43 | 2026-11-12 16:56:00+00:00 | 25.70 | -1,551.97 |
| INTC | 2026-11-11 20:59:00+00:00 | 62.51 | 2026-11-12 14:16:00+00:00 | 59.27 | -518.32 |
| QCOM | 2026-11-11 20:59:00+00:00 | 176.55 | 2026-11-12 09:01:00+00:00 | 171.10 | -308.69 |
| MRVL | 2026-11-11 20:59:00+00:00 | 168.74 | 2026-11-12 14:27:00+00:00 | 155.30 | -796.49 |
| AMAT | 2026-11-11 20:59:00+00:00 | 395.07 | 2026-11-12 14:29:00+00:00 | 375.80 | -487.76 |
| LRCX | 2026-11-11 20:59:00+00:00 | 235.71 | 2026-11-12 14:16:00+00:00 | 225.30 | -441.64 |
| SMH | 2026-11-11 20:59:00+00:00 | 507.23 | 2026-11-12 14:24:00+00:00 | 483.12 | -475.33 |
| SOXX | 2026-11-11 20:59:00+00:00 | 155.41 | 2026-11-12 14:16:00+00:00 | 149.37 | -388.65 |

## Checks and limits

Verification: `{"archive_verification": {"detector_reruns": 0, "network_requests": 0, "pooled_scores_reproduced": 3, "raw_hashes_verified": 14}, "checked_at_utc": "2026-11-15T04:19:39.559872+00:00", "existing_validator_errors": {"index": [], "intc-2026-10-29": [], "mrvl-2026-10-28": [], "smci-2026-10-20": []}, "pytest_command": "cd backend && python -m pytest -q -rs", "pytest_elapsed_s": 35.15, "pytest_log_sha256": "28e24bbaee52ec0f4eaf69c67789c91da8c5042152e5c1e9e513ed300fa0c5bf", "pytest_passed": 341, "pytest_skipped": 9, "shared_source_fingerprints_unchanged": true, "skip_reasons": ["SKIPPED [1] tests/live/test_tiger_live.py:11: no .env with TIGER_DATABASE_URL", "SKIPPED [1] tests/oos/test_oos.py:58: Frozen-core fingerprint requires the registered runtime (pyarrow: registered 24.0.0, running 25.0.1). See docs/oos/amendment-2026-11-15-runtime.md; this skip does not verify the historical fingerprint.", "SKIPPED [1] tests/oos/test_oos.py:64: Frozen-core fingerprint requires the registered runtime (pyarrow: registered 24.0.0, running 25.0.1). See docs/oos/amendment-2026-11-15-runtime.md; this skip does not verify the historical fingerprint.", "SKIPPED [1] tests/oos/test_oos.py:72: Frozen-core fingerprint requires the registered runtime (pyarrow: registered 24.0.0, running 25.0.1). See docs/oos/amendment-2026-11-15-runtime.md; this skip does not verify the historical fingerprint.", "SKIPPED [1] tests/test_export.py:55: no processed SGX data", "SKIPPED [1] tests/test_ingest.py:65: SGX data not in data/raw", "SKIPPED [1] tests/test_labels.py:45: SGX data not in data/raw", "SKIPPED [1] tests/test_readme_results.py:59: data/processed/metrics.json not present (SGX data is not committed)", "SKIPPED [1] tests/test_readme_results.py:73: data/processed/metrics.json not present (SGX data is not committed)"]}`.

- The universe and shock week were selected with NVDA already observed; the thirteen new names are a cross-ticker test, not independent future-period validation.
- All served history is the primary registered window. The November 9–13 view is a descriptive slice of that one run. Warm-up has no history before the earliest acquired bar.
- Yahoo has trades rather than quotes. Thin extended-hours bars, missing minutes, bad prints, unadjusted prices and sector correlation affect interpretation; overnight price gaps cannot trigger this session-safe detector.
- Labels use close extrema, not intrabar lows. The separate November close-to-low facts use the existing equity convention. False alarms are defined against labels, not a judgement that an alert had no trading value.
- The replay book is synthetic, uses next observed open fills and assumes no spread, slippage or fees; replay selection includes an upward storm and missed/late alarms.
- Modal token accounting is zero because billing is for infrastructure. The reported runtime cost is an explicitly conservative wall-time estimate, not an invoice; startup/stop are included.
