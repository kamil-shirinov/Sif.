# StormScore web (lane CC-W)

A 3D storm replay. It plays one replay bundle (`contracts/replay_bundle.md`, schema_version 1) as a live sea: the sky turns, the alarm fires, and two ships show what the warning saved. Every visual is driven by a bundle field; nothing is decoration.

```bash
cd web && npm install && npm run dev
```

Open `http://localhost:5173/`. It opens on calm water and auto-plays after 2 seconds. There is no title screen.

| URL parameter | Effect |
|---|---|
| `?storm=<storm_id>` | load `public/bundles/<storm_id>.json` (default `mock_storm`) |
| `?at=<frame>` | start at a frame (handy for demos and screenshots) |
| `?autoplay=0` | do not auto-play |
| `?quality=low` | start in low quality (no reflections, no bloom) |

Scripts: `npm run dev`, `npm run typecheck` (`tsc --noEmit`), `npm run build`.

Only `public/bundles/mock_storm.json` (copied from `contracts/`) is committed. Real bundles written by the backend into `public/bundles/` are gitignored.

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
| Storm front on the horizon | `events[type=watch]`: `i`, `at_i` | appears at `i` 1500 units out and closes to overhead by `at_i`, then fades over 40 frames (`scene/StormFront.tsx`) |
| Lightning bolt and flash | `series.jump` | a strike on every frame with jump = 1, strength from vol_ratio / 10 (`scene/Lightning.tsx`) |
| Lighthouse lamp lit, beam sweeping | `events[type=alarm]` → next `all_clear` | lamp and beam on between an alarm and the following all_clear (`derive.ts: alarmActive`) |
| Ship names (labels) | `ships.prepared.label`, `ships.unprepared.label` | DOM labels pinned above each ship, with equity and change |
| Cargo crates on deck | `exposure.positions[].notional_usd` | one crate per $1M of notional, up to 24; above that each crate grows (edge ∝ cube root of notional per crate); colour per position |
| Waterline (how high the ship rides) | ship equity series, book notional, `cut_i`, `cut_fraction`, `margin_call_i` | margin buffer = (equity − 2.5% × current notional) / equity; freeboard = 0.2 + 1.75 × buffer (`Ship.tsx`) |
| Heel (list) | `series.*_equity`, `ships.*.start_equity_usd` | heel = (1 − equity / start_equity) × 60°, clamped 0..30° |
| Crates thrown overboard, floating away | `ships.*.cut_i`, `ships.*.cut_fraction` | at `cut_i` the ship throws round(cut_fraction × crates) over the side, one every 0.4 frames (`Jettison.tsx`) |
| Ship sinks | `ships.*.margin_call_i` | sinks over 30 frames from `margin_call_i` |
| Sails fill, wake appears | `series.*_equity` | while equity has risen over the last 3 frames (+0.25% of start equity in 3 min = full sail) |
| Sun position and daylight | `t0 + i × step_s` (UTC time of day) | sun rises in the east at 06:00 UTC, highest at 12:00, sets at 18:00 |
| HUD price, UTC time, state badge, risk gauge | `series.mid`, frame time, `series.state`, `series.risk` | values at the current frame |
| HUD storm label | `storm.kind`, `storm.label` | label shown from `storm.onset_i` |
| "synthetic data" badge | `source` | shown when `source` is `synthetic` |
| Cargo manifest | `exposure.positions`, `exposure.leverage`, `exposure.net_usd_by_ccy`, `book_is_synthetic` | labelled "synthetic book" |
| Manifest: equity and margin-buffer bars | ship equity series + the waterline rule above | per frame |
| Market chart candles | `series.open/high/low/mid` | aggregated to 5-minute candles and revealed up to the playhead (lightweight-charts) |
| Chart markers | `storm.onset_i`, `events[alarm]`, `events[margin_call]` | appear when the playhead passes them |
| Chart risk strip | `series.risk` | max risk per 5-minute bucket, coloured green → amber → red |
| Chart tooltip | `series.spread_bp`, `series.risk` | mean spread and max risk of the hovered candle |
| Toasts | `events[].text`, `alarm.move_ahead_pct`, `cut_i` | one toast per event as the playhead crosses it |
| Sound (CX's engine) | `series.risk`, `vol_ratio`, `state`, `mid`, heel, frame index | `update()` every animation frame; `trigger()` on jump, watch, alarm, cut, margin_call, all_clear |

Heel sent to the sound engine is the "Ignored it" ship's heel while it is afloat, then the prepared ship's.

## Controls

- Drag to orbit 360°, look down from above, scroll to zoom. The camera never goes below the waves.
- After 5 s idle the camera drifts back into a slow cinematic orbit. Double-click resets the view.
- Bottom left: play/pause (or Space), speed (default 1 market minute per 0.25 s), scrubber.
- Click the chart to seek to that candle.
- Sound starts on the first click or key press (browsers block audio before one); the cold open is silent until then. The speaker button turns sound on and off.
- "Low quality" (HUD) turns off reflections and bloom and lowers resolution. It is remembered per browser.
- If WebGL fails, the app shows the chart, HUD, manifest and controls without the 3D view.

## Layout

```
src/
  types/bundle.ts        contract types (schema_version 1)
  lib/loadBundle.ts      fetch + runtime checks (every series has length n, frames in range, ...)
  lib/derive.ts          per-frame derived arrays: notional, margin buffer, heel, alarm window, crates, triggers
  lib/useReplayDriver.ts one rAF loop: advances the playhead, fires triggers, feeds audio
  state/timeline.ts      zustand: playhead, playing, speed, seek, per-frame selectors
  state/app.ts           zustand: bundle, quality, sound, toasts
  scene/                 three.js / react-three-fiber scene (sea, sky, rain, lightning, front, lighthouse, ships)
  ui/                    HUD, toasts, manifest, chart, controls, ship labels
  audio/                 owned by CX (lane/cx-audio); not edited here
```

No external assets or CDNs: ships, crates and the lighthouse are built from primitives, and the water normal map is generated procedurally (`scene/waterNormals.ts`).

Charts by [TradingView Lightweight Charts](https://www.tradingview.com/lightweight-charts/) (attribution logo kept on).
