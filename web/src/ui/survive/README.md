# Survive for beginners (web/src/ui/survive)

Our entry for SGX Challenge 2, "Every trader needs to start somewhere". These files teach. They never change the
maths: the player's book, fills and margin calls stay in `web/src/lib/survive.ts`, which matches the backend.
Every number shown here is computed by that code from the bundle, and the words around the numbers are fixed
templates.

| What | Where | Pure logic (tested) |
|---|---|---|
| First-run tutorial: three cards (leverage, the margin-call line, cut and restore), Skip or Esc, shown once; **How to play** in the setup opens it again | `Tutorial.tsx` | `tutorialCards.ts` |
| Storm choice: every storm in index.json as Easy, Medium or Hard, with one plain sentence each; 30 July stays the default (tagged "headline") | `StormList.tsx`, `stormFacts.ts` | `difficulty.ts` |
| Coach line under the equity while sailing | `Coach.tsx` | `coachLine.ts` |
| End card: what happened, the ship that followed the alarm, one lesson, a share line with Copy, best scores per storm | `../SurviveCard.tsx` | `endcard.ts` |

Styles: `web/src/survive.css`, imported by `../SurvivePanel.tsx`. Tests: `survive.test.mjs` with fixtures in
`fixtures/`. `../hud.test.mjs` imports it, so `node --test src/ui/hud.test.mjs` runs both.

## Tutorial, shown once

`createTutorialGate(storage)` reads and writes `stormscore.survive.tutorial.v1` in localStorage. If storage is
blocked, missing or full, no call throws, and the gate still remembers for the page's lifetime. The cards' numbers
come from `lib/survive.ts` on the loaded storm at the slider's starting leverage: the cargo (`marginLineFor`), the
margin-call distance, and how far a cut on the first minute pushes the line (`simulate` with one cut).

## Difficulty

- **Size:** |move| × the slider's starting leverage (10x for FX, 4x for equities). That is the share of the
  player's money the storm's move is worth. Under 10% is Easy, under 20% is Medium, anything above is Hard.
- **Speed:** trading minutes from `storm.onset_i` to `storm.trough_i`. A storm whose move takes 20 minutes or less
  goes up one level.

index.json has `move_bp` but no timing, so `stormFacts.ts` reads each listed bundle once in the background, two at a
time, and keeps only its facts. Until a bundle has been read, its storm is rated on size alone and the row says
"(Timing still loading.)". A bundle that fails to load keeps its size-only rating.

Example sentence: "USDJPY fell 2.9% in 54 minutes. At 10x that move is worth 29% of your money."

## Coach

`pastOf(bundle, sim, f)` cuts the bundle and the simulation down to frames 0..f. It slices the arrays, keeps only
events at or before f, and passes on the margin call only once it has happened. `coachLine` reads nothing else. The
first matching line wins:

1. margin call
2. market closed
3. the alarm, in the last 16 frames (about 4 s at 1x)
4. the all-clear, in the same window
5. a squall
6. a fair wind
7. a scheduled release still ahead (storm watch)
8. a safety margin under 30%
9. cargo cut
10. up 5% or more
11. "You're at 25x: a 1.5% fall in USDJPY sinks you."

The tests swap in other futures after every frame (the price jumps 3% up or down, new events appear) and check that
the line at that frame does not change.

## End card

`whatHappened`, `alarmFollower`, `lessonFor` and `shareLine` read only the run's `RunResult` (`summarize` in
`lib/survive.ts`) and the bundle's clock. The lesson picks one of these cases: sunk while the alarm would have saved
the ship; sunk too fast for any alarm; sunk with no alarm; a cut that saved the ship; a cut that kept or cost money
compared with holding everything; a storm that went the player's way; a thin margin; room to spare. The share line
links to `?mode=survive&storm=<id>`. What-if runs get no link, because their storm cannot be opened from a URL.
Best scores per storm stay in `state/survive.ts`, using the same guarded localStorage as before.
