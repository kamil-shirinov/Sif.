# Landing page (lane CC-W)

The app's opening screen, for presenting StormScore to judges live. It opens when the URL has neither `?storm=` nor `?mode=`. It sits over the live 3D sea with the HUD hidden. The replay behind it is loaded (the headline storm by default) and paused at its calm first frame, and the camera's idle orbit gives the slow drift. A soft scrim keeps the text readable: it is dark on the left and at the foot, and open on the right where the ships are.

## What it shows, and where every number comes from

| Section | Content | Source |
|---|---|---|
| Hero | Name, one line, **Watch 30 July** (`?storm=usdjpy-2026-07-30`) and **Survive a storm** (`?mode=survive`) | — |
| Three figures | storms alarmed in the test month, caught with at least half the move ahead (plus `caught_first_onset`), false alert episodes per day (plus the per-pair rate). Each has a one-line plain meaning and links to its section of `docs/metrics.md` on GitHub | `index.json` → `metrics`: `split`, `storms`, `alarmed`, `caught`, `caught_first_onset`, `false_alarm_episodes_per_day`, `false_alarms_per_day` |
| 01 The 30 July storm | Three sentences and a two-ship ledger, then a plain note that July was the tuning month | the headline bundle: `storm` (`onset_i`, `trough_i`, `move_bp`, `kind`, `event`, `alarm_i`, `move_ahead_pct`), `alarm` events (any before the credited alarm is the false one), `ships` (`cut_fraction`, `start_equity_usd`, `margin_call_i`), the last frame of `prepared_equity` / `unprepared_equity` |
| 02 How it works | The three defences, "models read, code judges", the data stack (SGX, Tiger Data, ElevenLabs, Meta, Fireworks, Modal) | text, no numbers |
| 03 What we do not claim | synthetic book, July in-sample, onset in hindsight so `first_onset` is reported too, no price predictions; links to the README's honesty notes | text, no numbers |
| 04 Other storms | Every storm in the index except the headline one, with its move and kind | `index.json` → `storms` |
| Footer | GitHub link, presenter keys, "Open the replay" | — |

**No figure is typed into the page.** `facts.ts` builds every string that has a number in it, from the JSON as fetched. A test also checks that `Landing.tsx` contains none of the real backtest's figures. The landing fetches `index.json` and the headline bundle itself and reads them leniently. A missing `metrics` hides the figures, and a missing bundle hides the story, with a short note in each case. So the story still reads even from a bundle the replay's strict validator would refuse.

## Presenter keys

| Key | Does |
|---|---|
| L | Back to the landing page from anywhere: replay mode, the loaded storm rewound to calm and paused, `?storm`/`?mode` dropped from the URL |
| 1 | Opens 30 July (`usdjpy-2026-07-30`), auto-playing |
| 2 | Opens Survive on 30 July (or on the loaded storm when the index does not list 30 July) |
| 3 | Opens NVDA (`nvda-2026-11-12`) |
| Esc | Closes the landing overlay over the loaded storm, paused (only while the landing is open: the storm picker keeps its own Esc) |

Space (play/pause), C and R (Survive's cut and restore) are left alone. The keys are ignored with Ctrl, Cmd or Alt held, on auto-repeat, and while typing in a field (the navigator's question, the leverage slider). The buttons are real links (`?storm=…`, `?mode=survive`): a plain click switches in place, so the canvas and sound stay warm, and a modified click opens a new tab.

## Files

```
landing/
  Landing.tsx          the page
  facts.ts             readMetrics, headlineFigures, readStory, storySentences, pickerEntries (pure, no imports)
  keys.ts              presenterAction, bindPresenterKeys (pure, no imports)
  usePresenterKeys.ts  binds the keys to actions.ts on window (mounted once in App)
  actions.ts           showLanding, closeLanding, openFromLanding, openSurvive, openHeadline, openNvda
  useLandingData.ts    fetches index.json and the headline bundle
  route.ts             landingFromUrl, setLandingUrl
  landing.test.mjs     tests (fixtures/ holds a synthetic index.json and bundle)
../landing.css         styles: the HUD's fonts and colour tokens, sized from the viewport
```

There are two hooks outside this folder. `state/app.ts` has `landing` and `setLanding`, initialised from the URL. `App.tsx` renders `<Landing />` instead of the HUD overlay while `landing` is true, skips the cold-open autoplay, and calls `usePresenterKeys()`.

## Design

Type sizes come from one viewport-relative base, `clamp(15px, min(1.14vw, 2.02vh), 30px)`: about 16 px at 1280x720, 22 px at 1920x1080 and 29 px at 2560x1440. That keeps the layout the same across the projector range and readable from 3 m. The first screen holds the hero and the three figures. The rest scrolls up as a blurred dark sheet over the sea. The colours are the HUD's state colours: amber for watch and the calendar, red for storm and the margin call, green for calm and the prepared book, blue for the accent. Each count's gauge has one segment per storm. No external assets or fonts are used. Motion is a short staggered rise on load, and it is off under `prefers-reduced-motion`.

## Tests

```bash
cd web && node --test src/landing/landing.test.mjs
```

They use the synthetic fixtures, whose numbers differ on purpose from the real backtest's (5 of 7 alarmed, 0.25 episodes a day, a $812,345 prepared ship), so a typed-in figure cannot pass. They cover the figures, the story sentences (including the false alarm and the no-margin-call case), the picker, and the keys: the mapping, what is ignored, and binding to an `EventTarget`. `package.json` is outside this lane's files, so there is no `npm test` script. Adding `"test": "node --test src/landing/landing.test.mjs"` would give one.
