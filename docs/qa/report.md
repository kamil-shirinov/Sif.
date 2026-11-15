# Demo QA report

Run on 15 November 2026, 05:10 to 05:40 UK time, against `origin/main` at `8f88b34` (a temporary git worktree, dev server on port 5176, the 20 local bundles copied from the working copy; nothing from `web/public/bundles/` is committed).

**Result: 18 of 18 storms and 13 of 13 presenter steps pass.** No page errors, no NaN pixels. Two real defects (a duplicate React key, a missing favicon) and a few frame hitches, written up below with repros. Nothing was changed in app or backend code.

## How it was run

- Installed Google Chrome 157 through Playwright, **headed** (a real window, so the GPU is used), on an Apple M1 Pro (a 120 Hz display), viewport 1440 x 810 at a device pixel ratio of 1. The scene's adaptive quality read `tier 3` throughout.
- Storm runs: `/?storm=<id>&stats=1&debug=nan`, speed set to 16x, played from minute 1 until the end card appeared. The live API was not running, so `/api/health` returned 502 through Vite's proxy on every page load, as the README says it may: the app plays the bundles as they are.
- **NaN pixels:** with `?debug=nan` the post-processing guard paints NaN or Inf pixels magenta (255, 0, 255) and blown-out ones yellow. A full-frame screenshot every 2.5 s during play (and one at the first frame and at the end card) was scanned pixel by pixel for both.
- **Frame times:** two sources. `?stats=1`'s once-a-second `window.__sceneStats` (fps, mean frame ms, p95), and an injected `requestAnimationFrame` probe that records every frame delta (so single long frames show up, which a 1-second average hides). The probe skips the three frames after each of our own screenshots, which stall the page.
- **Presenter flow:** landing, then `1`, `H`, `H`, the end card, `L`, `2`, Survive with a cut (`C`) and a restore (`R`), `3`, `L`. Each step is asserted (URL, visible elements, playhead moving, CSS class) and screenshotted. The Survive cut was pressed at minute 212 (the alarm is at 209) and the restore at 297 to 299 (the all-clear is at 295).
- Scripts were kept outside the repo, in the session scratchpad. Six compressed screenshots are committed in `docs/qa/` (JPEG, 744 KB together), taken in a second pass without the stats badge.

## Per storm (16x to the end)

`n` = minutes in the bundle. Pixels = most magenta / most yellow pixels in any screenshot (0 / 0 is clean). fps = the median and the lowest of the once-a-second readings. p95 = the highest 1-second p95 frame time. Max frame = the longest single frame of the run (the probe). `>50 ms` = frames longer than 50 ms. Console = React errors other than the two environment ones listed above (502 on `/api/health`, 404 on `/favicon.ico`).

