// Survive's coach: one short line under the ship's books, reacting to the player's own state in plain words.
// Pure code (tested by survive.test.mjs).
//
// The coach never sees the future. `pastOf` cuts the bundle and the simulation down to frames 0..f (arrays sliced,
// events at or before f, the margin call only once it has happened) and `coachLine` reads nothing else. The
// simulation itself is causal (lib/survive.ts: each frame's equity, cargo and margin-call line depend only on the
// frames up to it), so the line at frame f is the same whatever the storm does next.

import type { Bundle, BundleEvent } from "../../types/bundle";
import { fmtClock, fmtUsd, watchName } from "../../lib/format";
import { CUT_FRACTION, type SimResult } from "../../lib/survive";

/** How many frames an event's line stays up (4 frames a second at 1x: about 4 s). */
export const COACH_HOLD = 16;
/** Below this margin buffer (share of equity above maintenance) the coach warns. */
export const LOW_BUFFER = 0.3;

/** Everything the coach may read at frame f: nothing after it. */
export interface Past {
  f: number;
  symbol: string;
  leverage: number;
  startEquity: number;
  maintenance: number;
  /** +1 when a rising price hurts the book, -1 when a falling one does. */
  adverseSign: 1 | -1;
  /** Frames 0..f. */
  mid: number[];
  equity: number[];
  notional: number[];
  held: number[];
  liq: number[];
  restorable: number[];
  /** Events with i <= f, in order. */
  events: BundleEvent[];
  /** The margin call's frame once it has happened (<= f), else null. */
  sunkAt: number | null;
  /** The market is closed at f. */
  closed: boolean;
  /** Clock time of frames 0..f, "HH:MM UTC". */
  clock: (i: number) => string;
}

const upTo = (a: ArrayLike<number>, f: number) => Array.from({ length: f + 1 }, (_, i) => a[i]);

export function pastOf(b: Bundle, sim: SimResult, frame: number): Past {
  const f = Math.max(0, Math.min(b.n - 1, Math.floor(frame)));
  const open = b.series.market_open;
  return {
    f,
    symbol: b.symbol,
    leverage: sim.leverage,
    startEquity: sim.startEquity,
    maintenance: sim.maintenance,
    adverseSign: sim.leg.adverseSign,
    mid: upTo(b.series.mid, f),
    equity: upTo(sim.equity, f),
    notional: upTo(sim.notional, f),
    held: upTo(sim.held, f),
    liq: upTo(sim.liq, f),
    restorable: upTo(sim.restorable, f),
    events: b.events.filter((e) => e.i <= f),
    sunkAt: sim.marginCallI !== null && sim.marginCallI <= f ? sim.marginCallI : null,
    closed: open ? open[f] === 0 : false,
    clock: (i: number) => `${fmtClock(b.t0 + Math.min(i, f) * b.step_s)} UTC`,
  };
}

export type CoachTone = "info" | "good" | "warn" | "danger";
export type CoachKind =
  | "sunk"
  | "closed"
  | "alarm"
  | "all_clear"
  | "squall"
  | "fair_wind"
  | "watch"
  | "low_buffer"
  | "cut"
  | "up"
  | "leverage";

export interface CoachLine {
  kind: CoachKind;
  tone: CoachTone;
  text: string;
}

const pct = (x: number) => `${Math.abs(x).toFixed(1)}%`;

/** The latest event of a type within the last COACH_HOLD frames. */
function recent<T extends BundleEvent["type"]>(p: Past, type: T): Extract<BundleEvent, { type: T }> | null {
  for (let k = p.events.length - 1; k >= 0; k--) {
    const e = p.events[k];
    if (p.f - e.i >= COACH_HOLD) break;
    if (e.type === type) return e as Extract<BundleEvent, { type: T }>;
  }
  return null;
}

/** The move, as a fall or a rise of the symbol, that would bring the margin call from here; null when nothing is open. */
function sinkMove(p: Past): string | null {
  const liq = p.liq[p.f];
  const price = p.mid[p.f];
  if (!Number.isFinite(liq) || !(price > 0)) return null;
  const move = (liq / price - 1) * 100;
  return `a ${pct(move)} ${move < 0 ? "fall" : "rise"} in ${p.symbol || "the price"}`;
}

