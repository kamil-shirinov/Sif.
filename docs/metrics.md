# StormScore metrics: exact definitions

Each definition below is what the backend code computes, written as a formula, with the
module that computes it. Times are UTC. One frame or bar is one minute. `mid` is the
close mid of the one-minute bar stamped `t`. Unless a section says otherwise, the
numbers come from SGX spot bars, 1 July to 31 August 2026.

Splits: **July** is the tuning month for the alarm. **August** is the test split
(`TEST_START = 2026-08-01`, `TEST_END = 2026-09-01`, end exclusive). July bars are still
read as warm-up history for the trailing 24-hour volatility.

## 1. Storm label (`storm.labels`)

Per pair, for every bar `t`:

```
ret_bp(t)    = (mid(t) / mid(t-1) - 1) * 1e4        undefined if the previous bar is > 5 min earlier
sd_24h(t)    = sd of ret_bp over the 1,440 bars before t (t excluded; at least 720 bars)
move15(t)    = (mid(t) / mid(t - 15 min) - 1) * 1e4
threshold(t) = max(30 bp, 8 * sd_24h(t - 15 min) * sqrt(15))
trigger(t)   = |move15(t)| >= threshold(t)          (undefined start price or sd: no trigger)
```

Triggering windows on the same pair less than 6 hours apart form **one storm**.
Volatility windows count bars, not clock minutes, so a weekend never dilutes `sd_24h`.

## 2. Onset, trough, move_bp, duration (`storm.labels`)

Within one storm:

```
peak window = the triggering window with the largest |move15|
onset       = start of the peak window          (peak window end - 15 min)
end         = end of the last triggering window
trough      = argmin mid over [onset, end] if the peak move is down, argmax if it is up
move_bp     = (mid(trough) / mid(onset) - 1) * 1e4      simple return, signed, rounded to 0.1
duration    = trough - onset, in minutes
```

`move_bp` is a **simple** return, not a log return. The bundle's `storm.label` is
`f"{move_bp/100:+.1f}% in {duration} min"`. A storm is a storm whichever way it moves.
Each ship's book decides whether the move is danger or a fair wind.

**Equities (NVDA, `storm.equity`).** Onset is the 11 Nov regular-session close (the last
minute before 16:00 ET). Trough is the lowest one-minute **low** (not the close) on 12 Nov,
up to the end of the replay. `move_bp = low / close - 1`. The market is closed from 20:00
to 04:00 ET. No return or detector window crosses that closed stretch: every bar carries
its session, and windows that change session are undefined. The storm report counts
**trading minutes** (pre-market, regular and after-hours sessions) from onset to trough,
not clock minutes, and states the closed stretch as a fact. For NVDA that is 572 trading
minutes out of 1,052 clock minutes, closed 12 Nov 01:00 to 09:00 UTC.

## 3. Scheduled matching (`storm.labels.scheduled_event`)

```
scheduled  iff  min over calendar events e of |onset - e.time_utc| <= 15 min     (inclusive both sides)
event      = the nearest such event (name and time); otherwise kind = unscheduled
```

The calendar is `contracts/calendar.csv`: every verified release, never filtered. A
scheduled label states timing only. It does not claim the release caused the move.

## 4. The alarm (`storm.detector`, v1, config tuned on July)

```
strength(t) = max over m in {1, 3, 5} of  |mid(t)/mid(t-m) - 1| * 1e4 / (sd_24h(t) * sqrt(m))
risk(t)     = clip(strength / 10 + w_comove * [comove >= 2], 0, 1)      tuned w_comove = 0
direction   = sign of the move in the window that set strength
```

Tuned thresholds: `squall_on = 0.75`, `storm_on = 0.80`, `storm_minutes = 2`,
`calm_off = 0.25`, `calm_minutes = 20`.

- **Episode.** Opens at the first minute with `risk >= squall_on`. It closes (the
  **all-clear**) after 20 consecutive minutes with `risk < calm_off`.
- **Storm-level detection** (direction-agnostic). The first minute in an episode that
  completes 2 consecutive minutes with `risk >= storm_on`.
