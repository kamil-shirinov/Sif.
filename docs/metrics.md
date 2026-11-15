# StormScore metrics: exact definitions

Each definition below is what the backend code computes, written as a formula, with the
module that computes it. Times are UTC. One frame or bar is one minute. `mid` is the
close mid of the one-minute bar stamped `t`. Unless a section says otherwise, the
numbers come from SGX spot bars, 1 July to 31 August 2026.

Splits: **July** is the tuning month for the alarm. **August** is the test split
(`TEST_START = 2026-08-01`, `TEST_END = 2026-09-01`, end exclusive). July bars are still
read as warm-up history for the trailing 24-hour volatility.

**Rounding.** Nothing is rounded while computing. Labels, classification (`caught`), the
tuning constraint and the tuning rank all use exact values. Rounding is applied once, to
what is written or printed (`storm.evaluate.for_display`). The figures in this document
are those rounded outputs.

**Time units.** Every timestamp is held at nanosecond resolution (`storm.features.as_ns`),
and minute arithmetic does not depend on the unit (`storm.features.epoch_minutes`).
pandas is pinned below 3, which parses to microseconds by default.

## 1. Storm label (`storm.labels`)

Per pair, for every bar `t`:

```
ret_bp(t)    = (mid(t) / mid(t-1) - 1) * 1e4        defined only if the previous bar is exactly 1 min earlier
sd_24h(t)    = sd of ret_bp over the 1,440 bars before t (t excluded; at least 720 defined returns)
move15(t)    = (mid(t) / mid(t - 15 min) - 1) * 1e4
threshold(t) = max(30 bp, 8 * sd_24h(t - 15 min) * sqrt(15))
observed(t)  = number of bars in (t - 15 min, t]
trigger(t)   = |move15(t)| >= threshold(t)  and  observed(t) >= 13
               (no bar at t - 15 min, or an undefined sd: no trigger)
```

No return spans a gap, and every missing minute counts, so a two-minute hole leaves its
return undefined. SGX spot has about 40 such holes per pair (2 to 5 minutes) outside the
weekend close. A label window needs at least 13 of its 15 minutes observed.

