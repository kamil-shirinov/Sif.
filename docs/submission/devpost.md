# Sif: a storm defence for FX traders, shown as a live 3D sea

*Tagline: the alarm sounds in the first minutes of a fast move, and two ships show what heeding it saved.*

> Every number below is taken from the repository: the [README](../../README.md), [docs/metrics.md](../metrics.md), [docs/oos/](../oos/), [docs/chips/](../chips/), [docs/tiger.md](../tiger.md) or [backend/reports/bakeoff.md](../../backend/reports/bakeoff.md). The source of each is named where it matters.

## Inspiration

A margin call is not a slow event. In SGX's data, USDJPY fell 2.9% in 54 minutes on 30 July 2026, and a trader holding a leveraged long was closed out at 14:05 with half the equity gone. The warning that would have mattered arrived after the move began, not before it. We wanted to build the thing a trader needs in those first minutes: an alarm they can trust, a cut that is already decided, and a way to *see* what the warning is worth, because a table of numbers does not make anyone act.

So the data became a sea. Volatility is the waves, risk is the sky, the alarm is a lighthouse and a foghorn, and the trader's book is a ship carrying crates. Two ships sail the same storm: one follows the alarm and throws part of its cargo overboard, one ignores it.

## What it does

Sif replays a real storm from SGX's one-minute FX data (EURUSD, USDJPY, USDSGD; spot and forwards from 1 July to 31 August 2026). The sea and sky turn, the alarm fires, the two ships diverge, and a short storm report appears whose every number was computed by code and checked by code.

- **Replay.** Press play on any of 13 SGX storms, or the NVDA and chip-sector storms. The HUD shows both ships' equity and margin buffer, a market chart with the alarm, cut and margin call marked, stress tests, and the report.
- **A watch ahead of scheduled events.** A front appears on the horizon, labelled with the release ("US Employment Situation in 12 min"), from a calendar of 12 verified releases.
- **Survive the storm.** A game for beginners: pick a storm and a leverage from 1x to 30x, see where the margin-call line sits, sail, and cut or restore as the same alarm sounds. At 10x on 30 July, "a 1% move changes your equity by about 10%", and the end card says so in plain words.
- **The navigator.** Ask "what if USDJPY drops 3% in 30 minutes?" and an AI calls deterministic tools and returns a replayable what-if storm. The answer's numbers are checked against the tools' output.
- **Sound.** Sea, wind, rain, thunder, a foghorn, a voice that says "Storm warning", and a note per market minute whose pitch follows the price.

## The two SGX challenges

**Challenge 1, "Cloudy with a chance of margin calls".** The brief is to warn a trader before leverage turns a fast move into a margin call. We found little advance warning in prices, and we say so: before 13 storms, volatility in the preceding 90 minutes was above the 95th percentile of normal for 1 storm (chance alone gives about 0.65), spreads for 3, and forward points for 0 to 2 of 13 depending on tenor (1W, 1M, 3M: 1, 2 and 0) (`scripts/no_warning_check.py`). So the product makes three defences and no price predictions. It **warns ahead for scheduled events** from the calendar (all 4 of August's scheduled storms were watched before onset, a median of 28.5 minutes ahead, the shortest 20); it **raises the alarm in the first minutes** of unscheduled ones (August's 6 storms: all 6 alarmed, a median 3.5 minutes after onset, 4 of 6 with at least half the move still ahead, against 1 of 6 for a naive rule); and it **prepares the book**, with exposure and stress tests, so the cut is decided before the alarm sounds. The alarm was tuned on July only; August is the test, and 6 storms is a small sample.

**Challenge 2, "Every trader needs to start somewhere".** *Survive the storm* is the beginner's answer: the same storm, the same alarm, and a leverage slider. A beginner learns where the margin-call line sits by losing a ship to it, then trying again at a lower leverage. The book is synthetic, labelled so on screen.

## How we built it

**Twenty-four hours at DurHack 2026, with Claude Code and Codex working under strict file ownership**, so no lane edited another's files. Every result was checked by tests and two independent audits.