/** The coach's line at the frame `p` was cut at. */
export function coachLine(p: Past): CoachLine {
  const f = p.f;
  const L = p.leverage;
  const equity = p.equity[f];
  const notional = p.notional[f];
  const held = p.held[f];
  const whole = held === 1;
  const buffer = notional > 0 && equity > 0 ? (equity - p.maintenance * notional) / equity : null;
  const sink = sinkMove(p);
  const changePct = (equity / p.startEquity - 1) * 100;
  const share = Math.round(CUT_FRACTION * 100);

  if (p.sunkAt !== null) {
    return { kind: "sunk", tone: "danger", text: `Margin call at ${p.clock(p.sunkAt)}: the broker closed your trade. You keep ${fmtUsd(Math.max(0, equity))}.` };
  }
  if (p.closed) return { kind: "closed", tone: "info", text: "The market is closed: prices hold, and nobody can trade until it opens." };

  const alarm = recent(p, "alarm");
  if (alarm) {
    return whole
      ? {
          kind: "alarm",
          tone: "warn",
          text: `The alarm just sounded: a storm has started.${sink ? ` At ${L}x, ${sink} sinks you.` : ""} Cut (C) throws ${share}% overboard.`,
        }
      : { kind: "alarm", tone: "good", text: "The alarm just sounded, and your cargo is already cut. Hold steady." };
  }
  const clear = recent(p, "all_clear");
  if (clear) {
    return !whole && p.restorable[f] === 1
      ? { kind: "all_clear", tone: "good", text: "All clear: the storm has passed. Restore (R) brings your cargo back aboard." }
      : { kind: "all_clear", tone: "good", text: "All clear: the storm has passed." };
  }
  const squall = recent(p, "squall");
  if (squall) {
    return {
      kind: "squall",
      tone: "warn",
      text: `A squall: a sharp move against you.${buffer !== null ? ` Your safety margin is ${Math.round(buffer * 100)}% of your money.` : ""}`,
    };
  }
  const fair = recent(p, "fair_wind");
  if (fair) {
    return {
      kind: "fair_wind",
      tone: "good",
      text: `Fair wind: the price moved your way and you are ${changePct >= 0 ? "up" : "down"} ${pct(changePct)}. At ${L}x a move the other way counts just as much.`,
    };
  }
  // A scheduled release still ahead: its watch event has passed, its own minute has not.
  const watch = [...p.events].reverse().find((e) => e.type === "watch" && e.at_i !== undefined && e.at_i > f);
  if (watch && watch.type === "watch" && watch.at_i !== undefined) {
    const mins = watch.at_i - f;
    return {
      kind: "watch",
      tone: "info",
      text: `Storm watch: ${watchName(watch)} is due in ${mins} minute${mins === 1 ? "" : "s"}. Scheduled news can move prices fast.`,
    };
  }
  if (buffer !== null && buffer < LOW_BUFFER) {
    return {
      kind: "low_buffer",
      tone: "danger",
      text: `Your safety margin is down to ${Math.round(buffer * 100)}% of your money.${sink ? ` ${cap(sink)} sinks you.` : ""}${whole ? ` Cut (C) to lighten the ship.` : ""}`,
    };
  }
  if (!whole && held > 0) {
    return {
      kind: "cut",
      tone: "info",
      text: `Cargo cut to ${Math.round(held * 100)}%.${sink ? ` Now it takes ${sink} to sink you.` : ""}${p.restorable[f] === 1 ? " Restore (R) when you want it back." : ""}`,
    };
  }
  if (changePct >= 5) {
    return { kind: "up", tone: "good", text: `You're up ${pct(changePct)}. At ${L}x, the same move the other way would cost you as much.` };
  }
  return { kind: "leverage", tone: "info", text: sink ? `You're at ${L}x: ${sink} sinks you.` : `You're at ${L}x.` };
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
