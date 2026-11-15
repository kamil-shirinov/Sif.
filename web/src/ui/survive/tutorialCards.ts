// Survive's first-run tutorial: three short cards, shown once. Pure code, no React, no stores (tested by
// src/ui/survive/survive.test.mjs).
//
// "Shown once" lives in localStorage under TUTORIAL_KEY. Storage can be missing, full or blocked (private windows,
// sandboxed iframes): every access is guarded, and without storage the gate still remembers for the page's lifetime,
// so a player never sees the cards twice in one visit.

import type { Bundle } from "../../types/bundle";
import { fmtUsd } from "../../lib/format";
import { CUT_FRACTION, defaultLeverageFor, marginLineFor, simulate, startEquityOf } from "../../lib/survive";

export const TUTORIAL_KEY = "stormscore.survive.tutorial.v1";

/** The part of Storage the gate uses. */
export interface KeyValue {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

/** window.localStorage, or null where reading it throws (blocked storage) or there is no window (tests). */
export function browserStorage(): KeyValue | null {
  try {
    return typeof window !== "undefined" && window.localStorage ? window.localStorage : null;
  } catch {
    return null;
  }
}

export interface TutorialGate {
  /** True until the player has finished or skipped the cards once. */
  shouldShow(): boolean;
  /** Finished or skipped: never shown again (on this device when storage works, else for this page). */
  markSeen(): void;
}

export function createTutorialGate(storage: KeyValue | null): TutorialGate {
  let seenThisPage = false;
  return {
    shouldShow() {
      if (seenThisPage) return false;
      try {
        return storage?.getItem(TUTORIAL_KEY) !== "seen";
      } catch {
        return true;
      }
    },
    markSeen() {
      seenThisPage = true;
      try {
        storage?.setItem(TUTORIAL_KEY, "seen");
      } catch {
        /* storage unavailable: remembered for this page only */
      }
    },
  };
}

let pageGate: TutorialGate | null = null;
/** The page's one gate, over localStorage. */
export function tutorialGate(): TutorialGate {
  if (!pageGate) pageGate = createTutorialGate(browserStorage());
  return pageGate;
}

export interface TutorialCard {
  key: "leverage" | "line" | "cut";
  title: string;
  text: string;
}

const pct = (x: number) => `${Math.abs(x).toFixed(1)}%`;

/**
 * The three cards for a bundle. Every number comes from the game's own maths (lib/survive.ts) on this storm's first
 * minutes, at the leverage the slider starts on: nothing is typed in.
 */
export function tutorialCards(b: Bundle): TutorialCard[] {
  const L = defaultLeverageFor(b);
  const e0 = startEquityOf(b);
  const line = marginLineFor(b, L);
  const cards: TutorialCard[] = [
    {
      key: "leverage",
      title: "Leverage loads your ship",
      text:
        `You start with ${fmtUsd(e0, true)}. At ${L}x the broker lends you the rest, so you carry ${fmtUsd(line.notional, true)} of cargo. ` +
        `Every 1% the price moves then changes your money by about ${L}%, for you or against you.`,
    },
    {
      key: "line",
      title: "The red line is the margin call",
      text: Number.isFinite(line.movePct)
        ? `The red dashed line on the chart is where the broker closes your trade. At ${L}x it sits ${pct(line.movePct)} from your starting price. ` +
          "If the price reaches it, the ship sinks and the run is over. More leverage pulls the line closer."
        : "The red dashed line on the chart is where the broker closes your trade. If the price reaches it, the ship sinks and the run is over. More leverage pulls the line closer.",
    },
  ];
  // How far a cut pushes the line, from the simulation itself: a cut pressed on the first minute fills at the next open.
  const cutMove = cutLineMovePct(b, L);
  const share = Math.round(CUT_FRACTION * 100);
  cards.push({
    key: "cut",
    title: "Cut when the sea turns, restore when it calms",
    text:
      (cutMove !== null && Number.isFinite(line.movePct)
        ? `Cut (key C) throws ${share}% of the cargo overboard: at ${L}x that moves the red line from ${pct(line.movePct)} to ${pct(cutMove)} away. `
        : `Cut (key C) throws ${share}% of the cargo overboard and moves the red line much further away. `) +
      "Restore (key R) brings it back aboard once your margin allows. When the alarm sounds, the storm has started: that is the moment to decide.",
  });
  return cards;
}

/** Distance, in percent of the price, from the fill minute's close to the margin-call line after a cut on the first minute; null if it cannot be computed. */
export function cutLineMovePct(b: Bundle, leverage: number): number | null {
  if (b.n < 2) return null;
  const sim = simulate(b, leverage, [{ i: 0, kind: "cut" }]);
  const cut = sim.applied.find((a) => a.kind === "cut");
  if (!cut) return null;
  const liq = sim.liq[cut.i];
  const price = b.series.mid[cut.i];
  if (!Number.isFinite(liq) || !(price > 0)) return null;
  return (liq / price - 1) * 100;
}