- **Backend (Python).** Labels, a causal feature pipeline, the detector, the evaluation and backtest, the exposure and equity simulators, and the bundle exporter. A replay bundle is one JSON file that drives everything on screen. The detector is code: no model decides an alarm.
- **Web (React, three.js, react-three-fiber).** The 3D sea, sky and ships, the HUD and the chart (TradingView Lightweight Charts), and the Survive game. The scene is driven by bundle fields only: wave height by volatility against its trailing 24-hour level, sky by the risk score, the lighthouse by the alarm, the ship's heel and draught by its equity and margin buffer.
- **Tiger Data (TimescaleDB).** SGX's bars live in hypertables with compression and continuous aggregates, behind a small FastAPI service. See below.
- **ElevenLabs.** The sound design. See below.
- **The AI crew.** *Models read, code judges.* A **navigator** (Qwen 3.8 Max) answers what-if questions by calling deterministic tools; a **radio officer** (GLM 5.3) writes the three-or-four-sentence storm report; an **inspector** (Kimi, a different model family from the writer) audits both; a **quartermaster** enforces a budget (warn at 75% of a provider's cap, refuse at 90%). Every number a model writes is extracted and must equal a fact the code computed from the bundle, exactly or rounded at the precision written. A failed check gets one correction; after that the report is a deterministic template. In a private mode, every role runs on one H100 on Modal with GPT-OSS-120B and no external provider is called.

## Challenges we ran into

- **There is little warning in prices.** We expected volatility or spreads to lead the storms. They mostly do not, and the honest design followed from that: warn from a calendar, alarm early, prepare the book.
- **Onset is defined in hindsight.** A storm's onset is the start of its strongest 15-minute window, known only afterwards. We report `first_onset` next to it everywhere, and the 30 July storm shows why: its first onset is 10:02, three and a half hours before the main fall at 13:29. The detector did alarm at 10:18 for the first drop, and called it clear at 11:44. That alarm is scored as a false one for July, and the replay shows it.
- **A replay must never open inside an alarm.** Our first 30 July replay began at 10:29, inside an alarm, with the prepared ship still full size. The window now widens until it opens calm, at 10:08.
- **Tuning on July only.** July is in-sample. Only August is a test, so we later froze the detector and tested it on other data (below).
- **Keeping the AI honest.** A fluent report with one wrong number is worse than a plain one. The verifier, the inspector and the template fallback exist because models do invent. In the private-mode comparison, Qwen3-8B passed numeric verification on first draft for 10 of 13 reports and needed the template for 8; GPT-OSS-120B passed 13 of 13 with no fallback ([backend/reports/bakeoff.md](../../backend/reports/bakeoff.md)).
- **Two independent audits.** A second model family reviewed the backend and found 15 issues (execution timing, margin order, causality of bad prints, calendar rules, stress tests, rounding, false-alarm counting, provenance). A second review rated 12 fixed and 3 partly fixed, and found new issues in the no-warning check and the README. All are fixed with tests.

## Accomplishments we are proud of

- **The headline case.** 30 July: USDJPY fell 2.9% in 54 minutes with no scheduled release nearby. The alarm fired at 13:37, eight minutes after onset, with 89.0% of the move still ahead. The ship that followed the alarm ended at $762,899, down 23.7%; the one that ignored it was closed out at 14:05 and ended at $494,551. **The alarm kept $268,348.** It is a defence, not a profit: the prepared ship still lost $237,101. July is the tuning month, so this case is in-sample.
- **August, which tuning never saw.** 6 of 6 storms alarmed, 4 of 6 caught with at least half the move ahead, **0.33 false alert episodes per day** (0.51 alarms a day counting each pair on its own). Over August the prepared book ended at $1,033,659 against $993,889, with a maximum drawdown of 17.2% against 20.6%, after $7,038 of spread cost. Neither book had a margin call that month, so this shows a shallower drawdown, not a disaster avoided.
- **Frozen out-of-sample tests, with the misses in the tables.** (1) **Round 1**, another vendor's feed and other periods: six famous events (the SNB floor removal in 2015, the sterling flash crash in 2016, the yen flash crash in 2019, two interventions in 2022 and the carry-trade unwind of 2024) and two ordinary months. In the events, 11 storms, 9 alarmed, 5 caught; in the ordinary months, 12 storms, 10 alarmed, 4 caught, and **11 false alert episodes in 42.16 days (0.26 a day)**. Across all 14 pair-windows: 23 storms, 19 alarmed, 9 caught. (2) **Round 2**, the same frozen detector on 2025, scored a month at a time with independent weekly synthetic books. It reached **January to July**, not the full year, and only **24 of 72 pair-months** were usable (GBPUSD and AUDUSD had no usable month, a few more had empty feed files or too few trading days, and August to December was not reached). On those ordinary months: **38 storms, 32 alarmed, 10 caught**, 0.34 false alert episodes a day. The weekly books **helped in 13, hurt in 23 and made no difference in 62, for -$477,177 in total**; one margin call avoided. (3) **The chip sector**: 14 tickers over 20 trading days, where the detector, built on FX, did worse (below).
- **Tested against chance, and we report where the edge is and where it is not.** Moving the same alarms to random times (10,000 draws): on the crisis events the real alarms caught 9 of 23 where the moved ones caught a median of 0 (p=0.0001), and on SGX August 4 of 6 against a median of 0 (p=0.0006); both stay significant after Holm's correction (0.0008 and 0.0042). **On round 2's ordinary months it is not better than random timing: 10 of 38 against a median of 8, p=0.37.** Nor on the chips (6 of 19 against 3, p=0.1081). The intervals are wide: August's 4 of 6 is 66.7% with a 95% interval of 33.3% to 100%. The prepared synthetic book was ahead in August, round 1 and the chips, behind in round 2, and **0 of 4 datasets survive multiplicity correction**; with fills five bars after the signal August's +$39,770 becomes -$10,269. So: **a reliable storm alarm** (alarmed 6 of 6, 19 of 23 and 32 of 38), **an early-warning edge on big storms** (crisis events and SGX August), and **a response rule, the blunt 75% cut, that still needs work**. ([docs/stats/results.md](../stats/results.md))
- **Every number checked by code.** The README's results tables are tested against the generated metrics file; the AI's numbers are verified against facts; the OOS results can be recomputed with `python -m storm.oos.run --verify`, with no network, from hashed raw data.

## What we learned

- **Be exact about what a test can say.** Thirteen storms against 40 days each can say "little warning", not "none". Six August storms move a share by 17 points: 4 of 6 is 66.7% with a 95% interval of 33.3% to 100%.
- **A pre-registered test is only worth something if it can embarrass you.** In the first out-of-sample round the detector alarmed on 19 of 23 storms but caught only 9 with half the move still ahead, and the synthetic policy's cut was no better than holding at the SNB event (prepared ending at $346,121, unprepared at $363,481, and both books margin-called). We left that in the results.
- **Test the claim against chance, and report the part that fails.** The detection result beats randomly moved alarms on big storms (p=0.0001 and p=0.0006) but not on ordinary months (round 2, p=0.37), and the money result does not survive correction (0 of 4); round 2's weekly books lost $477,177 and five-bar fills turn August's gain into a small loss. That is why we call it a defence, not a profit, and why the cut rule is what we would work on next.
- **The detector is fast, not clairvoyant.** It finds a storm minutes after it starts. That is worth something because leverage turns minutes into margin calls, and it is the only claim we make.
- **Giving every lane a boundary made 24 hours work.** Contracts in the repo, not conversations, were what kept three lanes from stepping on each other.

## What's next

- **Quotes for equities.** The NVDA and chip data are Yahoo trades, not quotes, so the equity replays measure no spread and assume none. Real quotes would make the cost of a cut visible there too.
- **A detector built for stocks.** On the chip sector the FX detector gave 2.35 false alerts per trading day. Per-asset tuning, with the same discipline of testing on data it never saw.
- **A real book, with consent.** The trader's book is synthetic everywhere; a real one would need the exposure feed, permissions and a very different level of care.
- **A larger calendar.** 12 verified releases, assembled after we saw the storm list, is enough to show the idea and too few to measure it.
- **Prospective testing.** Everything here is historical. A forward test, with the alarm logged before the outcome, is the only evidence that would settle it.

## The chip sector, honestly

We froze the detector and ran it on 14 chip-sector tickers (Yahoo one-minute bars, 20 trading days, 19 October to 13 November 2026): NVDA, used when building the equity path and so reported apart, and 13 new names. On the new names: **19 storms, 16 alarmed, 6 caught** with at least half the move still ahead, and **47 false pair alerts over 20 trading days, 2.35 a day**. Three replays (INTC, SMCI and MRVL, the largest moves) were not caught in time; in INTC both ships were margin-called together, in MRVL only the unprepared one. The ticker universe was chosen with NVDA already observed, so this is a cross-ticker test, not a future-period one. We include it because it shows where the detector stops working: a detector tuned on FX is not a detector for stocks. ([docs/chips/results.md](../chips/results.md))

## Sponsor prizes

### Tiger Data

We use Tiger Data (TimescaleDB 2.32 on PostgreSQL 18) as the time-series store behind the live chart. SGX's bars are in two hypertables, `spot_1m` (193,049 rows) and `forward_1m` (1,661,187 rows), with 7-day chunks, compression segmented by series, and a compression policy; a third, `equity_1m` (211,948 rows), holds the chip-sector data. Three continuous aggregates (`candles_5m`, `vol_1h`, `equity_5m`) serve the candles. Measured on 15 November:

- **Compression:** 347.9 MB to 48.4 MB across the three hypertables (7.2x); the forward-curve table, the biggest, went from 269.0 MB to 26.9 MB (10.0x).
- **Queries:** the same 5-minute candles from the raw hypertable and from the continuous aggregate return identical results. Server-side, the aggregate does 2.8 to 5.5 times less work at every window (for a month of USDJPY: 29.6 ms against 5.4 ms). Over the internet from a laptop, the round trip alone is 19.4 ms, which hides the difference up to a day's candles: the wall clock is 20.4 against 19.3 ms for one hour, and 55.9 against 38.2 ms for a month. We report the hidden gap as it is.
- The HUD shows "Live · Tiger Data" and the chart prints the database's own query time. The app still plays the bundles without the service.

Full method and tables: [docs/tiger.md](../tiger.md).

### ElevenLabs

The soundscape is the alarm, not decoration: it is what a trader would hear with their eyes on another screen. **19 sounds, generated once** with `tools/audio/generate.py` and committed: five ambience loops (calm and rough sea, wind, rain, storm), eight one-shots (three thunders, a foghorn, a splash for the cut, a creak, a sinking ship, a bell), three 60-second music beds (calm, tension, storm: C minor, 80 BPM) and three stock-voice lines ("Storm warning", "Margin call", "Storm passing"). The browser crossfades them from the live risk and state, ducks the music under a voice line, and plays the margin call's sinking and voice when the unprepared ship goes down. The price melody (one soft note per market minute, pitch following the price) is not a recording: it is synthesised live in the browser with Tone.js. ([web/src/audio/README.md](../../web/src/audio/README.md))

## Built with

SGX one-minute FX data · Python, pandas, NumPy · FastAPI, psycopg · **Tiger Data (TimescaleDB)** · React, three.js, react-three-fiber, Vite, zustand · TradingView Lightweight Charts · **ElevenLabs** (sound effects, music, stock voice) · Tone.js · GLM 5.3, Qwen 3.8 Max and Kimi on Fireworks · Meta Muse · GPT-OSS-120B and Qwen3-8B on Modal · Yahoo Finance via yfinance (NVDA and the chip sector) · Dukascopy historical feed (the out-of-sample FX holdouts) · matplotlib · Claude Code and Codex.

*Team: TBC.*
