import { create } from "zustand";
import type { Bundle } from "../types/bundle";
import { makeCrates, withPlayer, type CrateSpec, type Derived } from "../lib/derive";
import {
  clampLeverage,
  defaultLeverageFor,
  marginLineFor,
  maxLeverageFor,
  simulate,
  type MarginLine,
  type PlayerAction,
  type RunResult,
  type SimResult,
} from "../lib/survive";

export type Phase = "setup" | "sailing" | "over";

export interface BestScore {
  storm_id: string;
  title: string;
  leverage: number;
  score: number;
  sunk: boolean;
  /** ISO date of the run. */
  at: string;
}

const BEST_KEY = "stormscore.survive.best.v1";
const BEST_PER_STORM = 5;

/** Best scores live in localStorage. It can be missing, full or blocked: every access is guarded and the game plays on without it. */
export function loadBest(): BestScore[] {
  try {
    const raw = window.localStorage.getItem(BEST_KEY);
    if (!raw) return [];
    const j: unknown = JSON.parse(raw);
    if (!Array.isArray(j)) return [];
    return j.filter(
      (e): e is BestScore =>
        typeof e === "object" && e !== null && typeof e.storm_id === "string" && typeof e.score === "number" && Number.isFinite(e.score) && typeof e.leverage === "number",
    );
  } catch {
    return [];
  }
}

export function saveBest(all: BestScore[]) {
  try {
    window.localStorage.setItem(BEST_KEY, JSON.stringify(all));
  } catch {
    /* storage unavailable: the table lives for this page only */
  }
}

/** Add a run and keep the best few per storm. Returns the updated list and the new run's rank for its storm (1 = best), null if it did not make the table. */
export function recordScore(prev: BestScore[], entry: BestScore): { all: BestScore[]; rank: number | null } {
  const same = [...prev.filter((e) => e.storm_id === entry.storm_id), entry].sort((a, b) => b.score - a.score || (a.at < b.at ? 1 : -1));
  const kept = same.slice(0, BEST_PER_STORM);
  const rank = kept.includes(entry) ? kept.indexOf(entry) + 1 : null;
  return { all: [...prev.filter((e) => e.storm_id !== entry.storm_id), ...kept], rank };
}

export interface SurviveState {
  phase: Phase;
  leverage: number;
  /** The cut and restore presses of this run, in order. */
  actions: PlayerAction[];
  /** The base (Replay-mode) derivation of the loaded bundle; the player's derivation is built from it. */
  base: Derived | null;
  crates: CrateSpec[];
  sim: SimResult | null;
  line: MarginLine | null;
  result: RunResult | null;
  /** Rank of the finished run in the storm's best scores. */
  rank: number | null;
  best: BestScore[];
  /** Set once the margin call has been announced (toast, sound), so it happens once. */
  sunkAnnounced: boolean;
  /** Number of finished runs this page load, for the "try again" wording. */
  runs: number;
  /** (Re)start the setup for a loaded bundle; returns the Derived the app should show. */
  begin(b: Bundle, base: Derived, keepLeverage?: boolean): Derived;
  setLeverage(b: Bundle, leverage: number): Derived | null;
  addAction(b: Bundle, a: PlayerAction): Derived | null;
  sail(): void;
  finish(result: RunResult, rank: number | null, best: BestScore[]): void;
  markSunk(): void;
  reset(): void;
}

/** Simulation and the player's derivation for the current leverage and actions. */
function build(b: Bundle, base: Derived, leverage: number, actions: PlayerAction[], crates: CrateSpec[]) {
  const sim = simulate(b, leverage, actions);
  return { sim, derived: withPlayer(base, { ...sim, applied: sim.applied }, crates) };
}

export const useSurvive = create<SurviveState>((set, get) => ({
  phase: "setup",
  leverage: 10,
  actions: [],
  base: null,
  crates: [],
  sim: null,
  line: null,
  result: null,
  rank: null,
  best: loadBest(),
  sunkAnnounced: false,
  runs: 0,
  begin: (b, base, keepLeverage = true) => {
    const max = maxLeverageFor(b);
    const leverage = keepLeverage && get().base ? clampLeverage(get().leverage, max) : defaultLeverageFor(b);
    const line = marginLineFor(b, leverage);
    const crates = makeCrates([{ instrument: b.symbol, notional_usd: line.notional }]);
    const { sim, derived } = build(b, base, leverage, [], crates);
    set({ phase: "setup", leverage, actions: [], base, crates, sim, line, result: null, rank: null, sunkAnnounced: false, best: loadBest() });
    return derived;
  },
  setLeverage: (b, leverage) => {
    const { base, phase } = get();
    if (!base || phase !== "setup") return null;
    const L = clampLeverage(leverage, maxLeverageFor(b));
    const line = marginLineFor(b, L);
    const crates = makeCrates([{ instrument: b.symbol, notional_usd: line.notional }]);
    const { sim, derived } = build(b, base, L, [], crates);
    set({ leverage: L, actions: [], crates, sim, line });
    return derived;
  },
  addAction: (b, a) => {
    const { base, leverage, actions, crates, phase } = get();
    if (!base || phase !== "sailing") return null;
    const next = [...actions, a];
    const { sim, derived } = build(b, base, leverage, next, crates);
    set({ actions: next, sim });
    return derived;
  },
  sail: () => set({ phase: "sailing", actions: [], result: null, rank: null, sunkAnnounced: false }),
  finish: (result, rank, best) => set({ phase: "over", result, rank, best, runs: get().runs + 1 }),
  markSunk: () => set({ sunkAnnounced: true }),
  reset: () => set({ phase: "setup", actions: [], result: null, rank: null, sunkAnnounced: false }),
}));

