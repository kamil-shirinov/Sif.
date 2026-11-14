// Survive mode: the player's ship. Pure code, no stores.
//
// The player's equity is computed here, in the browser, from the bundle's mid prices with the same book
// accounting as the backend (backend/storm/exposure.py `simulate_book` for FX, backend/storm/equity.py
// `simulate_stock` for equities). Written out in web/README.md.
//
//   book         $1,000,000 equity (the bundle's start_equity_usd) and a position of `leverage` x equity, opened at the
//                first mid. FX: long USD against the other currency (USDJPY, USDSGD: long the pair; EURUSD: short EUR),
//                the backend's book. Equity and anything else: long the symbol, priced in USD.
//   cash         one balance per currency, marked at spot mid. A cut's realised P&L stays in the currency it was made in.
//                  USD is the base (USDJPY):   equity = cash_base + cash_quote / mid,   gross = |qty|
//                  USD is the quote (EURUSD, stocks): equity = cash_base x mid + cash_quote,   gross = |qty| x mid
//   maintenance  2.5% of the open notional for FX, 15% for equity. Equity below maintenance x gross is a margin call:
//                the position is closed at that minute's mid and equity stays flat afterwards.
//   cut          the player throws 75% of the cargo overboard (only while the cargo is whole) at that minute's mid.
//   restore      the full position again at that minute's mid, refused when equity would be below maintenance on it.
//   no spread, no slippage, no fees.
//
// A player's cut or restore fills at the mid of the frame the HUD is showing when the button is pressed.

import type { Bundle } from "../types/bundle";
import { maintenanceFor } from "./derive";
import { fmtClock, fmtUsd } from "./format";

export const MIN_LEVERAGE = 1;
export const MAX_LEVERAGE = 30;
export const CUT_FRACTION = 0.75;
/** USD one crate on the deck stands for (derive.ts USD_PER_CRATE). */
const USD_PER_CRATE = 1_000_000;

export type LegKind = "usd-base" | "usd-quote" | "asset";

/** What the player's book holds. */
export interface Leg {
  kind: LegKind;
  /** e.g. "long USD, short JPY". */
  position: string;
  /** The currency or asset the player's money sits against, e.g. "JPY" or "NVDA". */
  against: string;
  /** +1 when a rising price hurts the book (short base), -1 when a falling price hurts it. */
  adverseSign: 1 | -1;
}

export function legFor(b: Pick<Bundle, "symbol" | "asset_class">): Leg {
  const sym = b.symbol.toUpperCase();
  if (b.asset_class === "fx" && /^[A-Z]{6}$/.test(sym)) {
    const base = sym.slice(0, 3);
    const quote = sym.slice(3);
    if (base === "USD") return { kind: "usd-base", position: `long USD, short ${quote}`, against: quote, adverseSign: -1 };
    if (quote === "USD") return { kind: "usd-quote", position: `short ${base}, long USD`, against: base, adverseSign: 1 };
  }
  return { kind: "asset", position: `long ${sym}`, against: sym, adverseSign: -1 };
}

export interface PlayerAction {
  /** Frame whose mid the trade fills at. */
  i: number;
  /** The fractional playhead when the button was pressed (drives the crates' flight), else `i`. */
  at?: number;
  kind: "cut" | "restore";
}

export interface SimResult {
  leg: Leg;
  leverage: number;
  maintenance: number;
  startEquity: number;
  entryPrice: number;
  /** USD equity per frame; flat after a margin call. */
  equity: Float64Array;
  /** Open notional per frame, USD (0 after a margin call). */
  notional: Float64Array;
  /** Share of the full position held at frame i (1 whole, 0.25 after a cut, 0 once sunk). */
  held: Float64Array;
  /** Price at which the margin call would hit given the book at frame i; NaN when nothing is open. */
  liq: Float64Array;
  /** 1 where a restore pressed at frame i is accepted (cut and enough margin to take the cargo back). */
  restorable: Uint8Array;
  marginCallI: number | null;
  /** Cuts and restores that changed the book, in order. */
  applied: PlayerAction[];
}

/**
 * Highest leverage the slider offers for this bundle: 30x, or less when maintenance margin would sink the book on its
 * first minute (equity: 15% maintenance means anything above 6x starts below the line).
 */
export function maxLeverageFor(b: Pick<Bundle, "asset_class">): number {
  return Math.min(MAX_LEVERAGE, Math.max(MIN_LEVERAGE, Math.floor(1 / maintenanceFor(b) - 1e-9)));
}
export const defaultLeverageFor = (b: Pick<Bundle, "asset_class">) => Math.min(maxLeverageFor(b), b.asset_class === "fx" ? 10 : 4);
export const clampLeverage = (x: number, max = MAX_LEVERAGE) => Math.min(max, Math.max(MIN_LEVERAGE, Math.round(x)));

