# HUD (web/src/ui)

The panels over the 3D sea. This note covers the presenter layout: the right card, the scrubber's ticks, the captions,
the end card and the clean view (H). Every number shown is read from the bundle; the words around them are fixed
templates in `story.ts`, with no number typed in.

## Layout

| Where | What | File |
|---|---|---|
| Top left | HUD, storm picker, evidence card | `Hud.tsx`, `StormPicker.tsx`, `EvidenceCard.tsx` |
| Top right | "Two ships, one book": both ships always (equity, change, notional, margin buffer bar), a one-line book summary, then tabs **Cargo**, **Stress tests**, **Report**, all collapsed at first (a second click collapses the open one) | `Manifest.tsx` |
| Bottom left | play, scrubber with event ticks, speed | `Controls.tsx` |
| Bottom centre | captions; at the last frame the end card above them | `Presenter.tsx` |
| Bottom right | market chart | `MarketChart.tsx` |

The bottom row's sizes are CSS variables on `:root` (`--controls-w`, `--chart-w`, `--chart-h`, `--left-w`), so the
captions and the end card sit in the gap between the controls and the chart at any width. The left column is 232 px at
1280 wide and 260 px from about 1450 wide, so it clears the prepared ship at the default camera. Checked at 1280x720,
1366x768, 1440x900, 1920x1080 and 2560x1440. On screens narrower than 16:9 (16:10 laptops frame the ships wider) the
evidence card starts as one summary line; a click opens it.

`ReportPanel` (still mounted by `App.tsx`) renders nothing now: the report is the right card's Report tab
(`ReportBody`). The mount in `App.tsx` can go at the next merge.

The new parts are mounted from `Controls` (always on screen with the overlay) and portalled to `<body>`, so `App.tsx`
did not change.

## Event ticks (scrubber)

One small coloured tick per event: watch, alarm, squall, fair wind, cut, restore, margin call, all-clear. Events closer
than 0.6% of the replay share a tick (stacked colours, every event in the tooltip). Hover or focus shows the tooltip,
e.g. "13:31 · The alarm fires with 90% of the move still ahead"; a click jumps there (and shows that caption). Ticks
already passed are full strength. Hidden in Survive (the alarm's place would give the game away).

Sources: the bundle's `watch`, `alarm`, `squall`, `fair_wind`, `margin_call` and `all_clear` events; a ship's
`margin_call_i` when it has no `margin_call` event; cuts and restores from the ships' derived actions (`derive.ts`),
which are the `cut` / `restore` events, else `ships.*.cut_i` / `restore_i`, as the scene and the toasts use them.

## Captions

One line at the bottom centre per event as the playhead passes it, fading after about 4 s (a queued one shows at
least 2.2 s first; at high speed older ones are dropped). Replay mode only.

| Event | Caption (numbers from) |
|---|---|
| watch | "10:03 · Storm watch: US Employment Situation due at 10:08" (`event`, else parsed from `text`; `at_i`) |
| alarm | "10:10 · The alarm fires with 82% of the move still ahead" (`move_ahead_pct`, rounded); "The alarm fires" when it is null |
| squall | "A squall: a sharp move against the book, no cut" |
| fair_wind | "Fair wind: a sharp move in the book's favour" |
| cut | "The prepared ship cuts 75% of its cargo" (`ships.<ship>.cut_fraction`) |
| restore | "The prepared ship hoists its cargo back aboard" |
| margin_call | "Margin call: the unprepared ship goes down" (`ship`) |
| all_clear | "All clear: the storm has passed" |

Times are the frame's clock, `t0 + i × step_s`, UTC (HH:MM).

## End card

At the replay's last frame (gone as soon as the playhead leaves it): each ship's label, final equity
(`series.*_equity[n − 1]`), change from `start_equity_usd`, "Afloat" or "Margin call HH:MM UTC"
(`ships.*.margin_call_i`, else that ship's `margin_call` event), and "Following the alarm kept $X more" (or "Ignoring
the alarm kept $X more" when that ship ended higher, or "Both ships ended level"). **Replay** rewinds and plays;
**Back to landing (L)** does what L does.

## Stress rows

`"USDJPY storm 02 Jul 12:20 UTC: -58 bp"` shows as `USDJPY 2 Jul 12:20 −58 bp → −$118k, afloat`. The backend's full
text (with ", applied as USD … bp" where it has one) is the row's tooltip. A scenario in any other form is shown whole.
At 290 px a "margin call" row with a long name wraps its result to a second, right-aligned line.

## Presenter clean view: H

H hides every panel (HUD, picker, evidence, right column, chart, toasts, the hint, Survive's panels and the end card);
the captions, the ship labels, the storm-front labels and the timeline stay. H again brings them back. A small note
"Clean view · H shows the panels" shows for 2.6 s. Ignored with Ctrl, Cmd or Alt, on auto-repeat and while typing in a
field; bound only while the replay's overlay is up, and leaving it (L) restores the panels. L, 1, 2, 3, Esc, Space, C
and R keep their meaning.

## Tests

```bash
cd web && node --test src/ui/hud.test.mjs
```

Two fixtures with deliberately different numbers (`fixtures/story-a.fixture.json`, `story-b.fixture.json`): captions,
ticks and the end card are checked against each, a changed number changes the caption, and the H key is checked
(both cases, modifiers, repeat, fields, bind and unbind).