Triggering windows on the same pair 6 hours or less apart (from one triggering window's end
to the next one's) form **one storm**. Labels use the whole history, so a later trigger can
merge into an earlier episode and change its onset, trough and move; the bundles' stress menu
therefore relabels on the bars up to its snapshot (`storm.labels.label_as_of`, section 8).
Volatility windows count bars, not clock minutes, so a weekend never dilutes `sd_24h`.

## 2. Onset, first onset, trough, move_bp, duration (`storm.labels`)

Within one storm:

```
peak window = the triggering window with the largest |move15|
onset       = start of the peak window          (peak window end - 15 min)
first_onset = start of the storm's first triggering window      (first_onset <= onset)
end         = end of the last triggering window
trough      = argmin mid over [onset, end] if the peak move is down, argmax if it is up
move_bp     = (mid(trough) / mid(onset) - 1) * 1e4      simple return, signed, unrounded
duration    = trough - onset, in minutes
```

`move_bp` is a **simple** return, not a log return. It is stored unrounded in
`storms.csv`. The bundle's `storm.move_bp` rounds it to 0.1, and `storm.label` is
`f"{move_bp/100:+.1f}% in {duration} min"`. A storm is a storm whichever way it moves.
Each ship's book decides whether the move is danger or a fair wind.

`first_onset` can be far earlier than `onset`, because the 6-hour merge joins an early,
smaller trigger to the main move. Examples: usdjpy-2026-07-30 has onset 13:29 and first
onset 10:02. usdjpy-2026-07-02 has onset 12:20 and first onset 06:35.

**Equities (NVDA, `storm.equity`).** Onset is the 11 Nov regular-session close (the last
minute before 16:00 ET). Trough is the lowest one-minute **low** (not the close) on 12 Nov,
up to the end of the replay. `move_bp = low / close - 1`. Both are measured on bars not
flagged as bad prints (section 4). The market is closed from 20:00 to 04:00 ET. No
return or detector window crosses that closed stretch: every bar carries its session,
and windows that change session are undefined. The storm report counts **trading
minutes** (pre-market, regular and after-hours sessions) from onset to trough, not clock
minutes, and states the closed stretch as a fact. For NVDA that is 572 trading minutes
out of 1,052 clock minutes, closed 12 Nov 01:00 to 09:00 UTC.

## 3. Calendar and scheduled matching (`storm.detector.load_calendar`, `storm.labels.scheduled_event`)

Only rows of `contracts/calendar.csv` with `verified = yes` and an http(s) `source_url`
are loaded. Every other row creates no watch and no scheduled label.

```
scheduled  iff  min over loaded events e of |onset - e.time_utc| <= 15 min     (inclusive both sides)
event      = the nearest such event (name and time); otherwise kind = unscheduled
```

The calendar is every verified release, never filtered to improve a number. A scheduled
label states timing only. It does not claim the release caused the move.

**The schedules are public in advance.** The BLS publishes its release schedule
(Employment Situation, CPI, PPI, ECI, Productivity, Import/Export Prices) for the whole
year ahead. The Federal Reserve publishes FOMC meeting dates, and the minutes three weeks
after each meeting, a year ahead. A watch built from these rows therefore uses no
information a trader did not have before the release.

## 4. The alarm (`storm.detector`, v1, config tuned on July)

```
strength(t) = max over m in {1, 3, 5} of  |mid(t)/mid(t-m) - 1| * 1e4 / (sd_24h(t) * sqrt(m))
              (a window is defined only when its m bars span exactly m clock minutes,
               and do not change session)
risk(t)     = clip(strength / 10 + w_comove * [comove >= 2], 0, 1)      tuned w_comove = 0
direction   = sign of the move in the window that set strength
```

Tuned thresholds (unchanged by this round's re-tune): `squall_on = 0.75`,
`storm_on = 0.80`, `storm_minutes = 2`, `calm_off = 0.25`, `calm_minutes = 20`.

- **Episode.** Opens at the first minute with `risk >= squall_on`. It closes (the
  **all-clear**) after 20 consecutive minutes with `risk < calm_off`.
- **Storm-level detection** (direction-agnostic). The first minute in an episode that
  completes 2 consecutive minutes with `risk >= storm_on`.
- **Book-aware alarm** (what a bundle's `alarm` event shows). The same rule, counting
  only minutes where the move goes against the book's exposure. Every alert carries the
  all-clear time of its episode, which the matcher in section 5 uses.

The **scoring in sections 5 to 7 uses the direction-agnostic detection**. Bundles and the
policy use the book-aware alarm.

**Bad prints (equities), causal.** A Yahoo bar whose close is at least 2% from the
previous close, while the next bar opens back within a quarter of that jump, is flagged.
It is never dropped. At its own minute it is visible like any bar: its return, z and
strength use the history before it, so it can alarm, or count as a false alarm. From the
next minute on, once the reversal has been seen, every return, window, `sd_24h`, spread
median and realised volatility is computed as if it had never printed.

On 10 Nov 18:00 UTC the NVDA print (+6.5%) gives risk 1.00 at that minute. It adds **no
alarm on 10 Nov**: storm level needs 2 consecutive minutes, and the next minute no longer
sees the print. It raises no squall or fair wind either. NVDA's only storm-level danger
alarm of 9 to 13 Nov is still 11 Nov 21:57 UTC.

## 5. Alarmed, caught, minutes from onset (`storm.evaluate`)

**One matcher** (`storm.evaluate.alarm_matches`) decides whether an alarm belongs to a
storm. The evaluator uses it here, and `storm.export` and `storm.equity` use it for every
bundle alarm event's `move_ahead_pct`:

```
onset - 60 min <= alarm <= trough        and        still in force at onset (all-clear is none or >= onset)
```

A storm's alarm is the **earliest** storm-level detection on the storm's own pair that
matches. An alarm that fired and cleared before onset is not credited. Neither is one
older than 60 minutes, so a detector that stays in storm state cannot game the score. A
bundle alarm event that does not match gets `move_ahead_pct = null` and the text "(turbulence)".

```
alarmed             = the storm has an alarm
minutes_from_onset  = alarm - onset, in whole minutes (negative when the alarm came first)
move_ahead_pct      = 100                                               if alarm <= onset
                    = 0                                                 if alarm >= trough
                    = clip((mid(alarm) - mid(trough)) / (mid(onset) - mid(trough)) * 100, 0, 100)   otherwise
caught              = alarmed and move_ahead_pct >= 50          (on the unrounded share)
```

The same two figures are also reported **relative to first_onset**, as `minutes_first_onset`
and `move_ahead_pct_first_onset` per storm. Over the storms, these give
`caught_first_onset`, `median_move_ahead_pct_first_onset` and
`median_minutes_to_alarm_first_onset`. Matching and `caught` stay on `onset`.

**Signs.** The ratio is the share of the onset-to-trough distance still to travel, and it
is the same formula for both directions:

- **Down move** (`onset > trough`): `(mid(alarm) - trough) / (onset - trough)`.
- **Up move** (`trough > onset`): numerator and denominator both flip sign, so it equals
  `(trough - mid(alarm)) / (trough - onset)`.

In both cases, a price that has already passed the trough gives 0, and a price still at
or beyond the onset gives 100 (after clipping).

August, v1:

| | relative to onset | relative to first_onset |
|---|---|---|
| caught | 4 of 6 | 4 of 6 |
| median share of move ahead | 57.4% | 57.6% |
| median minutes to alarm | +3.5 | +9.0 |

## 6. False alarms: two rates, each labelled exactly (`storm.evaluate.score`)

```
false alarm      = a storm-level detection in August on pair P that lies outside
                   [onset - 60 min, end + 60 min] of every labelled storm on P
observed day     = 1,440 minutes with a bar on ANY pair in the split
days             = (number of distinct such minutes in August) / 1,440 = 21.52
```

- **`false_alarms_per_day`: pair alarms per observed day.** Each pair's false alarm counts
  on its own, and a storm on another pair does not excuse it. One USD shock that alarms
  USDJPY and USDSGD in the same minute is two pair alarms.
- **`false_alarm_episodes_per_day`: distinct alert episodes per observed day.** Sort the
  false alarms on all pairs by time. An episode opens at the first false alarm not yet in
  an episode, and it holds every false alarm within 15 minutes (inclusive) of that
  opening alarm. So alarms on different pairs within 15 minutes count as one, and any two
  alarms in one episode are at most 15 minutes apart. The window is anchored at the
  opening alarm, so a chain of alarms 14 minutes apart cannot stretch an episode.

August, v1: **11 pair alarms over 21.52 days, or 0.51 per day**. They form **7 distinct
alert episodes, or 0.33 per day**. Eight of the eleven come in four same-minute pairs:

- 12 Aug 09:25, USDJPY and USDSGD
- 12 Aug 12:32, EURUSD and USDSGD
- 19 Aug 12:38, EURUSD and USDSGD
- 28 Aug 14:01, USDJPY and USDSGD

The other three are single USDJPY alarms: 6 Aug 14:11, 23 Aug 21:39 and 30 Aug 20:17. Two
of the pairs (19 Aug 12:38, 28 Aug 14:01) coincide with a real storm on the third pair.
They still count as false, because the storm is on another pair.

Before this round there were 12 pair alarms (0.56 per day) in 8 episodes (0.37 per day).
The one that went is 10 Aug 21:05 USDSGD. It came from a "one-minute" move measured
across the 21:01 to 21:04 hole, which the exact-minute rule in sections 1 and 4 no
longer allows.

**Storm-state share.** v1's storm-state minutes over the pair-minutes actually observed:
the sum of each pair's own August bars, not `days * 1440 * 3`. For August that is
1,696 of 92,951, or **1.82%**.

## 7. Watch window, warning time, quiet watches (`storm.detector`, `storm.backtest`)

```
watch window(e) = [e - 30 min, e + 15 min)          half-open; state = 1 unless a storm (2) is active
```

When two windows overlap, the earlier event keeps the minute. A storm can hide a
window's start; the watch event then fires at the first minute the watch state shows,
after the all-clear (`test_detector.py::test_watch_hidden_at_its_start_is_announced_when_first_shown`).
A storm is **watched before onset** if its pair shows `state == 1` at some minute in
`[event - 30 min, onset)`. Its warning time is:

```
warning_minutes = onset - first such minute
```

The warning is measured to the **onset**, not to the release. The onset is the start of
the strongest 15-minute window, so it can come up to 15 minutes before the release. For
example, 7 Aug payrolls on USDJPY: release 12:30, watch from 12:00, onset 12:20. The
warning is 20 minutes, while the warning before the release itself was 30.

**Quiet watches and precision (per release, August):**

```
release had a storm  iff  some labelled storm on ANY pair has onset in [e - 30 min, e + 15 min)
watch_precision      = releases with a storm / all releases
```

A release counts once however many pairs stormed. August had 7 releases and 2 had a
storm, so `watch_precision = 0.29`. The 5 quiet ones are listed in `metrics.json`.

**Edge note.** Scheduled matching (section 3) is `|onset - e| <= 15` inclusive. The watch
window is `[e - 30, e + 15)`. The two differ only for an onset at exactly `e + 15`, or one
between `e - 30` and `e - 15`. No storm in July or August falls in either gap: every
scheduled onset is between 14 minutes before and 1 minute after its release.

**Combined coverage:** a storm is covered if it was watched before onset, or it was caught.

## 8. Ships: execution, margin, stress, drawdown (`storm.exposure`, `storm.equity`)

The books are **synthetic**. FX: long USD 20,000,000 against the pair's other currency,
$1,000,000 equity, maintenance 2.5% of open notional. The policy backtest splits that
across three pairs at 6,666,667 each. NVDA: long $4,000,000 on $1,000,000 equity,
maintenance 15% of the position.

**Execution.** A signal is read from bar `t`'s close, so its trade fills at the open of
bar `t+1`. If that minute has no bar, the trade fills at the next minute that has one;
for NVDA after a closed night, that is the next session's first bar. Fills are
side-correct: buying the base currency pays the ask, and selling it gets the bid.

| Trade | Fills at |
|---|---|
| Legs open | the first frame's close mid. This is the book's starting position, not a trade. |
| Cut (prepared ship, 75% of the leg) | the next bar's open, **bid** for USDJPY and USDSGD (sells USD), **ask** for EURUSD (buys EUR back) |
| Restore (after the all-clear) | the next bar's open, **ask** for USDJPY and USDSGD, **bid** for EURUSD |
| Margin call | the price where the breach was found (that bar's open or close), bid or ask by side; every currency balance is then converted to USD at mid, and equity is held flat afterwards |

Every fill records its price, the mid of the same quote, and its **cost versus mid** in
USD: `|qty| * |price - mid|`, converted at mid. `metrics.json` lists the prepared ship's
fills under `policy.trades`, and each bundle's `cut` and `restore` event text states the
fill price and side. Yahoo has trades, not quotes, so NVDA fills at the bar's open with a
cost of 0. That 0 is not a measured spread.

**Margin order, each minute `i`:**

1. Mark the book at bar `i`'s **open** mid and test maintenance, before any trade that minute.
2. Fill the voluntary trades scheduled for that minute.
3. Mark at bar `i`'s **close** mid and test again.

A breach at the alarm bar's close is therefore a margin call even if a cut was
scheduled for the next bar. A restore is skipped if, spread included, it would put the
book straight into a margin call.

```
equity(i) = sum over currencies c of cash_c(i) * usd_rate_c(mid)
gross(i)  = sum over legs of |qty| * usd_rate(base currency, mid)          (marked notional)
breach    = gross > 0 and equity < maintenance * gross
```

**Stress menu (point in time).** A replay's `stress` rows use only storms whose trough came
before the exposure snapshot, which is the bar before onset, and those storms are labelled
on the bars stamped at or before the snapshot (`storm.labels.label_as_of`, called by
`storm.exposure.stress_menu`): the labels a trader could have computed then. Full-history
labels would not do: the 6-hour merge can fold an earlier move into a storm whose trough
is still in the future, so a later price would remove a scenario that was known at the
snapshot (the audit's reproducer, `test_1_stress_menu_does_not_depend_on_prices_after_the_snapshot`).
An episode still running at the snapshot appears as it stood then. When none qualifies,
the menu is empty. The NVDA bundle's menu is empty: its candidate moves are all on 12 Nov,
in the snapshot's future. Each 2 Jul FX bundle has one row, the USDJPY move that began at
06:35 that morning: labelled on the history up to the snapshot it is a finished storm,
while the full-history labels merge it into the 12:20 USDJPY storm. Each row applies the
storm's **unrounded** USD move `u`, computed from its onset and trough mids with EURUSD
inverted, to the snapshot's actual holdings: the unprepared ship's cash per currency and
its legs at `as_of_i`. Every leg is shocked (`USDxxx mid * (1 + u)`, `EURUSD mid / (1 + u)`),
and the book is revalued with the same `equity` and `gross` as above:

```
pnl_usd     = equity(shocked) - equity(snapshot)
margin_call = gross(shocked) > 0 and equity(shocked) < maintenance * gross(shocked)
```

The EURUSD notional is marked at the shocked price, not held at 20,000,000. The row applies
no cuts and no path.

**Max drawdown.** The dollar and percentage figures are maximised independently, so they
can come from different peaks:

```
dd_usd = max over i of (peak(i) - equity(i))              peak(i) = max equity up to i
dd_pct = max over i of (peak(i) - equity(i)) / peak(i) * 100
```

The policy backtest runs on the three-pair book from 2 Aug 19:01 to 31 Aug 23:59 UTC:

| | prepared | unprepared |
|---|---|---|
| final equity | $1,033,659 | $993,889 |
| max drawdown | $191,261 (17.2%) | $226,151 (20.6%) |
| danger alarms / cuts / restores | 11 / 11 / 11 | 0 / 0 / 0 |
| fills and their cost vs mid | 22 fills, $7,038 | none |

## 9. Worked example: USDJPY, 30 July 2026 (`usdjpy-2026-07-30`)

**Label.** At 13:29, `sd_24h = 1.227 bp`, so `threshold = max(30, 8 * 1.227 * 3.873) = 38.0 bp`.
The strongest triggering window runs 13:29 to 13:44, with `move15 = -150.6 bp`. So:

- onset = 13:29, with mid 162.7805. The first triggering window of the same storm starts
  at 10:02 (first_onset, mid 163.2725), because it lies within 6 hours of the main move:
  10:02 to 10:17 moved -41.6 bp against a 30 bp threshold. The detector alarmed on it at
  10:18 and cleared at 11:44, before the onset, so the matcher does not credit that alarm
  and July's score counts it as false. Against first_onset the credited 13:37 alarm is
  +215 min with 80.6% of the move (163.2725 to 158.054) still ahead.
- The last triggering window ends at 14:24. The lowest mid in 13:29 to 14:24 is 158.054, at 14:23 (the trough).
- `move_bp = (158.054 / 162.7805 - 1) * 1e4 = -290.4`. Duration is 54 min. Label: `-2.9% in 54 min`.

**Kind.** The nearest calendar event is the FOMC decision on 29 Jul at 18:00, which is
19 h 29 min away. That is more than 15 min, so the storm is **unscheduled** and has no
watch.

**Alarm.** Risk by minute:

| Minute (UTC) | Mid | Strength | Risk |
|---|---|---|---|
| 13:35 | 162.799 | 2.68 | 0.27 |
| 13:36 | 162.6055 | 9.65 | 0.97 |
| 13:37 | 162.261 | 16.68 | 1.00 |

At 13:36, risk is at least `squall_on` against the long-USD book, so a squall fires. At
13:37, two consecutive minutes have `risk >= 0.80`, so the storm-level alarm fires. Its
episode is still open at the onset, so the matcher credits it.

- `minutes_from_onset = 13:37 - 13:29 = +8`.
- `move_ahead_pct = (162.261 - 158.054) / (162.7805 - 158.054) * 100 = 4.207 / 4.7265 * 100 = 89.0`.
- 89.0 >= 50, so the storm is **caught**. This is July, so the result is in-sample for the alarm.

**Ships.** The replay runs from 10:08 to 16:29. Its default window is onset ± 3 h, 10:29 to
16:29, but a replay may not open inside a danger alarm: the 10:18 alarm is still in force
at 10:29, so the window starts 10 minutes before that alarm instead (`export.storm_window`).
Both books start at 10:08's close mid, 163.2685.

- **Prepared ship.** The 10:18 alarm is read at its close; the cut fills at the **10:19 open
  bid, 162.734**: it sells 15,000,000 USD, against a mid of 162.736, a cost of $184. The
  all-clear comes at 11:44 and the restore fills at the **11:45 open ask, 163.014**, a cost of
  $92. The 13:37 alarm is read at the 13:37 close (162.261); its cut fills at the **13:38
  open bid, 162.263**, a cost of $139. The all-clear comes at 15:03 and the restore fills at
  the **15:04 open ask, 159.379**, a cost of $235. The ship ends at **$762,899**.
- **Unprepared ship.** It holds. `gross` stays at $20,000,000, so maintenance is $500,000.
  Equity at mid is `21,000,000 - 20,000,000 * 163.2685 / mid`:
  - At the 14:04 close, mid 159.37 gives equity $510,761, which is at least $500,000.
  - At the 14:05 open, mid 159.371 gives about the same: no breach.
  - At the 14:05 close, mid 159.2445 gives equity $494,614, which is below $500,000. That is
    the **margin call**. The position sells at the 14:05 close bid, 159.244, and equity
    stays at **$494,551**.

The prepared ship ends **$268,348** ahead.

The stress menu has 6 rows: the 2 Jul and 14 Jul storms, whose troughs came before the
13:28 snapshot, and the 10:02 drop of this same morning (-42 bp, P&L -$83,758), which,
labelled on the bars up to 13:28, is a storm that had already ended. A row for the main
13:29 fall would use the future, so it is not in the menu.

**Watch example (scheduled), USDJPY, 7 Aug 2026.** The release is US Employment
Situation at 12:30. The onset is at 12:20, which is within 15 min, so the storm is
scheduled.

- The watch runs from 12:00 to 12:45. The first watch minute is 12:00, so the warning is
  `12:20 - 12:00 = 20 min`.
- The storm-level alarm comes at 12:32, which is +12 min, with 59.3% of the move ahead. The storm is caught.
- The release counts once toward watch precision, although three pairs stormed.

## Where the numbers live

- `python -m storm.tune` writes `data/processed/detector_config.json`.
- `python -m storm.backtest` writes `data/processed/metrics.json`, with every figure above,
  the `definitions` block, and `provenance`: the SHA-256 of the three spot parquets,
  `contracts/calendar.csv`, the calendar content actually used (`calendar_content`: the
  verified rows, which differ from the file when `run_backtest` is given a calendar),
  `detector_config.json`, and `code`: a fingerprint per calculation module (`labels`,
  `features`, `detector`, `detector_v0`, `evaluate`, `exposure`, `backtest`, `export`,
  `equity`, `tune`) of its source file, its UPPERCASE constants as they are at run time and
  any function or class bound in it from elsewhere, so a patched constant counts.
- `python -m storm.export --all` writes `index.json`. It **refuses to run** when any part
  of `metrics.json`'s provenance differs from the inputs and code now, because that would
  put stale metrics on the evidence card. Its `metrics` hold `storms`, `alarmed`, `caught`,
  `median_move_ahead_pct`, `median_minutes_to_alarm`, `caught_first_onset`,
  `median_move_ahead_pct_first_onset`, `median_minutes_to_alarm_first_onset`,
  `false_alarms_per_day`, `false_alarm_episodes_per_day`, `watch_precision` and
  `<prepared|unprepared>_max_drawdown_<usd|pct>`, all for August.
- Every bundle's `storm` carries `first_onset_i` and the storm-level alarm the evaluator
  links to it (`alarm_i`, `alarm_minutes`, `alarm_minutes_first_onset`, `move_ahead_pct`,
  `move_ahead_pct_first_onset`); `contracts/replay_bundle.md` has the field definitions.