/** Start equity of the player's book: the bundle's own ships start with it. */
export const startEquityOf = (b: Pick<Bundle, "ships">) => b.ships.prepared.start_equity_usd;

interface Book {
  cashBase: number;
  cashQuote: number;
  qty: number;
}

const usdValue = (leg: Leg, k: Book, p: number) => (leg.kind === "usd-base" ? k.cashBase + k.cashQuote / p : k.cashBase * p + k.cashQuote);
const grossUsd = (leg: Leg, qty: number, p: number) => (leg.kind === "usd-base" ? Math.abs(qty) : Math.abs(qty) * p);

/** Position in base units for `notional` USD at price p. */
function fullQty(leg: Leg, notional: number, p: number): number {
  if (leg.kind === "usd-base") return notional;
  if (leg.kind === "usd-quote") return -notional / p;
  return notional / p;
}

function openBook(leg: Leg, equity: number, qty: number, p: number): Book {
  const k: Book = leg.kind === "usd-base" ? { cashBase: equity, cashQuote: 0, qty: 0 } : { cashBase: 0, cashQuote: equity, qty: 0 };
  trade(k, qty, p);
  return k;
}

function trade(k: Book, target: number, p: number) {
  const dq = target - k.qty;
  k.cashBase += dq;
  k.cashQuote -= dq * p;
  k.qty = target;
}

/** Price at which equity equals maintenance x gross for the book as it stands: cash_quote / (mm x |qty| - cash_base). */
function liquidationPrice(k: Book, mm: number): number {
  if (k.qty === 0) return NaN;
  const den = mm * Math.abs(k.qty) - k.cashBase;
  if (den === 0) return NaN;
  const p = k.cashQuote / den;
  return p > 0 && Number.isFinite(p) ? p : NaN;
}

/** Price at which equity reaches zero: -cash_quote / cash_base. */
function zeroEquityPrice(k: Book): number {
  const p = k.cashBase !== 0 ? -k.cashQuote / k.cashBase : NaN;
  return p > 0 && Number.isFinite(p) ? p : NaN;
}

export function simulate(b: Bundle, leverage: number, actions: readonly PlayerAction[]): SimResult {
  const leg = legFor(b);
  const mid = b.series.mid;
  const n = b.n;
  const mm = maintenanceFor(b);
  const e0 = startEquityOf(b);
  const L = clampLeverage(leverage, maxLeverageFor(b));
  const p0 = mid[0];
  const full = fullQty(leg, L * e0, p0);
  const k = openBook(leg, e0, full, p0);

  const byFrame = new Map<number, PlayerAction[]>();
  for (const a of actions) {
    const list = byFrame.get(a.i);
    if (list) list.push(a);
    else byFrame.set(a.i, [a]);
  }

  const equity = new Float64Array(n);
  const notional = new Float64Array(n);
  const held = new Float64Array(n);
  const liq = new Float64Array(n);
  const restorable = new Uint8Array(n);
  const applied: PlayerAction[] = [];
  let marginCallI: number | null = null;

  for (let i = 0; i < n; i++) {
    const p = mid[i];
    if (marginCallI === null) {
      for (const a of byFrame.get(i) ?? []) {
        if (a.kind === "cut" && k.qty === full) {
          trade(k, full * (1 - CUT_FRACTION), p);
          applied.push(a);
        } else if (a.kind === "restore" && k.qty !== full && usdValue(leg, k, p) >= mm * grossUsd(leg, full, p)) {
          trade(k, full, p);
          applied.push(a);
        }
      }
    }
    let eq = usdValue(leg, k, p);
    let g = grossUsd(leg, k.qty, p);
    if (marginCallI === null && g > 0 && eq < mm * g) {
      // Margin call: the position is closed at this minute's mid; equity stays flat afterwards.
      trade(k, 0, p);
      eq = usdValue(leg, k, p);
      if (leg.kind === "usd-base") {
        k.cashBase = eq;
        k.cashQuote = 0;
      } else {
        k.cashBase = 0;
        k.cashQuote = eq;
      }
      marginCallI = i;
      g = 0;
    }
    equity[i] = eq;
    notional[i] = g;
    held[i] = full === 0 ? 0 : k.qty / full;
    liq[i] = liquidationPrice(k, mm);
    restorable[i] = marginCallI === null && k.qty !== full && eq >= mm * grossUsd(leg, full, p) ? 1 : 0;
  }
  return { leg, leverage: L, maintenance: mm, startEquity: e0, entryPrice: p0, equity, notional, held, liq, restorable, marginCallI, applied };
}