| storm | kind | n | play time | result | page errors | pixels (mag / yel) | median fps | min fps | worst p95 ms | max frame ms | >50 ms | console |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `usdjpy-2026-07-02` | scheduled | 521 | 8.2 s | PASS | 0 | 0 / 0 (3 shots) | 95 | 86 | 14.6 | 26 | 0 | 0 |
| `usdsgd-2026-07-02` | scheduled | 361 | 5.8 s | PASS | 0 | 0 / 0 (2 shots) | 106 | 84 | 14.8 | 18 | 0 | 0 |
| `eurusd-2026-07-02` | scheduled | 361 | 6.3 s | PASS | 0 | 0 / 0 (3 shots) | 107 | 81 | 16.9 | 117 | 1 | 0 |
| `eurusd-2026-07-14` | scheduled | 361 | 5.8 s | PASS | 0 | 0 / 0 (2 shots) | 105 | 85 | 15.6 | 125 | 1 | 0 |
| `usdjpy-2026-07-14` | scheduled | 361 | 5.8 s | PASS | 0 | 0 / 0 (2 shots) | 105 | 84 | 15.4 | 25 | 0 | 0 |
| `usdjpy-2026-07-30` | unscheduled | 382 | 6.6 s | PASS | 0 | 0 / 0 (3 shots) | 92 | 85 | 16.0 | 116 | 1 | 0 |
| `eurusd-2026-07-31` | unscheduled | 361 | 5.7 s | PASS | 0 | 0 / 0 (2 shots) | 106 | 94 | 13.6 | 125 | 1 | 0 |
| `usdjpy-2026-08-03` | unscheduled | 361 | 5.6 s | PASS | 0 | 0 / 0 (2 shots) | 117 | 90 | 15.8 | 33 | 0 | 0 |
| `usdjpy-2026-08-07` | scheduled | 361 | 5.8 s | PASS | 0 | 0 / 0 (2 shots) | 105 | 87 | 15.6 | 25 | 0 | 0 |
| `usdsgd-2026-08-07` | scheduled | 361 | 5.8 s | PASS | 0 | 0 / 0 (2 shots) | 106 | 82 | 16.7 | 125 | 2 | 0 |
| `eurusd-2026-08-07` | scheduled | 361 | 6.3 s | PASS | 0 | 0 / 0 (3 shots) | 107 | 83 | 16.1 | 133 | 2 | 0 |
| `usdjpy-2026-08-19` | unscheduled | 361 | 5.8 s | PASS | 0 | 0 / 0 (2 shots) | 105 | 89 | 15.4 | 18 | 0 | 0 |
| `eurusd-2026-08-28` | scheduled | 361 | 5.7 s | PASS | 0 | 0 / 0 (2 shots) | 105 | 84 | 15.7 | 18 | 0 | 0 |
| `nvda-2026-11-12` | unscheduled | 1801 | 21.9 s | PASS | 0 | 0 / 0 (8 shots) | 103 | 87 | 15.2 | 117 | 1 | 0 |
| `scenario-usdjpy-2026-07-30-down3-30m` | unscheduled | 31 | 0.8 s | PASS | 0 | 0 / 0 (1 shots) | 98 | 98 | 12.8 | 17 | 0 | 0 |
| `intc-2026-10-29` | unscheduled | 361 | 6.1 s | PASS | 0 | 0 / 0 (3 shots) | 107 | 87 | 15.9 | 25 | 0 | 163 |
| `smci-2026-10-20` | unscheduled | 361 | 5.8 s | PASS | 0 | 0 / 0 (2 shots) | 104 | 96 | 13.8 | 25 | 0 | 0 |
| `mrvl-2026-10-28` | unscheduled | 361 | 5.7 s | PASS | 0 | 0 / 0 (2 shots) | 106 | 86 | 16.3 | 25 | 0 | 0 |

Reading it: At 16x the median is 92 to 117 fps on every storm and the lowest one-second reading is 81 fps; the worst one-second p95 is 16.9 ms. 11 of 18 storms never have a frame over 50 ms after warm-up; the other 7 have one or two (below). `scenario-usdjpy-2026-07-30-down3-30m` is the navigator's what-if bundle (31 minutes), included because it is in `index.json`.

## Presenter flow

Max frame is the longest single frame in that step.

| step | result | max frame | what was seen |
|---|---|---|---|
| landing: open / | PASS | 615 ms | hero visible=true, HUD hidden=true; text: SGX FX · CLOUDY WITH A CHANCE OF MARGIN CALLS / StormScore / A storm defence for FX traders: the alarm sound |
| key 1: opens 30 July and plays | PASS | 109 ms | url storm=usdjpy-2026-07-30, playhead 12->18 of 382, landing hidden=true |
| replay reaches the alarm (min 210) | PASS | 18 ms | playhead 214 |
| H: clean view on | PASS | 18 ms | clean-view class=true |
| H: clean view off | PASS | 116 ms | clean-view class=false |
| end card at last frame | PASS | 18 ms | END OF THE REPLAY / Followed the alarm / $762,899 -23.7% / Afloat / Ignored it / $494,551 -50.5% / Margin call 14:05 UTC / Following the alarm kept /  |
| L: back to landing (rewound, paused) | PASS | 25 ms | hero=true, end card gone=true, url=?stats=1&debug=nan, playhead=n/a (HUD hidden) |
| key 2: Survive setup on 30 July | PASS | 117 ms | Sail button visible=true, url=?stats=1&debug=nan&storm=usdjpy-2026-07-30&mode=survive |
| Survive: Sail, then Cut at the alarm | PASS | 34 ms | at min 212: canCut before=true, after=false; SURVIVE THE STORM / synthetic book / $841,499 / -15.9% / Leverage / 10x / Cargo / 25% aboard · $2.5M / Ma |
| Survive: Restore after the all-clear | PASS | 32 ms | at min 299: canRestore before=true, after=false |
| Survive: run ends with a result card | PASS | 25 ms | Land ho! / $831,889 / -16.8% / 10x on USDJPY / At 10x, a 1% move changes your equity by about 10%. A 9.1% move against you wipes out your whole stake, |
| key 3: NVDA opens and plays | PASS | 83 ms | url=?stats=1&debug=nan&storm=nvda-2026-11-12, playhead 275->371 of 1801 |
| L: back to landing from NVDA | PASS | 24 ms | hero=true, url=?stats=1&debug=nan |

