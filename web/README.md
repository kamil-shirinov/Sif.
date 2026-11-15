# StormScore web (lane CC-W)

A 3D storm replay and a beginner's game. It plays one replay bundle (`contracts/replay_bundle.md`, schema_version 1) as a live sea: the sky turns, the alarm fires, and two ships show what the warning saved. Every visual is driven by a bundle field; nothing is decoration. A mode switch in the HUD (**Replay | Survive**) turns the same sea into "Survive the storm": you sail your own ship through the storm, with a leverage you choose (see "Survive the storm" below).

```bash
cd web && npm install && npm run dev
```

Open `http://localhost:5173/`. It opens on calm water and auto-plays after 2 seconds. There is no title screen.

Which storm opens: `?storm=<storm_id>` if given; otherwise, when `public/bundles/index.json` exists, `usdjpy-2026-07-30` if it is listed, else the storm with the largest move in it; otherwise `mock_storm`. With no server and no `index.json` it plays exactly the committed `mock_storm`, plus the storm picker and report panel.

| URL parameter | Effect |
|---|---|
| `?storm=<storm_id>` | load that storm (the file named in `index.json`, else `public/bundles/<storm_id>.json`). The picker keeps this parameter up to date |
| `?at=<frame>` | start at a frame (handy for demos and screenshots) |
| `?autoplay=0` | do not auto-play |
| `?quality=low` | start in low quality (no reflections, no bloom) |
| `?mode=survive` | open in Survive mode (setup for the chosen storm, paused) |
| `?stats=1` | an overlay with fps, frame time (mean and p95 over the last second), draw calls and triangles per frame (the mirror and post-processing passes included), pixel ratio and quality tier (`scene/Stats.tsx`); also on `window.__sceneStats` |
| `?tier=0..3` | pins the adaptive quality tier (see Controls), for measuring like with like |
| `?debug=nan` | paints every NaN or Inf pixel of the rendered scene magenta, and every finite pixel brighter than the guard's cap (48) yellow. Needs the high-quality path |
| `?hide=<parts>` | leaves scene parts out, comma-separated: `clouds`, `stars`, `sea`, `front`, `lighthouse`, `sunbreak`, `ships`, `particles`, `rain`, `lightning`, and inside the lighthouse `lhbeam`, `lhlight`, `lhlamp`, `lhhalo`, `lhglass`. For finding which part causes a rendering fault on a real GPU |
| `?msaa=<samples>`, `?dpr=<ratio>` | override the quality tier's MSAA sample count and pixel ratio, for measuring what each costs |
| `?bloom=0` | no post-processing at all: the renderer tone-maps directly (as in low quality), everything else stays |
| `?sky=0` | hides the sky |
| `?cam=<az>,<el>[,<dist>]` | put the camera at an azimuth (degrees around the ships, 0 = the home side) and elevation (degrees above the sea), optionally at a distance in scene units (8 to 320), and keep it there until the first drag. For screenshots and for checking the sky from every side |

Scripts: `npm run dev`, `npm run typecheck` (`tsc --noEmit`), `npm run build`.

Only `public/bundles/mock_storm.json` (copied from `contracts/`) is committed. Real bundles and `index.json` written by the backend into `public/bundles/` are gitignored.

## Visuals and the fields that drive them

Interpolation: the scene samples every series at a fractional playhead and interpolates between frames, so motion stays smooth at 60 fps. Short exponential smoothing removes pops; it never changes where a value ends up.