// ---------------------------------------------------------------- the line, before sailing

/** What the leverage slider shows for a bundle: the cargo and where the margin-call line sits. */
export interface MarginLine {
  leverage: number;
  notional: number;
  crates: number;
  /** Price at which the margin call hits, with the cargo whole. */
  price: number;
  /** The same as a move from the entry price, in percent (negative = the price falls). */
  movePct: number;
  /** Price and move at which the whole stake is gone. */
  zeroPrice: number;
  zeroMovePct: number;
}

export function marginLineFor(b: Bundle, leverage: number): MarginLine {
  const leg = legFor(b);
  const mm = maintenanceFor(b);
  const e0 = startEquityOf(b);
  const L = clampLeverage(leverage, maxLeverageFor(b));
  const p0 = b.series.mid[0];
  const k = openBook(leg, e0, fullQty(leg, L * e0, p0), p0);
  const price = liquidationPrice(k, mm);
  const zero = zeroEquityPrice(k);
  return {
    leverage: L,
    notional: L * e0,
    crates: Math.max(1, Math.round((L * e0) / USD_PER_CRATE)),
    price,
    movePct: (price / p0 - 1) * 100,
    zeroPrice: zero,
    zeroMovePct: (zero / p0 - 1) * 100,
  };
}

// ---------------------------------------------------------------- the end of the run

export interface Outcome {
  equity: number;
  sunk: boolean;
  marginCallI: number | null;
}

export interface RunResult {
  leverage: number;
  startEquity: number;
  /** Final equity, never below zero (a margin call stops the losses; nobody owes more than the stake). */
  score: number;
  changePct: number;
  sunk: boolean;
  marginCallI: number | null;
  /** Price moves, in percent, as a positive number when they went against the player. */
  worstAdversePct: number;
  worstAdverseI: number;
  /** Lowest margin buffer on the way, (equity - maintenance x notional) / equity: 0 is a margin call. */
  minBuffer: number;
  cuts: number;
  restores: number;
  firstCutI: number | null;
  line: MarginLine;
  /** The same bundle with no cut at all, and with policy v1 (cut at the alarm, restore at the all-clear). */
  held: Outcome;
  followed: (Outcome & { cutI: number }) | null;
  alarmI: number | null;
  /** The player's own run is a re-run of a what-if scenario, not real history. */
  scenario: boolean;
}

const outcomeOf = (s: SimResult): Outcome => ({
  equity: s.equity[s.equity.length - 1],
  sunk: s.marginCallI !== null,
  marginCallI: s.marginCallI,
});

/** The bundle's first alarm and the all-clear after it: where policy v1 cuts and restores. */
export function alarmWindow(b: Bundle): { alarmI: number; clearI: number | null } | null {
  const alarm = b.events.find((e) => e.type === "alarm");
  if (!alarm) return null;
  const clear = b.events.find((e) => e.type === "all_clear" && e.i > alarm.i);
  return { alarmI: alarm.i, clearI: clear ? clear.i : null };
}

export function summarize(b: Bundle, sim: SimResult): RunResult {
  const leg = sim.leg;
  const n = b.n;
  const end = sim.marginCallI ?? n - 1;
  let worst = 0;
  let worstI = 0;
  let minBuffer = 1;
  for (let i = 0; i <= end; i++) {
    const adverse = leg.adverseSign * (b.series.mid[i] / sim.entryPrice - 1) * 100;
    if (adverse > worst) {
      worst = adverse;
      worstI = i;
    }
    if (sim.notional[i] > 0 && sim.equity[i] > 0) {
      minBuffer = Math.min(minBuffer, (sim.equity[i] - sim.maintenance * sim.notional[i]) / sim.equity[i]);
    }
  }
  if (sim.marginCallI !== null) minBuffer = 0;
  const finalEquity = sim.equity[n - 1];
  const win = alarmWindow(b);
  let followed: RunResult["followed"] = null;
  if (win) {
    const acts: PlayerAction[] = [{ i: win.alarmI, kind: "cut" }];
    if (win.clearI !== null) acts.push({ i: win.clearI, kind: "restore" });
    followed = { ...outcomeOf(simulate(b, sim.leverage, acts)), cutI: win.alarmI };
  }
  return {
    leverage: sim.leverage,
    startEquity: sim.startEquity,
    score: Math.max(0, finalEquity),
    changePct: (Math.max(0, finalEquity) / sim.startEquity - 1) * 100,
    sunk: sim.marginCallI !== null,
    marginCallI: sim.marginCallI,
    worstAdversePct: worst,
    worstAdverseI: worstI,
    minBuffer,
    cuts: sim.applied.filter((a) => a.kind === "cut").length,
    restores: sim.applied.filter((a) => a.kind === "restore").length,
    firstCutI: sim.applied.find((a) => a.kind === "cut")?.i ?? null,
    line: marginLineFor(b, sim.leverage),
    held: outcomeOf(simulate(b, sim.leverage, [])),
    followed,
    alarmI: win?.alarmI ?? null,
    scenario: b.source === "scenario",
  };
}