Second pass (no stats badge, no `?debug=nan`; used only for the committed screenshots): 13 of 13 pass again, no page errors. Survive's final equity depends on the exact minute the key is pressed (the first full run ended at $836,452, the next at $831,889): that is the game working, not noise.

## Worst frames

| where | frame | note |
|---|---|---|
| landing, first 3 seconds after a cold page load | 615 ms, then 310 ms and 68 ms | Shader compilation and the scene's first draws. It is before anything is presented. **Open the page about 5 seconds early.** |
| `2` (Survive setup), minute 1 | 117 ms | The scene is rebuilt for the new mode. |
| `1`, opening 30 July, minute 19 | 109 ms | First seconds of the first replay. |
| `H` pressed a second time | 116 ms | The replay ran on at 16x during this step and reached its last frame: the end card mounting. |
| `eurusd-2026-08-07`, last minute | 133 ms | The end card mounting. |
| `eurusd-2026-07-31` and `usdsgd-2026-08-07`, minute 3 | 125 ms | The first frames after play starts at 16x. |
| `eurusd-2026-07-14`, minute 38 and `eurusd-2026-07-02`, minute 37 | 125 ms and 117 ms | About half a second after play starts at 16x. No event is there (the first watch is at minute 164 and 150), and the cause was not found. |
| `3` (NVDA), minute 1 | 83 ms | Loading a 1,801-minute bundle. |

Every one is a single frame, never a run. After warm-up no storm had more than two frames over 50 ms in a 6 to 22 second run. These are not stutters a judge will see at 1x.

## Bugs and observations

**1. Duplicate React key in the market chart (INTC). Severity: low, a console error today, a possibly missing or doubled label.**
`web/src/ui/MarketChart.tsx:361` builds the chart-label key as `` `${it.mk.i}-${it.mk.text}` ``. When both ships have a margin call on the same minute, as in `intc-2026-10-29` (both at minute 189, event `margin_call` for `prepared` and for `unprepared`), the two labels get the key `189-Margin call`.
Repro: open `http://localhost:5173/?storm=intc-2026-10-29` with the browser console open, play to minute 189: React logs "Encountered two children with the same key, `189-Margin call`" (163 times in a 16x run). Expected: no warning. Suggested fix: add the ship, or the loop index, to the key. No other storm triggers it.

**2. `/favicon.ico` returns 404 on every page load. Severity: cosmetic.**
`web/index.html` has no `<link rel="icon">`, so Chrome asks for `/favicon.ico` and logs a 404. Repro: open the page, look at the console. It is the only non-React console error in any run. A one-line inline `data:` icon would clear it.

**3. At 16x the toast stack covers the scene. Severity: presentation.**
Four or five toasts stack at the top centre and cover the ship labels (`docs/qa/02-replay-storm.jpg` and `04-end-card.jpg` show it). At 1x it is one or two. Pressing `H` hides them, so the presenter flow (`1`, `H`) is unaffected. Advice: do not demo at 16x with the panels on.

**4. The evidence card says "measured on August" under the NVDA replay.**
On `nvda-2026-11-12` (see `docs/qa/06-nvda.jpg`) the left card still shows the SGX August figures (6 of 6 alarmed, 0.33 false episodes a day). It is correct for the detector, but a judge may read it as NVDA's own record. Hiding the card for non-SGX storms, or retitling it, would avoid the question.

**5. Not tested here.**
Audio output (Chrome logged "The AudioContext was not allowed to start" before the first keypress, which is the browser's rule; the keys count as the gesture afterwards, but nothing here listens to the sound). The live Tiger Data API. Retina (device pixel ratio 2) frame times: these runs are at ratio 1, so a projector or a Retina display will cost more per frame; the `Low quality` checkbox and the adaptive tiers exist for that. Other browsers and other GPUs. The 1920 x 1080 and 2560 x 1440 layouts.

## Screenshots

| | |
|---|---|
| `docs/qa/01-landing.jpg` | landing page |
| `docs/qa/02-replay-storm.jpg` | 30 July at minute 294: both ships' alarm, cut, margin call and fair wind |
| `docs/qa/03-clean-view.jpg` | the presenter's clean view (`H`) |
| `docs/qa/04-end-card.jpg` | the end card, $762,899 against $494,551 |
| `docs/qa/05-survive-cut.jpg` | Survive after a cut at the alarm |
| `docs/qa/06-nvda.jpg` | NVDA replay |
