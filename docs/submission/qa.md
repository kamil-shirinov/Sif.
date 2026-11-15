# Thirty hard questions, with honest answers

For a quant judge. Each answer is short and states its own limit. Where a number appears, it is in the file named under **Source**. File paths are relative to the repository root. If an answer and a source ever disagree, the source wins.

**Contents.** Look-ahead and method (1 to 7) · The alarm's results (8 to 13) · Spreads, latency and the book (14 to 19) · Why FX, and what we do not claim (20 to 22) · The AI's role (23 to 26) · The out-of-sample and chip results (27 to 30)

---

## Look-ahead and method

### 1. Does the alarm look ahead?

No, and we tested it directly rather than argue it. Each minute's strength uses only that minute and earlier ones: the move over the last 1, 3 and 5 minutes divided by the pair's own trailing 24-hour volatility, computed from the 1,440 bars before it. `scripts/causality_check.py` runs the detector on the full series and again on series cut off at a chosen time, with every later bar physically removed, and compares everything the detector said up to the cut-off (strength, risk, direction, state, and every episode, storm-level alarm and all-clear). It did this at 174 cut-offs across the three pairs, drawn at random and around each pair's own alarms; **all were identical**. A deliberately forward-looking control (the price two bars ahead) is caught at every cut-off, so the check can fail. *Limits:* it tests the detector, not the labels (next question), and not the calendar.
**Source:** [scripts/causality_check.py](../../scripts/causality_check.py), [docs/causality_check.json](../causality_check.json), [docs/metrics.md](../metrics.md) section 4.

### 2. The storm labels use the whole history. Isn't that look-ahead?

It is hindsight, on purpose, and only for scoring. A storm's `onset` is the start of its strongest 15-minute window, which you only know afterwards, and "share of the move still ahead" uses the trough. Those score the alarm; they never feed it. Because onset is hindsight, we report `first_onset` (the start of the first triggering window, which can be hours earlier) next to it everywhere. A test shows full-history labels are not point in time, and that the `label_as_of` variant is.
**Source:** [docs/metrics.md](../metrics.md) sections 1, 2 and 5; [backend/tests/test_audit2.py](../../backend/tests/test_audit2.py) (`test_1_full_history_labels_are_not_point_in_time_and_label_as_of_is`).

### 3. What exactly was tuned, and on what?

The alarm was tuned on July only, by a grid of 216 settings: the move windows (1 minute, or 1, 3 and 5), the cross-pair co-move weight, the storm threshold (0.5 to 1.0), the minutes it must hold (1 to 3), and the calm threshold (two values). The objective: most July storms caught, subject to at most one false storm alarm a day across the three pairs; ties go to fewer false alarms. Then `squall_on` was set, also on July. The code reads only July rows when tuning, and asserts that no row outside the month was read. The chosen setting is storm level 0.8 for 2 minutes, calm below 0.25 for 20 minutes, no co-move weight.
**Source:** [backend/storm/tune.py](../../backend/storm/tune.py), [docs/metrics.md](../metrics.md) section 4.

### 4. So 30 July is in-sample. Why is it your headline?

Because it is the clearest story, and we label it in-sample everywhere: the README, the landing page ("July was the tuning month") and the pitch. The evidence that matters is August (tuning never saw it) and the frozen out-of-sample tests, where the misses are in the tables.
**Source:** [README.md](../../README.md) ("Honesty notes"), [web/src/landing/README.md](../../web/src/landing/README.md).

### 5. Six August storms is a tiny test. What can it support?

Not much, and we say so. One storm moves a share by 17 points: "4 of 6 caught" is compatible with a wide range of true rates. It supports "the alarm worked on this month", not a rate. That is why we froze the detector and ran it on other data (questions 27 to 30).
**Source:** [README.md](../../README.md) ("Results on August").

### 6. "Caught means at least 50% of the move still ahead": isn't 50% arbitrary?

Yes. It is a round threshold chosen before looking at August. So we also report the median share of the move still ahead (57.4% in August, against 6.2% for the naive rule) and the median minutes after onset (3.5), which do not depend on the cut-off, and the same two measured from `first_onset`.
**Source:** [docs/metrics.md](../metrics.md) section 5, [README.md](../../README.md).

### 7. You built the event calendar after seeing the storms. Isn't that cheating?

