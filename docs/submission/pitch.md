# StormScore pitch scripts

Two scripts, word for word, that follow the landing page and the presenter keys: **landing, `1`, the false alarm and the real storm, `H`, the end card, `2` (Survive), `L`**. Words to say are in plain text. Keys and what is on screen are in `[brackets]`. Times are from the moment the key is pressed. Every number is in the table at the end with its source file.

## Before you go on (two minutes of setup)

1. Open the app, **wait five seconds** on the landing page. The first seconds after a cold load have two long frames (about 0.6 s and 0.3 s, [docs/qa/report.md](../qa/report.md)); do not start while they happen.
2. **Click once anywhere** so the browser lets the sound start. Check the speaker icon at the top of the HUD is on.
3. **Set the speed once.** Press `1`, choose the speed in the drop-down at the bottom left (**2x for the 2-minute script, 1x for the 4-minute one**), press `L`. The speed stays until the page is reloaded.
4. Zoom the browser so the landing text is readable from the back of the room. Do not demo at 16x with the panels on: the toasts pile up over the ships.
5. Keys are ignored while a text box has focus (the navigator's question box, the leverage slider). Click on the sea first if a key does nothing.
6. If the sound fails, say nothing about it and carry on: the replay works silently.

## 2-minute script (about 280 words)

**[LANDING: the wide shot, the three figures showing: 6 of 6, 4 of 6, 0.33]** *(0:00)*

Every trader knows the call that comes too late. StormScore is a storm defence for FX traders, shown as a live sea. We started from SGX's one-minute data and asked the honest question first: is there warning in the prices? Mostly, no. So we never predict. We warn ahead from a calendar, we sound the alarm in the first minutes, and we prepare the book.

**[Press `1`. 30 July opens and plays at 2x.]** *(0:30)*

Thirtieth of July, USDJPY. Two ships, one synthetic book, the same storm.
*(0:35, the first squall, alarm and cut captions appear; about 1 s in)*
An early alarm at ten-eighteen: a drop that steadied. We show it, and we count it as a false alarm.
*(about 12 s in, the all-clear)*
Then nearly two hours of calm. Our test is August, which tuning never saw: six of six storms alarmed, four with at least half the move still ahead.
*(about 26 s in, the lighthouse lights, the foghorn and the voice)*
Thirteen twenty-nine: USDJPY falls 2.9% in 54 minutes. The alarm sounds at thirteen thirty-seven, eight minutes in, with 89% of the move still ahead. One ship cuts three quarters of its cargo.
*(about 30 s in, the sinking and the "Margin call" voice)*
The other is closed out at two-oh-five.

**[Press `H`. The panels leave; the ships, captions and timeline stay.]** *(about 38 s in)*
Panels away: this is the view for a trading floor.
**[Press `H` again.]**

**[The END CARD appears at about 48 s]** 

$762,899 against $494,551. The alarm kept $268,348. Not a profit: the ship that cut still lost 24%. A defence. And we froze the detector and tested it on other data, misses included: twenty-three storms, nineteen alarmed, nine caught with half the move ahead. On the big storms the alarm beats random timing; on ordinary months it does not, and our simple cut rule lost money there. We say so.

**[Press `L` (the camera pulls back to the landing), then `2`. The Survive setup opens.]**

And for the beginner who has never met a margin call: Survive the storm. Pick a leverage, sail the same storm, and find the line by sinking.

**[Press `L`.]**

Every number you saw was computed by code and checked by code. Tiger Data serves the chart, ElevenLabs makes the storm. StormScore: a warning you can see.

> *Cut if short on time:* drop the "Our test is August" sentence and the "On stocks it is worse" sentence.

## 4-minute script (about 560 words)

Play it at **1x**. The 30 July replay then takes 95 seconds, and its key moments fall at: false alarm 2.5 s, its all-clear 24 s, the real alarm 52 s, the margin call 59 s, the second all-clear 74 s, the end 95 s. Speak in the gaps; the sea does the rest.

**[LANDING]** *(0:00 to 1:00)*

Every trader knows the call that comes too late: a fast move, a margin call, and the warning arrives after the loss.

StormScore is a storm defence for FX traders, shown as a live sea. Volatility is the waves, risk is the sky, the alarm is a lighthouse, and the trader's book is a ship carrying crates. We built it for SGX's challenge, "Cloudy with a chance of margin calls".

First, the honest question: is there warning in the prices? We measured the ninety minutes before each of thirteen storms. Volatility was above the ninety-fifth percentile for one; chance alone gives about two thirds of one. So: little advance warning. Thirteen storms is a small test, so we say "little", not "none".

So three defences, and no price predictions, ever. Warn ahead for scheduled events, from a calendar. Sound the alarm in the first minutes of an unscheduled storm. And prepare the book, so the cut is decided before the alarm.

On August, which tuning never saw: six storms, all six alarmed, four caught with at least half the move still ahead, and 0.33 false alert episodes a day.

**[Press `1`. 30 July opens and plays at 1x.]** *(1:00)*

Thirtieth of July, USDJPY. Two ships, one synthetic book, the same storm. One follows the alarm, one ignores it.

*(2.5 s in: the squall, alarm and cut)*
Ten-eighteen: the alarm fires, and the prepared ship cuts. USDJPY had dropped 0.4% in fifteen minutes. Then it steadied.

*(24 s in: all-clear, the cargo comes back)*
That was a false alarm. We count it as one. Nothing in the data tells you in advance which drop will steady.

*(30 to 50 s in: calm sea)*
Nearly two hours of calm. This storm is unscheduled: the Fed's decision was nineteen hours earlier. No calendar helps. This is the case the alarm is for.

*(52 s in: the foghorn, "Storm warning"; the cut)*
Thirteen twenty-nine: USDJPY falls 2.9% in 54 minutes. The alarm sounds at thirteen thirty-seven, eight minutes in, with eighty-nine percent of the move still ahead. The prepared ship cuts.

*(59 s in: the sinking, "Margin call")*
The ship that ignored it is closed out at two-oh-five.

**[Press `H` at about 80 s.]** Panels away: the view for a trading floor. **[Press `H` again.]**

**[END CARD at 95 s]**

$762,899 against $494,551. Following the alarm kept $268,348. To be exact: the prepared ship still lost $237,101. A defence, not a profit. And July is the tuning month, so this case is in-sample.

**[Keep the end card up.]** *(about 2:50)*

So we froze the detector and tested it on another vendor's data, before downloading a single bar: six famous events, from the SNB in 2015 to the 2024 carry unwind, and two ordinary months. Twenty-three storms, nineteen alarmed, nine caught with half the move ahead. And we asked whether luck could do it: we moved the same alarms to random times, ten thousand times. On the crisis events they caught a median of zero storms; ours caught nine, p equals one in ten thousand. On August, four against zero. The honest part: on ordinary months of 2025, ten of thirty-eight, no better than random timing, and the simple cut rule lost four hundred and seventy-seven thousand dollars over the weekly test books. So: a reliable alarm, an early-warning edge on big storms, and a response rule that still needs work. On fourteen chip stocks it is worse: six of nineteen caught, and 2.35 false alerts a trading day. A detector tuned on FX is not a detector for stocks. Every miss is in the tables.

**[Press `L`, then `2`.]** *(about 3:20)*

Challenge two: every trader needs to start somewhere. Survive the storm: same storm, same alarm, and you pick the leverage. The red line is where the broker closes you out. At ten times, a one percent move is about ten percent of your equity.

**[Choose 8x in the speed menu, press Sail. The run takes 12 seconds: press `C` when the foghorn sounds (about 7 s in) and `R` at the bell (about 10 s in).]**

Cut when it sounds, restore when it clears, and the end card tells you in plain words what that was worth.

**[Press `L`.]** *(about 3:40)*

Models read, code judges: an AI writes the report, and code checks every number it wrote. Tiger Data serves the candles. ElevenLabs makes the storm. Nothing here predicts a price; it tells you a storm is under way, in the first minutes, while there is still a move to cut. StormScore: a warning you can see.

> *If you run long:* cut "Nothing in the data tells you in advance…", the chip sentence, and the "honest part" sentences (keep the sentence that starts "So: a reliable alarm"). *To add NVDA (about 15 s):* press `3` after Survive and say "One more: NVDA, this week. Real prices, but Yahoo gives trades, not quotes, so there is no spread to measure, and we do not pretend there is." Then `L`. (The speed stays at 8x: set it back to 1x before the next show.)

## The numbers to say, and where they come from

| You say | Number | Source |
|---|---|---|
| Thirteen storms in July and August; nine scheduled, four not | 13; 9; 4 | [README](../../README.md), [docs/metrics.md](../metrics.md) |
| Volatility above the 95th percentile before 1 of 13 storms; chance gives about 0.65 | 1 of 13; 0.65 | [docs/no_warning_check.md](../no_warning_check.md) |
| August: six of six alarmed | 6 of 6 | README, `docs/metrics.md` |
| Four of six caught with at least half the move ahead (a naive rule: one of six) | 4 of 6; 1 of 6 | README |
| Median alarm 3.5 minutes after onset, 57.4% of the move ahead | 3.5; 57.4 | README |
| 0.33 false alert episodes a day (0.51 alarms a day counting each pair) | 0.33; 0.51 | README |
| Calendar: all four scheduled August storms watched first, median 28.5 minutes, shortest 20 | 4 of 4; 28.5; 20 | README |
| The 30 July storm: -2.9% in 54 minutes, 13:29 to 14:23 UTC | 2.9; 54 | README, `docs/metrics.md` section 9 |
| The alarm at 13:37, eight minutes after onset, 89.0% of the move ahead | 13:37; 8; 89.0 | README |
| The early alarm at 10:18, cleared at 11:44; first onset 10:02 | 10:18; 11:44 | README |
| Prepared ship $762,899 (-23.7%), unprepared $494,551 (margin call 14:05); $268,348 kept; prepared still lost $237,101 | as written | README, end card |
| Cut fills at 162.263 (bid); restore at 159.379 (ask) | 162.263; 159.379 | README |
| Survive: leverage 1x to 30x; at 10x a 1% move is about 10% of equity; a 9.1% move wipes out the stake, and the broker closes at 7.0% | as written | the Survive end card (10x on USDJPY) |
| Round 1 frozen holdout, all windows: 23 storms, 19 alarmed, 9 caught | 23; 19; 9 | [docs/oos/results.md](../oos/results.md) |
| Round 1 ordinary months: 0.26 false alert episodes a day over 42.16 days | 0.26; 42.16 | `docs/oos/results.md` |
| Chip sector (13 new tickers): 19 storms, 6 caught, 2.35 false alerts per trading day | 19; 6; 2.35 | [docs/chips/results.md](../chips/results.md) |
| Same alarms moved to random times (10,000 draws): round 1 caught 9 vs a median of 0, p=0.0001; August 4 vs 0, p=0.0006; after Holm 0.0008 and 0.0042 | as written | [docs/stats/results.md](../stats/results.md) |
| Round 2 ordinary months: 10 caught vs a median of 8, p=0.3704 (0.7407 corrected): not better than random timing | as written | `docs/stats/results.md` |
| Chips against chance: 6 caught vs a median of 3, p=0.1081 (0.3243 corrected): not distinguishable from chance | as written | `docs/stats/results.md` |
| August 4 of 6 caught: 66.7%, 95% interval 33.3% to 100% (40.0% to 100% by event date) | as written | `docs/stats/results.md` |
| Money result: ahead in August (+$39,770), round 1 (+$487,286) and chips (+$660,809), behind in round 2 (-$477,177); corrected p 0.2398, 0.2398, 1.0000, 0.1439: 0 of 4 survive | as written | `docs/stats/results.md` |
| Five-bar fills: August +$39,770 becomes -$10,269 | as written | `docs/stats/results.md` |
| Round 2 (January to July 2025; 24 of 72 pair-months usable): 38 storms, 32 alarmed, 10 caught; 0.34 false episodes a day; weekly books helped 13, hurt 23, tied 62, total -$477,177; one margin call avoided | 38; 32; 10; 0.34; 13; 23; 62 | [docs/oos/results-2.md](../oos/results-2.md) |
| Tiger Data: 347.9 MB compressed to 48.4 MB (7.2x); aggregate 2.8 to 5.5 times less server work | as written | [docs/tiger.md](../tiger.md) |
| ElevenLabs: 19 sounds generated once | 19 | [web/src/audio/README.md](../../web/src/audio/README.md) |

## Words we do not use

- **"Predict" or "forecast"** about prices. Say "detects", "warns", "alarm in the first minutes".
- **"Profit"** about the prepared ship. It lost $237,101. Say "defence", "kept".
- **"A year"** or **"full-year validation"** about round 2: it is January to July. **"Significant"** about the money result, and **"proves"** or **"validated"** about the out-of-sample tests. They are frozen historical holdouts with the misses in the tables, not a forward test.
- **"Real trader"** or **"real book"**. The book is synthetic, and the screen says so.