- **Book-aware alarm** (what a bundle's `alarm` event shows). The same rule, counting
  only minutes where the move goes against the book's exposure.

The **scoring in sections 5 to 7 uses the direction-agnostic detection**. Bundles and the
policy use the book-aware alarm.

## 5. Alarmed, caught, minutes from onset (`storm.evaluate`)

A storm's alarm is the **earliest** storm-level detection on the storm's own pair that
meets both of these conditions:

```
onset - 60 min <= alarm <= trough        and        still in force at onset (all-clear is none or >= onset)
```

An alarm that fired and cleared before onset is not credited. Neither is one older than
60 minutes, so a detector that stays in storm state cannot game the score.

```
alarmed             = the storm has an alarm
minutes_from_onset  = alarm - onset, in whole minutes (negative when the alarm came first)
move_ahead_pct      = 100                                               if alarm <= onset
                    = 0                                                 if alarm >= trough
                    = clip((mid(alarm) - mid(trough)) / (mid(onset) - mid(trough)) * 100, 0, 100)   otherwise
caught              = alarmed and move_ahead_pct >= 50
```

**Signs.** The ratio is the share of the onset-to-trough distance still to travel, and it
is the same formula for both directions:

- **Down move** (`onset > trough`): `(mid(alarm) - trough) / (onset - trough)`.
- **Up move** (`trough > onset`): numerator and denominator both flip sign, so it equals
  `(trough - mid(alarm)) / (trough - onset)`.

In both cases, a price that has already passed the trough gives 0, and a price still at
or beyond the onset gives 100 (after clipping).

Index metrics, over August storms:

```
median_move_ahead_pct   = median of move_ahead_pct over alarmed storms      (rounded to 0.1)
median_minutes_to_alarm = median of minutes_from_onset over alarmed storms   (rounded to 0.1)
```

## 6. False storm alarms per day (`storm.evaluate.score`)

```
false alarm      = a storm-level detection in August on pair P that lies outside
                   [onset - 60 min, end + 60 min] of every labelled storm on P
days             = (number of distinct minutes in August with a bar on ANY pair) / 1,440
false_alarms_per_day = false alarms / days
```

**Cross-pair de-duplication.** The headline `false_alarms_per_day` does **none**. Each
pair's false alarm counts separately, and a storm on another pair does not excuse it. One
USD shock that alarms USDJPY and USDSGD in the same minute is two false alarms. The
de-duplicated companion figure is:

```
episodes = false alarms on any pairs, sorted by time; a new episode starts when the gap
           to the previous false alarm is > 15 min
false_alarm_episodes_per_day = episodes / days
```

August, v1: 12 false alarms over 21.52 days is **0.56 per day**. They form 8 episodes,
which is **0.37 per day**. Eight of the twelve come in four same-minute pairs. Two of
those pairs (19 Aug 12:38 EURUSD and USDSGD, 28 Aug 14:01 USDJPY and USDSGD) coincide with a real
storm on the third pair. They still count as false because the storm is on another pair.

## 7. Watch window, warning time, quiet watches (`storm.detector`, `storm.backtest`)

```
watch window(e) = [e - 30 min, e + 15 min)          half-open; state = 1 unless a storm (2) is active
```

When two windows overlap, the earlier event keeps the minute. A storm is **watched before
onset** if its pair shows `state == 1` at some minute in `[event - 30 min, onset)`. Its
warning time is:

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

## 8. Ships: fills, margin call, drawdown (`storm.exposure`, `storm.equity`)

The books are **synthetic**. FX: long USD 20,000,000 against the pair's other currency,
$1,000,000 equity, maintenance 2.5% of open notional. The policy backtest splits that
across three pairs at 6,666,667 each. NVDA: long $4,000,000 on $1,000,000 equity,
maintenance 15% of the position.

**Which price fills a trade.** Each trade fills at the mid of the minute shown below. That
mid is the close of the same bar the detector has just read, so the fill assumes zero
latency, no spread and no slippage.

| Trade | Fills at the mid of |
|---|---|
| Legs open | the first frame |
| Cut (prepared ship) | the alarm's minute: it sells 75% of the leg |
| Restore | the all-clear's minute |
| Margin call | the minute it triggers: every leg closes, and equity is held flat afterwards |

In the policy backtest, an event's minute maps to the first grid minute at or after it. A
restore is skipped if it would put the book straight into a margin call.

**Margin-call test (every minute, after that minute's trades):**

```
equity(i) = sum over currencies c of cash_c(i) * usd_rate_c(mid(i))
gross(i)  = sum over legs of |qty| * usd_rate(base currency, mid(i))
margin call at the first i with gross(i) > 0 and equity(i) < maintenance * gross(i)
```

The stress-test row's `margin_call` is a separate, endpoint-only check:
`equity + pnl < maintenance * N`, where `pnl = N * (1 - 1 / (1 + usd_move_bp / 1e4))` and
`N` is the total notional. It applies no cuts and no path.

**Max drawdown (policy backtest, `index.json` metrics):**

```
dd_usd = max over i of (max equity up to i - equity(i))
dd_pct = dd_usd / (peak at that i) * 100
```

The policy backtest runs on the three-pair book from 2 Aug 19:01 to 31 Aug 23:59 UTC.
Prepared: $191,021 (17.3%). Unprepared: $226,151 (20.6%).

## 9. Worked example: USDJPY, 30 July 2026 (`usdjpy-2026-07-30`)

**Label.** At 13:29, `sd_24h = 1.227 bp`, so `threshold = max(30, 8 * 1.227 * 3.873) = 38.0 bp`.
The strongest triggering window runs 13:29 to 13:44, with `move15 = -150.6 bp`. So:

- onset = 13:29, with mid 162.7805.
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
13:37, two consecutive minutes have `risk >= 0.80`, so the storm-level alarm fires.

- `minutes_from_onset = 13:37 - 13:29 = +8`.
- `move_ahead_pct = (162.261 - 158.054) / (162.7805 - 158.054) * 100 = 4.207 / 4.7265 * 100 = 89.0`.
- 89.0 >= 50, so the storm is **caught**. This is July, so the result is in-sample for the alarm.

**Ships.** The replay runs from 10:29 to 16:29 (onset ± 3 h), and both legs open at
162.8335.

- **Prepared ship.** It cuts 75% at 13:37, at 162.261. It restores at the 15:03 all-clear,
  at 159.375, and ends at **$844,002**.
- **Unprepared ship.** It holds. `gross` stays at $20,000,000, so maintenance is $500,000.
  Equity is `21,000,000 - 20,000,000 * 162.8335 / mid`:
  - At 14:15, mid 158.878 gives equity $502,071, which is at least $500,000.
  - At 14:16, mid 158.643 gives equity **$471,707**, which is below $500,000. That is the
    **margin call**: the position closes at 158.643 and equity stays at $471,707.

The prepared ship ends **$372,295** ahead.

**Watch example (scheduled), USDJPY, 7 Aug 2026.** The release is US Employment
Situation at 12:30. The onset is at 12:20, which is within 15 min, so the storm is
scheduled.

- The watch runs from 12:00 to 12:45. The first watch minute is 12:00, so the warning is
  `12:20 - 12:00 = 20 min`.
- The storm-level alarm comes at 12:32, which is +12 min, with 59.3% of the move ahead. The storm is caught.
- The release counts once toward watch precision, although three pairs stormed.

## Where the numbers live

- `python -m storm.backtest` writes `data/processed/metrics.json`, with every figure above
  and the `definitions` block.
- `python -m storm.export --all` writes `index.json`. Its `metrics` hold `storms`,
  `alarmed`, `caught`, `median_move_ahead_pct`, `median_minutes_to_alarm`,
  `false_alarms_per_day`, `false_alarm_episodes_per_day`, `watch_precision` and
  `<prepared|unprepared>_max_drawdown_<usd|pct>`, all for August.