It would be, if the watch used anything a trader did not already have. The calendar lists 12 releases from public schedules (the BLS release schedules for July and August, and the Federal Reserve's FOMC calendar), and a release's time is published in advance, so a watch built from it uses nothing new. But the *selection* of which releases to list was made after seeing the storm list, and we say so. A scheduled label states timing only (onset within 15 minutes of a release); it does not claim the release caused the move.
**Source:** [README.md](../../README.md) ("Honesty notes"), [contracts/calendar.csv](../../contracts/calendar.csv), [docs/metrics.md](../metrics.md) section 3.

---

## The alarm's results

### 8. Is there really no warning in prices?

"Little", not "none", from thirteen storms. In the 90 minutes before onset, volatility ranked above the 95th percentile of normal windows (same pair, same clock time, overlapping windows excluded) for 1 of 13 storms; chance alone gives about 0.65. Spread was above the 95th for 3 of 13, but two of those are the 2 July storms whose window leads into the payrolls release: spreads widen ahead of a scheduled release, which is the calendar's warning, not a price signal. Forward points (1W, 1M, 3M) were above the 95th for 1, 2 and 0. The one volatility exception, 3 August, began in the first hours after the Sunday-evening open.
**Source:** [docs/no_warning_check.md](../no_warning_check.md), [docs/no_warning_check.json](../no_warning_check.json), [scripts/no_warning_check.py](../../scripts/no_warning_check.py).

### 9. What is the false-alarm rate?

In August, 7 false alert episodes in 21.52 observed days: **0.33 a day**, about one every three days. Counting each pair's alarm on its own (a USD shock that alarms USDJPY and USDSGD counts twice) it is 0.51 a day. On the frozen test's two ordinary months it was 11 episodes in 42.16 days, 0.26 a day. On the chip stocks it was far worse (question 29). A "false alarm" means an alarm outside every labelled storm's window, not a judgement that the alert had no value.
**Source:** [README.md](../../README.md), [docs/oos/results.md](../oos/results.md), [docs/metrics.md](../metrics.md) section 6.

### 10. Your naive baseline had no false alarms in August. So is it better?

No: it is a ruler for lateness, not a competitor. The naive rule alarms on the first minute the 15-minute move already exceeds the storm threshold, which is the labelling rule itself. It caught 1 of 6 with a median 6.2% of the move ahead, 13 minutes after onset, against 4 of 6, 57.4% and 3.5 minutes. Its zero false alarms is what August's data showed, not a property of the rule: a crossing that the 6-hour merge later folds into a bigger storm, hours before its onset, is a false alarm, and a two-drop synthetic series gives one (a test shows it).
**Source:** [README.md](../../README.md), [backend/tests/test_audit2.py](../../backend/tests/test_audit2.py) (`test_5_naive_baseline_false_alarms_on_the_two_drop_toy`).

### 11. The watch has a precision of 0.29. Isn't that useless?

It is low and we state it: of 7 August releases, 5 passed without a storm. A watch means "be ready", not "a storm is coming". Its value is the other side: all 4 of August's scheduled storms were watched before onset, with a median of 28.5 minutes and a minimum of 20, so with the alarm, all 6 August storms were covered (watched before onset, or caught).
**Source:** [README.md](../../README.md) ("Watch and coverage").

### 12. The 30 July alarm came 8 minutes after onset. Is that fast enough to matter?

At 13:37 the move was still 89.0% ahead, and the prepared ship's cut filled at the next bar's open bid, 162.263. For a book on 20x leverage, eight minutes of a 54-minute fall is the difference between being closed out at 14:05 and ending the day down $237,101 instead of $505,449. The limit is the bar size: the data is one-minute bars, so we cannot say anything about seconds.
**Source:** [README.md](../../README.md) ("The 30 July case"), [docs/metrics.md](../metrics.md) section 9.

### 13. That 30 July replay had an earlier alarm that was false. Why show it?

Because hiding it would make the headline look better than the detector is. The first drop (10:02 to 10:17, 41.6 bp) crossed the storm threshold and steadied; the alarm fired at 10:18, cleared at 11:44, and July's scoring counts it as a false alarm. The replay starts at 10:08, ten minutes before it, so the viewer sees it. The prepared ship cuts and restores around it at a cost.
**Source:** [README.md](../../README.md) ("The earlier move"), [docs/metrics.md](../metrics.md) section 9.

---

## Spreads, latency and the book

### 14. Do you model spreads and execution?

For FX, yes: a signal is read at bar `t`'s close and fills at the next bar's open, side-correct (selling the base currency gets the bid, buying pays the ask), and each fill records its cost against mid. In August, 22 fills cost $7,038 of spread. Margin is tested at each bar's open before any trade, and again at its close. We do not model slippage beyond the quoted spread, market impact, partial fills or requotes.
**Source:** [docs/metrics.md](../metrics.md) section 8, [README.md](../../README.md), [backend/tests/test_audit.py](../../backend/tests/test_audit.py).

### 15. What about latency?

The data is one-minute bars, so the smallest delay we can express is one bar: alarm at the close, trade at the next open. The "3.5 minutes median after onset" is bar time. Network, feed and order latency in a real system are not modelled, and nothing here measures a live deployment. The detector is a single pass over bars, but we have not run it on a live feed.
**Source:** [docs/metrics.md](../metrics.md) section 8.

### 16. In a flash crash there may be no liquidity to cut into. Do you handle that?

No. A fill at the next bar's bid or ask assumes the market is there. In the SNB case (round 1) the books were margin-called in both the prepared and unprepared simulation, and the prepared one ended slightly worse (about $346,121 against $363,481); we left it in the results. A cut that cannot fill is a risk we do not simulate.
**Source:** [docs/oos/results.md](../oos/results.md) (SNB floor removal, USDCHF policy).

### 17. Is the trader's book real?

No. It is synthetic everywhere and labelled so on screen: long USD 20,000,000 on $1,000,000 equity for a single pair (2.5% maintenance), three equal legs in the August backtest, and long $4,000,000 of NVDA on $1,000,000 for equities (15% maintenance). No personal or client data is used. A real book would need an exposure feed and permissions.
**Source:** [README.md](../../README.md) ("Honesty notes"), [docs/metrics.md](../metrics.md) section 8.

### 18. In August neither book had a margin call. What did the defence buy?

A shallower drawdown, not a margin call avoided. The prepared three-pair book ended at $1,033,659 against $993,889, with a maximum drawdown of 17.2% against 20.6% (in dollars $191,261 against $226,151), after $7,038 of spread cost over 11 cuts and 11 restores. One month and one invented book: it demonstrates the mechanism and is not a performance claim.
**Source:** [README.md](../../README.md) ("Policy backtest").

### 19. Why cut 75%? Did you optimise it?

It is a fixed parameter of the exposure engine (`CUT_FRACTION = 0.75`), not part of the detector's tuning grid, and we did not search for a better one. A different fraction would change the policy numbers, not the alarm's.
**Source:** [backend/storm/exposure.py](../../backend/storm/exposure.py), [backend/storm/tune.py](../../backend/storm/tune.py).

---

## Why FX, and what we do not claim

### 20. Why FX?

It is SGX's challenge ("Cloudy with a chance of margin calls"), and the product is about leverage: FX is traded on margin, a margin call is a leverage event, and the SGX data (spot and nine forward tenors for three pairs, one-minute bars) is a clean testbed. The rule itself is price-only, so it runs on any series, but the chip result (question 29) shows it should not be assumed to work on stocks without its own tuning.
**Source:** [README.md](../../README.md), [docs/chips/results.md](../chips/results.md).

### 21. Do you predict prices?

Never. The detector says a storm is under way; the calendar says one may be near. We found little advance warning in the data and built around that. Any wording that implies prediction is a mistake in our text, not a claim.
**Source:** [README.md](../../README.md) ("Honesty notes"), [CLAUDE.md](../../CLAUDE.md).

### 22. Does Survive the storm teach anything?

We have not tested it on anyone, so we do not claim a learning effect. What it does is mechanical and checkable: it shows where the margin-call line sits for the chosen leverage (at 10x on 30 July, a 1% move is about 10% of equity, a 9.1% move wipes out the stake, and the broker closes the position earlier, at 7.0%), and lets the player cut and restore on the same alarm. Its equity is computed in the browser and checked against the backend; the method is in the web README.
**Source:** [web/README.md](../../web/README.md), [docs/qa/report.md](../qa/report.md).

---

## The AI's role

### 23. What does the AI actually do, and what does it not do?

It does three jobs and decides nothing about risk. A navigator answers what-if questions by calling deterministic tools (`scenario`, `stress_test`, `get_exposure`, `list_storms`) and returns a replayable what-if storm. A report writer turns facts that code computed into three or four sentences. An inspector, from a different model family, audits both for invented causes and wrong associations. Every alarm, watch and all-clear comes from the code detector, with no model in the loop.
**Source:** [README.md](../../README.md) ("The AI crew"), [backend/storm/ai/README.md](../../backend/storm/ai/README.md).

### 24. Can the AI put a wrong number on screen?

It is designed not to. Every number a model writes is extracted and must equal a fact the code computed from the bundle, exactly or rounded at the precision written. A failed check gets one correction with the bad numbers; after that, the report is a deterministic four-sentence template, and an inspector flag also sends it to the template. In the 15-bundle report comparison, GLM 5.3 had 15 of 15 first drafts numerically verified, no flags and no fallbacks. The check covers numbers, not every kind of misleading phrasing, which is the inspector's job and is not perfect.
**Source:** [backend/reports/bakeoff.md](../../backend/reports/bakeoff.md), [backend/storm/ai/README.md](../../backend/storm/ai/README.md).

### 25. Why those models?

They were chosen by measurement, on the same frozen inputs. Reports: GLM 5.3 (15 of 15 first drafts verified, no fallbacks, 4.31 s mean, $0.0044 a report) replaced Meta's Muse Spark, which had one format correction, a slower 10.17 s mean and $0.0087 a report. Navigator: Qwen 3.8 Max, on a fixed ten-question comparison, had 10 of 10 final answers verified with correct tool calls, the joint-most no-fallback successes (8 of 10, tied with Muse Wonder), the fastest mean (7.67 s, all ten under 15 s) and the second-lowest cost ($0.133 for the ten). Two Qwen answers still fell back to the template, and we do not call that perfect.
**Source:** [backend/reports/bakeoff.md](../../backend/reports/bakeoff.md).

### 26. What is "private mode", and what does it cost in quality?

With `LLM_PRIVATE_MODE=1` every live role, the inspector included, runs on one H100 on Modal with public GPT-OSS-120B weights, and no external model provider is called. In the 13-bundle SGX comparison it had 13 of 13 first drafts numerically verified and 11 of 13 accepted at first draft, with no template fallback; the smaller Qwen3-8B had 10 of 13 and 5 of 13 with 8 fallbacks. Its inspector shares the writer's weights, so it is a separate role, not an independent family. The endpoint scales to zero and needs waking three to five minutes before use.
**Source:** [backend/reports/bakeoff.md](../../backend/reports/bakeoff.md), [tools/modal/README.md](../../tools/modal/README.md).

---

## The out-of-sample and chip results

### 27. What was the first out-of-sample test, and what did it show?

A frozen holdout on another vendor's data, from periods outside SGX's two months, registered (config, code fingerprints, event list) and pushed before any download. Six famous events (the SNB floor removal in 2015, the sterling flash crash in 2016, the yen flash crash in 2019, two interventions in 2022, the 2024 carry-trade unwind) and two ordinary months (March 2024 and June 2025). Events: 11 storms, 9 alarmed, 5 caught. Ordinary months: 12 storms, 10 alarmed, 4 caught, 11 false alert episodes in 42.16 days. All windows: 23 storms, 19 alarmed, 9 caught. The detector alarms on most storms but catches fewer than half with half the move still ahead. The events were chosen by name, so their rate is a stress-case result, not a rate, and it is not evidence of price prediction.
**Source:** [docs/oos/results.md](../oos/results.md), [docs/oos/preregistration.md](../oos/preregistration.md).

### 28. And the policy in that test? Did the prepared ship do better?

Mixed, and we show it. Summed over the six event books (each reset independently), the prepared ship lost $802,978 against $1,297,798 for the unprepared one, but each had 3 margin calls, and at the SNB event the prepared book ended slightly worse. In the two ordinary months the prepared books lost $340,201 against $332,668, paying $4,746 of spread. The books are synthetic and reset per window, and non-USD crosses have no valued policy.
**Source:** [docs/oos/results.md](../oos/results.md) ("Policy totals").

### 29. What happened on the chip stocks?

The detector did worse, and we published it. Across 13 new tickers over 20 trading days: 19 storms, 16 alarmed, 6 caught with at least half the move ahead, and 47 false pair alerts, 2.35 a trading day. The three replays (INTC, SMCI, MRVL, the largest moves) were all missed, and in INTC both ships were margin-called together. The ticker universe was picked with NVDA already observed, so it is a cross-ticker test, not a future-period one; Yahoo gives trades, not quotes, so no spread is measured; sector moves are correlated. The reading is that a detector tuned on FX is not a detector for stocks.
**Source:** [docs/chips/results.md](../chips/results.md), [docs/chips/preregistration.md](../chips/preregistration.md).

### 30. What did the second out-of-sample round (a full year of 2025) show?

It was still running when this was written, so we claim nothing from it yet. It uses the same frozen detector, registered and pushed before its download, on a full year of 2025 (monthly detector scoring, weekly independent synthetic books), and its June 2025 overlaps round 1, as registered. Read its result file before answering with a number.
**Source:** `docs/oos/results-2.md` (when published), `docs/oos/preregistration-2.md`.

---

## If they ask something we have not covered

Say what is true: we found little advance warning in the data; the alarm is fast, not clairvoyant; July is in-sample; the book is synthetic; the out-of-sample tests include the misses. Then point to the file. Do not say "predict", "proves" or "profit".