| Visual | Bundle field(s) | Rule (code) |
|---|---|---|
| Wave height | `series.vol_ratio` | amplitude = 0.32 × vol_ratio^0.78, capped at 2.8 (`scene/vis.ts`). Eight layered Gerstner waves (`scene/waves.ts`); ships, containers, foam and spray ride the same model in JS. The sea's grid is 0.7 units fine for 105 units around the ships, then coarsens toward the horizon; each wave fades out with distance before the grid gets too coarse for it (a wave of length L between about 10 L and 26 L) |
| Wave steepness (sharp crests, flat troughs) | `series.vol_ratio` | Gerstner steepness = 0.35 + 0.09 × vol_ratio, capped at 1; each wave's sharpness Q·k·A is capped so the crests can never fold over |
| Chop: short waves, ripple distortion | `series.vol_ratio` | chop = (vol_ratio − 0.4) × 0.22, clamped 0.1..1.6 |
| Whitecaps | `series.risk` | foam cover = (risk − 0.15) / 0.7, clamped 0..1, laid where the Gerstner crests squeeze together (low Jacobian), broken up by noise (`scene/Sea.tsx`) |
| Water colour | `series.risk`, the solar clock, `series.market_open` | the body of the water moves from deep blue to North Sea grey-green with risk. What it reflects is 70% the mirrored scene and 30% a designed sky colour for that risk and daylight (navy at night), so the sea keeps a sea colour whatever the sky shader does: a turbid storm sky and a warm fair-wind grade used to turn the far water tan (`scene/Sea.tsx`). The sky's turbidity is 3.5 + 4 risk for the same reason |
| Sky darkness | `series.risk` | sky radiance × (1 − 0.72 × (0.85 risk² + 0.15 risk)), plus a slate overcast dome of the same strength (`scene/Atmosphere.tsx`). The storm takes at most 72% of the daylight: at noon it is slate grey, not black, so both ships stay readable |
| Cloud cover and density | `series.risk` | sky clouds: coverage 0.18 + 0.8 risk; density 0.25 + 0.7 risk. Two lower cloud decks at different heights (parallax): cover 0.25 + 0.7 risk, density 0.35 + 0.65 risk, darker with risk (`scene/Clouds.tsx`) |
| Cloud drift | `series.state` | the decks drift with the wind (0.15 calm, 0.55 watch, 1.0 storm) |
| Stars | the solar clock, `series.market_open`, `series.risk` | opacity = (1 − daylight)² × (1 − 1.3 risk, clamped), so a storm hides them (`scene/Stars.tsx`) |
| Light on ships and lighthouse | `series.risk`, the solar clock, `series.market_open` | three lights, none decorative: the sun (2.4 × daylight × (1 − 0.62 risk)), a hemisphere fill (0.34 + 0.75 × daylight × (1 − 0.3 risk) + 0.7 × night; sky colour above, sea colour below), and the sky itself as an environment map: the sky shader is prefiltered (PMREM, 64 px faces) into `scene.environment` and re-baked when risk, sun or daylight have changed visibly, at most every 0.4 s. At night a moon (1.5 × night × (1 − 0.6 risk)) lights the ships and puts a glitter path on the sea (`scene/Atmosphere.tsx`) |
| Ship liveries | `ships.prepared`, `ships.unprepared`, Survive | green hull and funnel: followed the alarm; red: ignored it; navy with a gold funnel: the player's ship. Same colours as the labels and the manifest |
| Storm cell | `series.risk`, `events[type=alarm]` → next `all_clear`, frames 0..i only | one cumulonimbus (a dark flat base, a tower, an anvil spreading downwind, rain shafts, a few hundred lit puffs sorted back to front: `scene/StormCell.tsx`). Its track (`scene/stormTrack.ts`) is computed in one forward pass, so frame i uses only frames 0..i: risk is smoothed (EMA 0.3); a cell builds on the upwind horizon (far left, behind the ships) once smoothed risk passes 0.14 and closes in as it climbs (it would be overhead at 0.8), 0.035 of the track per frame; an alarm brings it over the ships (0.12 per frame) and holds it there, sliding on downwind as risk falls under the alarm; after the all_clear, or if risk falls once it has come half way, it drifts past at 0.016 per frame and thins out on the downwind horizon (far right). It never backs up: a false alarm reads as a storm that passed by. Height and anvil grow with how built it is; base darkness and rain shafts follow the smoothed risk |
| Lightning inside the cell | `series.jump`, the cell's position | while a cell stands, each strike falls under its base, wherever it is (far-off flashes on the horizon while it approaches), and lights the cloud from within. Six bolts are built once and reused (`scene/Lightning.tsx`) |
| Fair-weather clouds | `series.risk`, the solar clock | small cumulus all round the horizon; opacity 1 − (risk − 0.12) / 0.4, so they stand on a calm day and are gone by risk 0.52 |
| Fog and horizon | `series.risk` | exp² fog, density 0.00055 + 0.0026 risk² + 0.0006 risk; colour moves from haze blue to storm grey (navy at night). A haze band of the fog colour rides with the camera: opaque at the horizon line, thinning upward (faster in calm, slower in a storm), so the far sea runs into the sky without an edge |
| Rain | `series.risk` | no rain below risk 0.25, then streak count rises linearly to the maximum at risk 1 |
| Wind: rain slant, cloud speed, wave phase speed, sail luffing | `series.state` | wind = 0.15 calm, 0.55 watch, 1.0 storm |
| Storm front on the horizon | `events[type=watch]`: `i`, `at_i` | appears at `i` 1500 units out and closes to overhead by `at_i`, then fades over 40 frames (`scene/StormFront.tsx`). A watch without `at_i` has a toast but no front |
| Storm front label, e.g. "US Employment Situation in 12 min" | `events[type=watch]`: `event` (else parsed from `text`), `at_i`, `step_s` | name + minutes to `at_i` at the playhead; after `at_i` "released N min ago"; pinned to the cloud wall (`ui/FrontLabels.tsx`) |
| Lightning bolt and flash | `series.jump` | a strike on every frame with jump = 1, strength from vol_ratio / 10 (`scene/Lightning.tsx`); the flash lights the cloud base around the bolt and the sea for its few frames |
| Lighthouse lamp lit, beam sweeping | `events[type=alarm]` → next `all_clear` | lamp and beam on between an alarm and the following all_clear (`derive.ts: alarmActive`) |
| Lighthouse amber flash (no cut) | `events[type=squall]` | strobing amber lamp, halo and beam for 6 market minutes after `i` (`vis.ts: squallEnvelope`, `Lighthouse.tsx`). Nothing else changes: no cut |
| Sun breaks through, sails fill | `events[type=fair_wind]` | for 34 frames after `i` (4 rising, 10 full): effective risk of the sky falls by 55% (cloud, darkness, fog), sun brighter, a shaft of light on the ships (`SunBreak.tsx`), both ships' sails fill and wakes show (`Ship.tsx`) |
| Ship names (labels) | `ships.prepared.label`, `ships.unprepared.label` | DOM labels pinned above each ship, with equity and change |
| Cargo containers on deck | `exposure.positions[].notional_usd` | one container per $1M of notional, up to 24; above that each grows (size ∝ cube root of notional per container; length 1.9, height 0.8, width 0.82 × size). Stowed in bays, rows and tiers on the hatch, one instanced draw per ship; livery per position, varied box by box (`scene/shipModel.ts`, `Ship.tsx: crateSlots`) |
| Waterline (how high the ship rides) | ship equity series, book notional, the cut / restore schedule, `margin_call_i`, `asset_class` | margin buffer = (equity − maintenance × current notional) / equity, maintenance 2.5% for `fx` and 15% for every other asset class (equity); freeboard = 0.2 + 1.75 × buffer (`Ship.tsx`, `derive.ts: maintenanceFor`) |
| Heel (list) | `series.*_equity`, `ships.*.start_equity_usd` | heel = (1 − equity / start_equity) × 60°, clamped 0..30° |
| Crates thrown overboard, floating away | `events[type=cut]`, `ships.*.cut_fraction` (fallback `ships.*.cut_i`, the fill frame one bar after the alarm) | at each cut the ship throws round(cut_fraction × crates) over the side, top crate first, one every 0.4 frames, each on a tumbling arc, landing with a splash and a ring of foam that tears and fades over 9 frames. It plunges, bobs up and floats for 24 frames, then settles over 44: a container that a later restore brings back rides awash until then; one with no restore ahead goes down by one end and is gone (`Jettison.tsx`) |
| Crates hoisted back aboard | `events[type=restore]` (fallback `ships.*.restore_i`) | at each restore the thrown crates rise from the water on a line from the mast head, swing over the rail and land in their places, lowest first, one every 0.4 frames, 3 frames each |
| Ship sinks | `ships.*.margin_call_i` | goes down by the stern over 30 frames from `margin_call_i`, with a burst of spray at `margin_call_i`. Where she went down the water boils, then a ragged patch of foam spreads, tears into lace and scraps and is gone 110 frames after the margin call; nine planks surface from frame 13 and drift apart. All of it is a function of the playhead, so it is the same paused, scrubbed or played (`scene/Wreck.tsx`) |
| Spray at the bows | `series.vol_ratio` (through chop) | spray rate = max(0, chop − 0.45) × 55 droplets per second per ship; none in a calm sea |
| Sails fill, wake appears | `series.*_equity` | while equity has risen over the last 3 frames (+0.25% of start equity in 3 min = full sail). The sail is furled on its yard when slack, unrolls and bellies forward as it fills, and shivers with the wind (`series.state`) (`shipModel.ts: shapeSail`) |
| Sun position and daylight | `t0 + i × step_s`, `asset_class`, `series.market_open` | the sun follows a solar clock: UTC for FX; exchange-local time (`America/New_York`, daylight saving included) for equity bundles (`asset_class` equity or source `yahoo`). It rises in the east at 06:00 on that clock, is highest at 12:00 and sets at 18:00. NVDA at 17:58 UTC is 12:58 in New York: noon, not dusk. While `market_open` is 0 it is night whatever the clock says: the sun sinks below the horizon (`vis.ts`) |
| Night: lanterns, "market closed" | `series.market_open`, the solar clock | the ships' masthead, port (red) and starboard (green) lanterns and a point light come on, and the cabin windows light up, as daylight fails (dusk, night, and every closed stretch). A "Market closed" badge in the HUD and a banner "trading resumes 09:00 UTC · 04:00 New York" show while `market_open` is 0. The closed stretch is fast-forwarded 8× so the replay does not sit through a flat night; the toasts "Market closed" and "Market open" (with the gap from the last price before the close) mark the edges. The first candle after reopening shows the gap |
| HUD price, UTC time, state badge, risk gauge | `series.mid`, frame time, `series.state`, `series.risk` | values at the current frame. Prices everywhere (HUD, chart axis, tooltips, toasts, Survive) use 2 decimals for equities (`asset_class` not `fx`, or source `yahoo`), 3 for yen pairs (USDJPY), 5 for other FX (EURUSD, USDSGD) (`derive.ts: priceDecimalsFor`) |
| HUD storm label | `storm.kind`, `storm.event`, `storm.label` | "Scheduled event · <event>" or "Unscheduled storm"; the move label is shown from `storm.onset_i` |
| "synthetic data" badge, "What if" chip | `source`, `title` | `synthetic` shows the badge. `scenario` (a navigator scenario) shows a **What if** chip carrying the bundle's title, a what-if clock instead of a calendar date, and is never presented as real history (the picker marks it too; Survive does not save its scores) |
| Cargo manifest | `exposure.positions`, `exposure.leverage`, `exposure.net_usd_by_ccy`, `book_is_synthetic` | labelled "synthetic book" |
| Stress tests (in the manifest) | `stress[]`: `scenario`, `pnl_usd`, `margin_call` | one row per earlier storm: P&L and "margin call" or "afloat". An empty array says "No earlier storms to test against yet" |
| Manifest: equity and margin-buffer bars | ship equity series + the waterline rule above | per frame |
| Market chart candles | `series.open/high/low/mid` | aggregated to 5-minute candles and revealed up to the playhead (lightweight-charts). With a live server the candles come from `/api/candles` at whatever bar size it returns (see "Live server hooks") |
| Chart markers | `storm.onset_i`, `events[alarm / squall / fair_wind / margin_call]`, release frame (`watch.at_i`, `storm.event_i`), each ship's cuts and restores | appear when the playhead passes them. The chart draws the shapes; the words are our own labels, placed over (or under) their candle, and labels that would touch push each other apart sideways, so "Onset", "Squall" and "Alarm" in the same or neighbouring candles read side by side. Cut and Restore sit on the fill frame, the same frame as the crates' splash and the toast: the cut / restore events, else `ships.*.cut_i` (one bar after the alarm) and `restore_i` |
| Chart risk strip | `series.risk`, `series.market_open` | max risk per 5-minute bucket, coloured green → amber → red; grey while the market is closed |
| Chart tooltip | `series.spread_bp`, `series.risk` | mean spread and max risk of the hovered candle. For source `yahoo` the spread is not shown: Yahoo has trades but no quotes, so `spread_bp` is 0, not a measured spread. A candle wholly inside a closed stretch says "market closed" |
| Toasts | `events[].text`, `alarm.move_ahead_pct` | one toast per event as the playhead crosses it (a bundle with no cut events gets one toast from `cut_i`) |
| Sound (CX's engine) | `series.risk`, `vol_ratio`, `state`, `mid`, heel, frame index | `update()` every animation frame; `trigger()` on jump, watch, alarm, cut, margin_call, all_clear. Squall, fair_wind and restore are silent: the engine's interface has no cue for them |
| Storm picker | `index.json`: `storms[]` (`symbol`, `title`, `kind`, `move_bp`, `file`) | grouped scheduled vs unscheduled; choosing one loads it without a reload (`ui/StormPicker.tsx`, `lib/session.ts`). Without `index.json` it lists the synthetic example |
| Evidence card | `index.json`: `metrics` | rows: `alarmed` of `storms`; `caught` of `storms` (at least half the move still ahead); `median_minutes_to_alarm`; false alarms, labelled as metrics.json defines them: `false_alarm_episodes_per_day` as the main figure ("distinct alert episodes per observed day") with `false_alarms_per_day` beside it ("pair alarms per observed day"); either alone if only one exists. A row with no number is left out; the card is hidden when `metrics` is null. Labelled "measured on August, never seen in tuning" (the month is read from `metrics.split`) |
| Storm report panel | `report`: `text`, `verified`, `unverified_numbers`, `model`, `inspector` | "numbers checked by code" badge only when `verified` is true and nothing is unverified; the inspector's verdict and issues; hidden when `report` is null (`ui/ReportPanel.tsx`) |
| "Live · Tiger Data" chip, chart candles, `query_ms` | `GET /api/health`, `GET /api/candles` | see "Live server hooks" below |
| Navigator panel, "Sail this scenario" | `GET /api/health`, `POST /api/navigator/ask` | see "Live server hooks" below |

Heel sent to the sound engine is the "Ignored it" ship's heel while it is afloat, then the prepared ship's.

## Optional contract additions

Everything below is optional and parsed leniently (`lib/loadBundle.ts`): a missing or malformed one is dropped, never fatal. The core (series, ships, exposure) stays strict.

- `ships.<name>.restore_i`: first restore after the first cut.
- Event types `squall`, `fair_wind`, `cut`, `restore`, each `{i, type, text}`. `cut` and `restore` act on the prepared ship unless the event carries `ship`. Unknown event types are ignored with a console warning.
- Watch events may carry `event` (the release's name) and `at_i`.
- `storm.event` and `storm.event_i` for `storm.kind: "scheduled"`.
- `report.inspector` `{verdict, issues}` (the backend sends verdict `ok` or `flag`).
- `source` may be `scenario` (a what-if) or `yahoo` (one-minute trade bars from Yahoo Finance; equities).
- `series.market_open` (0 or 1 for every frame, length `n`): absent means always open. Anything that is not exactly that is dropped with a console warning, never fatal.

Several cuts and restores per bundle are driven by the events: the cargo held at each frame is 1 (whole) or 1 − `cut_fraction` between a cut and the next restore (a cut while cut, or a restore while whole, changes nothing). Notional, margin buffer, waterline and crates follow it. A bundle with no cut or restore events falls back to `ships.*.cut_i` and `restore_i` (one cut, one restore), so `mock_storm.json` plays as before.

## Live server hooks

All optional. With no server running, each call fails quietly and the app plays the bundle as it is. The dev server proxies `/api` to `http://localhost:8000` (`vite.config.ts`, also for `vite preview`). For a built app on another host set `VITE_API_BASE` (that server must then allow CORS).

| Call | What the web expects | What it does |
|---|---|---|
| `GET /api/health` (once, on load) | `{"ok": true, "tiger": bool, "navigator": bool}` | `tiger` shows the "Live · Tiger Data" chip and fetches candles; `navigator` shows the navigator panel |
| `GET /api/candles?symbol=USDJPY&from=2026-07-30T10:00:00Z&to=2026-07-30T16:00:00Z` | the bundle's window, ISO 8601 UTC, inclusive; bars of **any size**: `{"candles": [{"time": <ISO string or epoch s/ms>, "open", "high", "low", "close"}], "query_ms": 12.3}`. A top-level array, `t/o/h/l/c` keys or `[t, o, h, l, c]` rows are accepted too. The bar size is read from the response (`bucket_s`, `bucket_seconds`, `interval_s`, `step_s`, or `bucket` / `interval` / `resolution` / `timeframe` as `300`, `"5m"`, `"5 min"`, `"PT5M"`), else from the median spacing between bars | the chart draws these candles and shows `query_ms` ("Tiger Data · 12 ms"). One-minute (or finer) bars are laid onto the bundle's frames. Coarser bars (5 minutes, 15 minutes, ...) are used as they are: the chart's candle is the smallest whole number of server bars of at least 5 minutes, a bar counts only once the playhead has passed it whole (the bar in progress is drawn from the bundle's own minute bars, so the chart never shows prices from after the playhead), and frames the server did not cover keep the bundle's values. If the server covers under 80% of the window, or fails, the chart keeps the bundle's own candles and the chip turns amber. The request sends no bucket parameter: when `contracts/api.md` exists, add the parameter in `lib/api.ts: fetchCandles` |
| `POST /api/navigator/ask` `{"question", "storm_id"}` | `{"answer": str, "verified": bool, "unverified_numbers": [], "inspector": {"verdict", "issues"}, "scenario": <bundle, source "scenario">}`; errors as `{"detail": str}` | shows the answer, the "numbers checked by code" badge when `verified`, the inspector's verdict; `scenario` (validated like any bundle) adds "Sail this scenario", which loads it into the scene. `storm_id` is the last storm loaded from a file, even while a scenario sails |

Answers are shown as plain text; nothing from the server is rendered as HTML.

## Survive the storm

A playful way to learn how leverage works. Switch the HUD to **Survive**, pick a storm and a leverage from 1x to 30x, press **Sail**.

- **Setup.** The panel shows the storm (from `index.json`, or the synthetic example), a leverage slider, the crates that leverage loads (one per $1M of cargo; 30x is 30 crates, the ship draws at most 24, bigger), and **where the margin-call line sits**: the price at which the broker closes you out, as a price and as a move from the entry price. The same price is drawn on the market chart as a red dashed line, and moves as you move the slider. The line is hidden when it lies outside the storm's price range (1x puts it far below).
- **Sailing.** One ship, yours (gold funnel), replaces the two demo ships. Its equity is computed in the browser from the bundle's mid prices with the formula below. **Cut** orders 75% of the cargo overboard and **Restore** orders it back; like the backend's policy, an order pressed on the minute the HUD shows fills at the next minute's open, at the bid or the ask (one order per minute). Keys: **C** cuts, **R** restores. The scrubber is locked (no rewinding a run), pause and speed work. While the market is closed you cannot trade. The bundle's alarm still fires: it is the warning you can follow. The demo ships' own cuts and margin calls do not play.
- **Margin call.** If equity falls below maintenance the position is closed at that minute's price and the ship sinks (30 frames, slowed to 1x so it is seen, with the red vignette and the margin-call sound).
- **End.** Score = final equity (never below $0; a margin call stops the loss). A card explains in plain words what happened, e.g. "At 20x, a 1% move changes your equity by about 20%. A 4.8% move against you wipes out your whole stake, and the broker closes you out earlier, at 2.4%", plus what holding everything, and cutting at the alarm, would have done. Every number on it is computed from the bundle by `lib/survive.ts`. **Try again** returns to the setup, keeping the leverage. Survival gets a cheerful toast; the card's confetti respects `prefers-reduced-motion`.
- **Best scores.** The top 5 runs per storm are kept in `localStorage` (`stormscore.survive.best.v1`), every access wrapped in try/catch: with storage blocked the game plays on and the table lives for the page. What-if scenario runs are practice and are not saved.

### The formula (the backend's)

`lib/survive.ts` mirrors `backend/storm/exposure.py: simulate_book` (FX) and `backend/storm/equity.py: simulate_stock` (equity), minute for minute.

- **Book.** Equity E = the bundle's `ships.prepared.start_equity_usd` ($1,000,000). Position notional N = leverage × E, opened at the first mid p0. FX: long USD against the other currency (USDJPY and USDSGD: long the pair; EURUSD: short EUR), the backend's book. Equity: long the symbol, priced in USD.
- **Cash.** One balance per currency, marked at mid. If USD is the base (USDJPY): `equity = cash_base + cash_quote / p` and `gross = |qty|`. If USD is the quote (EURUSD, stocks): `equity = cash_base × p + cash_quote` and `gross = |qty| × p`. Trading q units at price p moves `cash_base += q` and `cash_quote -= q × p`, so realised P&L stays in the currency it was made in. The book is booked at frame 0's close mid (a starting position, not a trade).
- **Execution.** A press on frame t is a signal at bar t's close. It fills at the open of the next traded bar (t + 1, or the first bar after a closed stretch), side-correct: buying the base currency pays the ask, selling it gets the bid. A USDJPY or USDSGD cut sells the pair at the bid; a EURUSD cut buys EUR back at the ask.
- **Each minute, in this order** (`simulate`, as `simulate_book`): 1. mark the book at the bar's open mid and test maintenance, before any trade: a breach is a margin call at the open; 2. fill the orders due this minute; 3. mark at the close mid and test maintenance again.
- **Maintenance** m: 2.5% for `fx`, 15% for equity. A margin call at the first point where `equity < m × gross`: the position is closed side-correct at that point's bid or ask, everything is converted to USD at mid, and equity stays flat afterwards.
- **Cut** (only while the cargo is whole): sell 75% of the full position. **Restore** (only while cut): buy back the full position, refused when, spread included, equity at the open would then be below `m × gross` of the full position.
- **Quotes.** The bundle carries mid OHLC and `spread_bp` (the close spread), not bid and ask. Close bid / ask = mid ∓ half the bar's `spread_bp`; open bid / ask = the bar's open mid ∓ half the previous bar's `spread_bp` (the open of bar t + 1 is the next tick after the close of bar t). Yahoo bundles have no quotes (`spread_bp` 0) and fill at the open with no spread, as the backend does. No slippage, no fees.
- **"Cut at the alarm" on the end card** is policy v1 run the backend's way: the alarm bar is the signal, the cut fills at the next bar's open, the all-clear restores the same way. If the book is already under the line at the alarm bar's close, the margin call comes first and no cut fills (the card says so).
- **Margin-call line.** Solving `equity = m × gross` at mid gives the price `p* = cash_quote / (m × |qty| - cash_base)`, for both kinds of book. The price at which the whole stake is gone is `-cash_quote / cash_base`. The line is a mid price; a margin call at the open is tested at the open mid, so a gap through the line calls the book at the open even if the close recovers.
- **Leverage cap.** 30x for FX. At 15% maintenance an equity book is already below the margin line on the first minute above 1 / 0.15 = 6.7x, so equity bundles top out at 6x.

How it was checked (`tools/parity/`, against the current `backend/storm/exposure.py: simulate_book` and `backend/storm/equity.py: simulate_stock`): 85 cases, the backend and the browser on the same prices. USDJPY, EURUSD and USDSGD at 1, 5, 10, 20 and 30x and NVDA (Yahoo bars, a closed night, a gap at the reopen) at 1, 2, 4, 5 and 6x, each holding, with one cut, with a cut and a restore, and with two cuts (NVDA: an order pressed on the last bar before the close, filled at the reopen); opens that differ from the previous close and spreads that widen in the storm; plus an open-gap margin call (breached at the open, recovered by the close), two refused restores (USDJPY, EURUSD) and the audit's reproducer. 20 cases end in a margin call, 57 cut, 37 restore. Result: **no difference** in margin-call frame, cut fills or restore fills, largest equity difference 4e-9 USD. The reproducer (USDJPY closes 100, 97.5, 99, 99; $1m at 20x; alarm at frame 1): margin call at frame 1, equity $487,179.49, no cut, in the backend and in the end card's "Cut at the alarm" row (before this change Survive cut at frame 1 and kept $570,707; the old code differs from the backend in 72 of the 85 cases).

**Difference by design.** The backend fills at SGX's real open bid and ask; the bundle does not carry them, so the browser estimates the open spread from the previous bar's close spread (above). The parity check feeds the backend that same quote model. Where the real open spread differs, the fill differs by the traded notional × the difference in half-spreads: in `tools/parity/gap.py`, with a synthetic spread that jumps at random between 0.2 and 10 bp from one minute to the next, up to $6,250 at 30x (cuts of $22.5M); margin-call frames, cut and restore fills stayed the same in every case. Real minute-to-minute spread changes are far smaller. An exact match would need the open bid and ask (or the open spread) in the bundle: a contract addition for Kamil.

## The sky

The sky is three.js's `Sky` material drawn on a 64 × 32 sphere of radius 225,000 (`SKY_RADIUS`, `scene/Atmosphere.tsx`), not on its 12-triangle box. The sphere is re-centred on the camera every frame and is never frustum-culled; the camera's far plane is 2,000,000 (`CAMERA_FAR`, `scene/Scene.tsx`). It is drawn with normal depth: `Sky`'s own `gl_Position.z = gl_Position.w` is removed, because the box's triangles that cross the camera plane clipped degenerately on Apple GPUs and gave NaN pixels. The only depth change left: a vertex beyond the far plane with w > 0 is held just inside it, which happens only in the water's mirror camera (its oblique near plane drags the far plane in); the main camera never triggers it.

Why the 3D view could go black (Apple GPUs): a NaN or Inf pixel goes black, the bloom's mip chain spreads it into screen-sized blocks, and with MSAA a single NaN sample can ruin the resolve of the whole frame before any post-processing pass sees it. Four defences:

1. The sky above, and its shader made NaN-proof: `acos` arguments clamped to [-1, 1], `atan(0, 0)` avoided at the zenith, the cloud-plane projection no longer divides by a vanishing `direction.y` at the horizon, `pow()` bases kept positive, the final colour clamped to non-negative and finite.
2. A NaN guard is the first pass of the composer (`scene/NanGuard.ts`): any NaN or Inf channel becomes 0 (negative colour too) and radiance is capped at 48 before bloom or tone mapping see it. It tests the float's bit pattern, not `isnan()`: Metal compiles with fast math and may drop `isnan()` / `isinf()`. It runs as its own pass because bloom reads its input before the effects of its own pass.
3. Every custom shader was checked for NaN on Apple GPUs: the water's Fresnel `pow(1 - theta, 5)` had theta able to exceed 1 by rounding (clamped now); the sun-break shaft's `normalize()` of an interpolated normal and its `pow(1 - h)` are guarded; particle sizes never divide by a zero depth. **The lighthouse beam was the one that blacked out every frame while the alarm was on** (found on a real MacBook GPU with `?hide=`): its `pow(1 - along, 1.6)` took a negative base at triangle edges, where MSAA extrapolates a varying past the triangle. It now clamps and uses `t * sqrt(t)`. Rule for new shaders: never `pow()`, `sqrt()` or `log()` an interpolated value without clamping it first.
4. No glossy lit surface sits next to a strong point light. The lantern-room glass is unlit: lit and glossy, a metre from the 520 cd lamp, its highlights ran into the millions and overflowed the half-float buffer.

Debug flags for checking on a laptop: `?debug=nan` (bad pixels magenta, too-bright ones yellow), `?bloom=0` (no composer), `?sky=0` (no sky), `?hide=` (leave scene parts out), `?msaa=` and `?dpr=`. `?cam=` places the camera at any azimuth and elevation.

## Controls

- Drag to orbit 360°, look down from above, scroll to zoom. The camera never goes below the waves.
- After 5 s idle the camera drifts back into a slow cinematic orbit. Double-click resets the view.
- Bottom left: play/pause (or Space), speed (default 1 market minute per 0.25 s), scrubber.
- Click the chart to seek to that candle.
- Sound starts on the first click or key press (browsers block audio before one); the cold open is silent until then. The speaker button turns sound on and off.
- "Low quality" (HUD) turns off reflections and bloom and lowers resolution. It is remembered per browser.
- Adaptive quality (high-quality path): the scene steps a tier down when it cannot hold 60 fps: when the median frame rate of two 2-second windows in a row is under 45 fps, after a 6-second warm-up following load and each change (`Scene.tsx: AdaptiveQuality`). It only steps down; a reload starts at the top. (drei's `PerformanceMonitor` did this before; on a 120 Hz MacBook it read the top tier's steady 60 to 65 fps as too slow and each tier change's hitch as another decline, and fell to tier 0 within half a minute.) Tier 3: pixel ratio up to 1.75, MSAA, reflections, bloom; 2: pixel ratio 1.35, no MSAA; 1: pixel ratio 1, sky tint instead of the mirror reflection; 0: pixel ratio 0.85, no bloom (`scene/Scene.tsx: TIERS`). `?stats=1` shows the tier.
- If WebGL fails, the app shows the chart, HUD, panels and controls without the 3D view.
- Left column: HUD (with the Replay | Survive switch), storm picker, evidence card. Right column: cargo manifest, storm report, navigator (when available). On short screens the columns scroll. In Survive the left column keeps only the HUD, the right column is the Survive panel, **Cut** and **Restore** sit above the playback controls and the end card opens in the middle.

## Layout

```
src/
  types/bundle.ts        contract types (schema_version 1)
  lib/loadBundle.ts      fetch + runtime checks (every series has length n, frames in range, ...)
  lib/derive.ts          per-frame derived arrays: cut/restore schedule, held cargo, notional, margin buffer (per-bundle maintenance), heel, alarm window, crates and their trips, triggers (incl. market close/open), solar clock offsets, the player's ship
  lib/survive.ts         Survive: the backend's book accounting in the browser, the margin-call line, the run summary and the plain-words card text (pure)
  lib/surviveGame.ts     Survive: mode switch, Sail, Cut / Restore, the margin call, the end of a run, C / R keys
  lib/session.ts         load a storm into the running app (picker, URL, navigator scenario)
  lib/api.ts             live server hooks: health, candles, navigator (all optional)
  lib/useReplayDriver.ts one rAF loop: advances the playhead, fires triggers, feeds audio
  state/timeline.ts      zustand: playhead, playing, speed, seek, per-frame selectors
  state/app.ts           zustand: mode, bundle, quality, sound, toasts
  state/survive.ts       zustand: phase, leverage, the player's actions, simulation, result, best scores (localStorage, guarded)
  scene/                 three.js / react-three-fiber scene (sea, sky, rain, lightning, front, lighthouse, sun break, ships, containers in the water, wreckage); shipModel.ts builds the hull, rigging, sail, containers and their textures in code
  ui/                    HUD, toasts, market banner, manifest, chart, controls, ship and front labels, storm picker, evidence card, report panel, navigator panel, Survive panel / actions / card
  audio/                 owned by CX (lane/cx-audio); not edited here
```

No external assets or CDNs: everything is generated in code. The hull is lofted from section curves (transom stern, flared bow, bulwark), the rock is displaced noise, the textures (windows, container ribs, sail cloth, the lighthouse's bands) are drawn on canvases (`scene/shipModel.ts`, `scene/Lighthouse.tsx`), and the water normal map is procedural (`scene/waterNormals.ts`).

Charts by [TradingView Lightweight Charts](https://www.tradingview.com/lightweight-charts/) (attribution logo kept on).
