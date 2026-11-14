# StormScore web (lane CC-W)

A 3D storm replay. It plays one replay bundle (`contracts/replay_bundle.md`, schema_version 1) as a live sea: the sky turns, the alarm fires, and two ships show what the warning saved. Every visual is driven by a bundle field; nothing is decoration.

```bash
cd web && npm install && npm run dev
```

Open `http://localhost:5173/`. It opens on calm water and auto-plays after 2 seconds. There is no title screen.

Which storm opens: `?storm=<storm_id>` if given; otherwise, when `public/bundles/index.json` exists, the storm with the largest move in it; otherwise `mock_storm`. With no server and no `index.json` it plays exactly the committed `mock_storm`, plus the storm picker and report panel.

| URL parameter | Effect |
|---|---|
| `?storm=<storm_id>` | load that storm (the file named in `index.json`, else `public/bundles/<storm_id>.json`). The picker keeps this parameter up to date |
| `?at=<frame>` | start at a frame (handy for demos and screenshots) |
| `?autoplay=0` | do not auto-play |
| `?quality=low` | start in low quality (no reflections, no bloom) |

Scripts: `npm run dev`, `npm run typecheck` (`tsc --noEmit`), `npm run build`.

Only `public/bundles/mock_storm.json` (copied from `contracts/`) is committed. Real bundles and `index.json` written by the backend into `public/bundles/` are gitignored.

## Visuals and the fields that drive them

Interpolation: the scene samples every series at a fractional playhead and interpolates between frames, so motion stays smooth at 60 fps. Short exponential smoothing removes pops; it never changes where a value ends up.