// ---------------------------------------------------------------- plain words

const fmtPctAbs = (x: number, digits = 1) => `${Math.abs(x).toFixed(digits)}%`;
const clock = (b: Bundle, i: number) => `${fmtClock(b.t0 + i * b.step_s)} UTC`;

/** Short lines for the end card. Every number is computed above from the bundle; none is typed in. */
export function explain(b: Bundle, r: RunResult): string[] {
  const out: string[] = [];
  const L = r.leverage;
  const lesson =
    L <= 1
      ? `At 1x you only trade what you own: a 1% move changes your equity by about 1%, and the broker would not close you out until the price had moved ${fmtPctAbs(r.line.movePct)} against you.`
      : `At ${L}x, a 1% move changes your equity by about ${L}%. A ${fmtPctAbs(r.line.zeroMovePct)} move against you wipes out your whole stake, and the broker closes you out earlier, at ${fmtPctAbs(r.line.movePct)}.`;
  out.push(lesson);

  if (r.sunk && r.marginCallI !== null) {
    out.push(
      `Your margin ran out at ${clock(b, r.marginCallI)}, with the price ${fmtPctAbs(r.worstAdversePct)} against you. The broker closed the position and you kept ${fmtUsd(r.score)} of your ${fmtUsd(r.startEquity, true)}.`,
    );
    if (r.cuts > 0 && r.firstCutI !== null) out.push(`You cut at ${clock(b, r.firstCutI)}, but the sea kept rising.`);
    else out.push("You never cut: the whole cargo stayed on deck.");
  } else {
    out.push(
      `You rode out the storm and finished with ${fmtUsd(r.score)}, ${r.changePct >= 0 ? "up" : "down"} ${fmtPctAbs(r.changePct)} on your ${fmtUsd(r.startEquity, true)}.`,
    );
    if (r.worstAdversePct > 0) {
      out.push(
        `The worst moment was ${clock(b, r.worstAdverseI)}, with the price ${fmtPctAbs(r.worstAdversePct)} against you. Your safety margin fell to ${(r.minBuffer * 100).toFixed(0)}% of your equity; at 0% the ship sinks.`,
      );
    } else {
      out.push("The storm blew in your favour: the price never went against you. Leverage multiplies gains as well as losses, so luck and ruin are the same coin.");
    }
    if (r.cuts > 0 && r.firstCutI !== null) out.push(`You threw ${Math.round(CUT_FRACTION * 100)}% of the cargo overboard at ${clock(b, r.firstCutI)}.`);
  }

  if (r.held.sunk && !r.sunk && r.held.marginCallI !== null) {
    out.push(`Holding everything would have sunk the ship at ${clock(b, r.held.marginCallI)}. Your cut saved ${fmtUsd(r.score - r.held.equity)}.`);
  } else if (!r.held.sunk && r.cuts > 0) {
    const diff = r.score - r.held.equity;
    out.push(`Holding everything would have ended at ${fmtUsd(r.held.equity)}, so your cut ${diff >= 0 ? `earned ${fmtUsd(diff)} more` : `gave up ${fmtUsd(-diff)}`}.`);
  } else if (r.held.sunk && r.sunk && r.cuts > 0) {
    out.push("Holding everything would have sunk you too.");
  }
  if (r.followed && r.cuts === 0 && r.alarmI !== null) {
    out.push(
      r.followed.sunk
        ? `StormScore's alarm fired at ${clock(b, r.followed.cutI)}. Even cutting then would not have saved this ship at ${L}x.`
        : `StormScore's alarm fired at ${clock(b, r.followed.cutI)}. Cutting ${Math.round(CUT_FRACTION * 100)}% then would have left you with ${fmtUsd(r.followed.equity)}.`,
    );
  }
  if (r.scenario) out.push("This was a what-if scenario, not real history.");
  return out;
}
