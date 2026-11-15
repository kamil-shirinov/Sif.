// Survive's storm list: each storm rated Easy, Medium or Hard from its own data, with one plain sentence.
// Pure code (tested by survive.test.mjs): no fetch, no stores.
//
// Two things make a storm hard for a beginner:
//   size   how much of the player's money the storm's move is worth at the leverage the slider starts on:
//          |move| x starting leverage (FX 10x, equities 4x). Under 10% Easy, under 20% Medium, else Hard.
//   speed  minutes from the storm's onset to its trough (trading minutes only, where the bundle marks a closed
//          market). A move that runs its course in FAST_MINUTES or less leaves no time to react: one level harder.
// index.json carries the move (move_bp) but not the timing: until the bundle's storm block has been read, a storm is
// rated on size alone and says so.

import type { Bundle, StormIndexEntry } from "../../types/bundle";
import { defaultLeverageFor } from "../../lib/survive";

export type Difficulty = "easy" | "medium" | "hard";
export const DIFFICULTIES: Difficulty[] = ["easy", "medium", "hard"];
export const DIFFICULTY_NAMES: Record<Difficulty, string> = { easy: "Easy", medium: "Medium", hard: "Hard" };

/** Size thresholds: share of the player's money the move is worth at the starting leverage, in percent. */
export const MEDIUM_HIT_PCT = 10;
export const HARD_HIT_PCT = 20;
/** A storm whose move runs its course in this many minutes or less is fast. */
export const FAST_MINUTES = 20;

/** What the rating reads: a storm's move, and how long it took when the bundle is known. */
export interface StormFacts {
  storm_id: string;
  symbol: string;
  asset_class: string;
  /** Signed, basis points (index.json move_bp, or the bundle's storm.move_bp). */
  moveBp: number;
  /** Minutes from onset to trough; null until the bundle has been read. */
  minutes: number | null;
}

export function factsFromEntry(e: Pick<StormIndexEntry, "storm_id" | "symbol" | "asset_class" | "move_bp">): StormFacts {
  return { storm_id: e.storm_id, symbol: e.symbol, asset_class: e.asset_class, moveBp: e.move_bp, minutes: null };
}

/** Facts from a loaded bundle: its storm's move and the trading minutes from onset to trough. */
export function factsFromBundle(b: Pick<Bundle, "storm_id" | "symbol" | "asset_class" | "storm" | "step_s" | "n" | "series">): StormFacts {
  const from = Math.max(0, Math.min(b.n - 1, b.storm.onset_i));
  const to = Math.max(from, Math.min(b.n - 1, b.storm.trough_i));
  const open = b.series.market_open;
  let frames = 0;
  for (let i = from + 1; i <= to; i++) if (!open || open[i] === 1) frames++;
  return {
    storm_id: b.storm_id,
    symbol: b.symbol,
    asset_class: b.asset_class,
    moveBp: b.storm.move_bp,
    minutes: Math.max(1, Math.round((frames * b.step_s) / 60)),
  };
}

export interface Rating {
  level: Difficulty;
  /** Starting leverage the size is measured at. */
  leverage: number;
  /** |move| in percent. */
  movePct: number;
  /** Share of the player's money the move is worth at the starting leverage, in percent. */
  hitPct: number;
  /** True when the move ran its course in FAST_MINUTES or less; null when the timing is not known yet. */
  fast: boolean | null;
  /** One plain sentence, e.g. "USDJPY fell 2.9% in 54 minutes. At 10x that move is worth 29% of your money." */
  sentence: string;
  /** For sorting inside a level: bigger is harder. */
  score: number;
}

const bump = (d: Difficulty): Difficulty => (d === "easy" ? "medium" : "hard");

export function duration(minutes: number): string {
  if (minutes < 120) return `in ${minutes} minute${minutes === 1 ? "" : "s"}`;
  const h = minutes / 60;
  return `over ${Number.isInteger(h) ? h : h.toFixed(1)} hours`;
}

export function rate(f: StormFacts): Rating {
  const leverage = defaultLeverageFor({ asset_class: f.asset_class });
  const movePct = Math.abs(f.moveBp) / 100;
  const hitPct = movePct * leverage;
  const bySize: Difficulty = hitPct >= HARD_HIT_PCT ? "hard" : hitPct >= MEDIUM_HIT_PCT ? "medium" : "easy";
  const fast = f.minutes === null ? null : f.minutes <= FAST_MINUTES;
  const level = fast ? bump(bySize) : bySize;
  const verb = f.moveBp < 0 ? "fell" : "rose";
  const name = f.symbol || "The price";
  const when = f.minutes === null ? "" : ` ${duration(f.minutes)}`;
  const tail = fast ? ", and it came too fast to think twice" : "";
  const sentence = `${name} ${verb} ${movePct.toFixed(1)}%${when}. At ${leverage}x that move is worth ${Math.round(hitPct)}% of your money${tail}.`;
  // Inside a level: the bigger hit first, a faster move breaking ties.
  const score = hitPct * (fast ? 2 : 1) + (f.minutes === null ? 0 : 1 / (1 + f.minutes));
  return { level, leverage, movePct, hitPct, fast, sentence, score };
}

/** Storms grouped Easy, Medium, Hard; inside a level the gentler ones first. Empty levels are left out. */
export function groupByDifficulty<T extends { rating: Rating }>(rows: T[]): { level: Difficulty; rows: T[] }[] {
  return DIFFICULTIES.map((level) => ({ level, rows: rows.filter((r) => r.rating.level === level).sort((a, b) => a.rating.score - b.rating.score) })).filter(
    (g) => g.rows.length > 0,
  );
}