| Visual | Bundle field(s) | Rule (code) |
|---|---|---|
| Wave height | `series.vol_ratio` | amplitude = 0.32 × vol_ratio^0.78, capped at 2.8 (`scene/vis.ts`) |
| Chop: short waves, crest foam, ripple distortion | `series.vol_ratio` | chop = (vol_ratio − 0.4) × 0.22, clamped 0.1..1.6 |
| Sky darkness | `series.risk` | sky radiance × (1 − (0.85 risk² + 0.15 risk)), plus a darkening dome (`scene/Atmosphere.tsx`) |
| Cloud cover and density | `series.risk` | coverage 0.18 + 0.8 risk; density 0.25 + 0.7 risk |
| Fog | `series.risk` | exp² fog, density rises with risk; colour moves from haze blue to storm grey |
| Rain | `series.risk` | no rain below risk 0.25, then streak count rises linearly to the maximum at risk 1 |
| Wind: rain slant, cloud speed, wave phase speed, sail luffing | `series.state` | wind = 0.15 calm, 0.55 watch, 1.0 storm |
| Storm front on the horizon | `events[type=watch]`: `i`, `at_i` | appears at `i` 1500 units out and closes to overhead by `at_i`, then fades over 40 frames (`scene/StormFront.tsx`). A watch without `at_i` has a toast but no front |
| Storm front label, e.g. "US Employment Situation in 12 min" | `events[type=watch]`: `event` (else parsed from `text`), `at_i`, `step_s` | name + minutes to `at_i` at the playhead; after `at_i` "released N min ago"; pinned to the cloud wall (`ui/FrontLabels.tsx`) |
| Lightning bolt and flash | `series.jump` | a strike on every frame with jump = 1, strength from vol_ratio / 10 (`scene/Lightning.tsx`) |
| Lighthouse lamp lit, beam sweeping | `events[type=alarm]` → next `all_clear` | lamp and beam on between an alarm and the following all_clear (`derive.ts: alarmActive`) |
| Lighthouse amber flash (no cut) | `events[type=squall]` | strobing amber lamp, halo and beam for 6 market minutes after `i` (`vis.ts: squallEnvelope`, `Lighthouse.tsx`). Nothing else changes: no cut |
| Sun breaks through, sails fill | `events[type=fair_wind]` | for 34 frames after `i` (4 rising, 10 full): effective risk of the sky falls by 55% (cloud, darkness, fog), sun brighter, a shaft of light on the ships (`SunBreak.tsx`), both ships' sails fill and wakes show (`Ship.tsx`) |
| Ship names (labels) | `ships.prepared.label`, `ships.unprepared.label` | DOM labels pinned above each ship, with equity and change |
| Cargo crates on deck | `exposure.positions[].notional_usd` | one crate per $1M of notional, up to 24; above that each crate grows (edge ∝ cube root of notional per crate); colour per position |
| Waterline (how high the ship rides) | ship equity series, book notional, the cut / restore schedule, `margin_call_i` | margin buffer = (equity − 2.5% × current notional) / equity; freeboard = 0.2 + 1.75 × buffer (`Ship.tsx`) |
| Heel (list) | `series.*_equity`, `ships.*.start_equity_usd` | heel = (1 − equity / start_equity) × 60°, clamped 0..30° |
| Crates thrown overboard, floating away | `events[type=cut]`, `ships.*.cut_fraction` (fallback `ships.*.cut_i`) | at each cut the ship throws round(cut_fraction × crates) over the side, top crate first, one every 0.4 frames (`Jettison.tsx`) |
| Crates hoisted back aboard | `events[type=restore]` (fallback `ships.*.restore_i`) | at each restore the thrown crates rise from the water on a line from the mast head, swing over the rail and land in their places, lowest first, one every 0.4 frames, 3 frames each |
| Ship sinks | `ships.*.margin_call_i` | sinks over 30 frames from `margin_call_i` |
| Sails fill, wake appears | `series.*_equity` | while equity has risen over the last 3 frames (+0.25% of start equity in 3 min = full sail) |
| Sun position and daylight | `t0 + i × step_s` (UTC time of day) | sun rises in the east at 06:00 UTC, highest at 12:00, sets at 18:00 |
| HUD price, UTC time, state badge, risk gauge | `series.mid`, frame time, `series.state`, `series.risk` | values at the current frame |
| HUD storm label | `storm.kind`, `storm.event`, `storm.label` | "Scheduled event · <event>" or "Unscheduled storm"; the move label is shown from `storm.onset_i` |
| "synthetic data" / "what-if scenario" badge | `source` | `synthetic`, or `scenario` (a navigator scenario) |
| Cargo manifest | `exposure.positions`, `exposure.leverage`, `exposure.net_usd_by_ccy`, `book_is_synthetic` | labelled "synthetic book" |
| Manifest: equity and margin-buffer bars | ship equity series + the waterline rule above | per frame |
| Market chart candles | `series.open/high/low/mid` | aggregated to 5-minute candles and revealed up to the playhead (lightweight-charts) |
| Chart markers | `storm.onset_i`, `events[alarm / squall / fair_wind / cut / restore / margin_call]`, release frame (`watch.at_i`, `storm.event_i`) | appear when the playhead passes them |
| Chart risk strip | `series.risk` | max risk per 5-minute bucket, coloured green → amber → red |
| Chart tooltip | `series.spread_bp`, `series.risk` | mean spread and max risk of the hovered candle |
| Toasts | `events[].text`, `alarm.move_ahead_pct` | one toast per event as the playhead crosses it (a bundle with no cut events gets one toast from `cut_i`) |
| Sound (CX's engine) | `series.risk`, `vol_ratio`, `state`, `mid`, heel, frame index | `update()` every animation frame; `trigger()` on jump, watch, alarm, cut, margin_call, all_clear. Squall, fair_wind and restore are silent: the engine's interface has no cue for them |
| Storm picker | `index.json`: `storms[]` (`symbol`, `title`, `kind`, `move_bp`, `file`) | grouped scheduled vs unscheduled; choosing one loads it without a reload (`ui/StormPicker.tsx`, `lib/session.ts`). Without `index.json` it lists the synthetic example |
| Evidence card | `index.json`: `metrics` | rows: `alarmed` of `storms`; `caught` of `storms` (at least half the move still ahead); `median_minutes_to_alarm`; `false_alarms_per_day`. A row with no number is left out; the card is hidden when `metrics` is null. Labelled "measured on August, never seen in tuning" (the month is read from `metrics.split`) |
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
- `source` may be `scenario`.

Several cuts and restores per bundle are driven by the events: the cargo held at each frame is 1 (whole) or 1 − `cut_fraction` between a cut and the next restore (a cut while cut, or a restore while whole, changes nothing). Notional, margin buffer, waterline and crates follow it. A bundle with no cut or restore events falls back to `ships.*.cut_i` and `restore_i` (one cut, one restore), so `mock_storm.json` plays as before.

## Live server hooks

All optional. With no server running, each call fails quietly and the app plays the bundle as it is. The dev server proxies `/api` to `http://localhost:8000` (`vite.config.ts`, also for `vite preview`). For a built app on another host set `VITE_API_BASE` (that server must then allow CORS).

| Call | What the web expects | What it does |
|---|---|---|
| `GET /api/health` (once, on load) | `{"ok": true, "tiger": bool, "navigator": bool}` | `tiger` shows the "Live · Tiger Data" chip and fetches candles; `navigator` shows the navigator panel |
| `GET /api/candles?symbol=USDJPY&from=2026-07-30T10:00:00Z&to=2026-07-30T16:00:00Z` | the bundle's window, ISO 8601 UTC, inclusive; one-minute bars: `{"candles": [{"time": <ISO string or epoch s/ms>, "open", "high", "low", "close"}], "query_ms": 12.3}`. A top-level array, `t/o/h/l/c` keys or `[t, o, h, l, c]` rows are accepted too | the chart draws these candles and shows `query_ms` ("Tiger Data · 12 ms"). If the server covers under 80% of the window, or fails, the chart keeps the bundle's own candles and the chip turns amber |
| `POST /api/navigator/ask` `{"question", "storm_id"}` | `{"answer": str, "verified": bool, "unverified_numbers": [], "inspector": {"verdict", "issues"}, "scenario": <bundle, source "scenario">}`; errors as `{"detail": str}` | shows the answer, the "numbers checked by code" badge when `verified`, the inspector's verdict; `scenario` (validated like any bundle) adds "Sail this scenario", which loads it into the scene. `storm_id` is the last storm loaded from a file, even while a scenario sails |

Answers are shown as plain text; nothing from the server is rendered as HTML.

## Controls

- Drag to orbit 360°, look down from above, scroll to zoom. The camera never goes below the waves.
- After 5 s idle the camera drifts back into a slow cinematic orbit. Double-click resets the view.
- Bottom left: play/pause (or Space), speed (default 1 market minute per 0.25 s), scrubber.
- Click the chart to seek to that candle.
- Sound starts on the first click or key press (browsers block audio before one); the cold open is silent until then. The speaker button turns sound on and off.
- "Low quality" (HUD) turns off reflections and bloom and lowers resolution. It is remembered per browser.
- If WebGL fails, the app shows the chart, HUD, panels and controls without the 3D view.
- Left column: HUD, storm picker, evidence card. Right column: cargo manifest, storm report, navigator (when available). On short screens the columns scroll.

## Layout

```
src/
  types/bundle.ts        contract types (schema_version 1)
  lib/loadBundle.ts      fetch + runtime checks (every series has length n, frames in range, ...)
  lib/derive.ts          per-frame derived arrays: cut/restore schedule, held cargo, notional, margin buffer, heel, alarm window, crates and their trips, triggers
  lib/session.ts         load a storm into the running app (picker, URL, navigator scenario)
  lib/api.ts             live server hooks: health, candles, navigator (all optional)
  lib/useReplayDriver.ts one rAF loop: advances the playhead, fires triggers, feeds audio
  state/timeline.ts      zustand: playhead, playing, speed, seek, per-frame selectors
  state/app.ts           zustand: bundle, quality, sound, toasts
  scene/                 three.js / react-three-fiber scene (sea, sky, rain, lightning, front, lighthouse, sun break, ships, crates in the water)
  ui/                    HUD, toasts, manifest, chart, controls, ship and front labels, storm picker, evidence card, report panel, navigator panel
  audio/                 owned by CX (lane/cx-audio); not edited here
```

No external assets or CDNs: ships, crates and the lighthouse are built from primitives, and the water normal map is generated procedurally (`scene/waterNormals.ts`).

Charts by [TradingView Lightweight Charts](https://www.tradingview.com/lightweight-charts/) (attribution logo kept on).
