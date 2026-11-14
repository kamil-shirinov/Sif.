// Per-frame quantities the scene and UI need, computed once from bundle fields.
// Nothing here is invented: every array is a function of the bundle (see web/README.md).

import type { AlarmEvent, Bundle, BundleEvent, ShipKey, WatchEvent } from "../types/bundle";

/** Maintenance margin rate on current notional (contract: 2.5%). */
export const MAINTENANCE_RATE = 0.025;
/** One crate on deck per this much notional, until MAX_CRATES is reached; then crates grow. */
export const USD_PER_CRATE = 1_000_000;
export const MAX_CRATES = 24;

export interface ShipDerived {
  key: ShipKey;
  label: string;
  startEquity: number;
  equity: Float64Array;
  /** Notional carried at frame i: book notional, less cut_fraction after cut_i, zero after margin_call_i. */
  notional: Float64Array;
  /** (equity - maintenance) / equity, clamped 0..1. 1 when flat (no margin needed). */
  buffer: Float64Array;
  /** Heel in degrees from equity / start_equity (losing ship lists). */
  heelDeg: Float64Array;
  /** 0..1 how fast equity is rising over the last 3 frames (sails and wake). */
  rising: Float64Array;
  cutI: number | null;
  cutFraction: number;
  marginCallI: number | null;
}

export interface CrateSpec {
  positionIndex: number;
  instrument: string;
  /** USD notional this crate stands for. */
  notionalUsd: number;
  /** Edge length in scene units (cube root of notional per crate, clamped). */
  size: number;
}

export interface Derived {
  n: number;
  times: Float64Array; // UTC epoch seconds per frame
  bookNotional: number;
  ships: Record<ShipKey, ShipDerived>;
  /** 1 between an alarm event and the next all_clear (lamp lit, beam sweeping). */
  alarmActive: Uint8Array;
  alarms: AlarmEvent[];
  watches: WatchEvent[];
  crates: CrateSpec[];
  priceDecimals: number;
  /** Frames where the replay fires an audio/toast trigger. */
  triggers: Map<number, TriggerSpec[]>;
}

export type TriggerSpec =
  | { kind: "event"; event: BundleEvent }
  | { kind: "cut"; ship: ShipKey; fraction: number }
  | { kind: "jump" };

const clamp = (x: number, a: number, b: number) => Math.min(b, Math.max(a, x));

export const HEEL_DEG_PER_LOSS = 60; // 10% equity lost -> 6 degrees of heel
export const HEEL_MAX_DEG = 30;

function deriveShip(b: Bundle, key: ShipKey, bookNotional: number): ShipDerived {
  const info = b.ships[key];
  const eq = key === "prepared" ? b.series.prepared_equity : b.series.unprepared_equity;
  const n = b.n;
  const equity = Float64Array.from(eq);
  const notional = new Float64Array(n);
  const buffer = new Float64Array(n);
  const heelDeg = new Float64Array(n);
  const rising = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    let notl = bookNotional;
    if (info.cut_i !== null && i >= info.cut_i) notl *= 1 - info.cut_fraction;
    if (info.margin_call_i !== null && i >= info.margin_call_i) notl = 0;
    notional[i] = notl;
    const maint = MAINTENANCE_RATE * notl;
    buffer[i] = notl <= 0 ? 1 : equity[i] <= 0 ? 0 : clamp((equity[i] - maint) / equity[i], 0, 1);
    heelDeg[i] = clamp((1 - equity[i] / info.start_equity_usd) * HEEL_DEG_PER_LOSS, 0, HEEL_MAX_DEG);
    const back = Math.max(0, i - 3);
    const d = (equity[i] - equity[back]) / info.start_equity_usd;
    rising[i] = clamp(d * 400, 0, 1); // +0.25% of start equity in 3 minutes = full sail
  }
  return {
    key,
    label: info.label,
    startEquity: info.start_equity_usd,
    equity,
    notional,
    buffer,
    heelDeg,
    rising,
    cutI: info.cut_i,
    cutFraction: info.cut_fraction,
    marginCallI: info.margin_call_i,
  };
}

function decimalsOf(values: number[]): number {
  let d = 0;
  for (let i = 0; i < values.length; i += Math.max(1, Math.floor(values.length / 200))) {
    const s = String(values[i]);
    const dot = s.indexOf(".");
    if (dot >= 0) d = Math.max(d, s.length - dot - 1);
  }
  return clamp(d, 2, 5);
}

export function derive(b: Bundle): Derived {
  const n = b.n;
  const times = new Float64Array(n);
  for (let i = 0; i < n; i++) times[i] = b.t0 + i * b.step_s;
  const bookNotional = b.exposure.positions.reduce((s, p) => s + p.notional_usd, 0);

  const alarmActive = new Uint8Array(n);
  const alarms = b.events.filter((e): e is AlarmEvent => e.type === "alarm");
  const watches = b.events.filter((e): e is WatchEvent => e.type === "watch");
  for (const a of alarms) {
    const clear = b.events.find((e) => e.type === "all_clear" && e.i > a.i);
    const end = clear ? clear.i : n;
    for (let i = a.i; i < end; i++) alarmActive[i] = 1;
  }

  // Crates: one per USD_PER_CRATE of notional, capped; split across positions by notional.
  const crates: CrateSpec[] = [];
  if (bookNotional > 0) {
    const total = clamp(Math.round(bookNotional / USD_PER_CRATE), 1, MAX_CRATES);
    const perCrate = bookNotional / total;
    const size = clamp(Math.cbrt(perCrate / USD_PER_CRATE) * 1.05, 0.7, 1.7);
    b.exposure.positions.forEach((p, idx) => {
      const k = Math.max(p.notional_usd > 0 ? 1 : 0, Math.round(p.notional_usd / perCrate));
      for (let j = 0; j < k && crates.length < MAX_CRATES; j++) {
        crates.push({ positionIndex: idx, instrument: p.instrument, notionalUsd: p.notional_usd / k, size });
      }
    });
  }

  const triggers = new Map<number, TriggerSpec[]>();
  const add = (i: number, t: TriggerSpec) => {
    const arr = triggers.get(i);
    if (arr) arr.push(t);
    else triggers.set(i, [t]);
  };
  for (let i = 0; i < n; i++) if (b.series.jump[i] === 1) add(i, { kind: "jump" });
  for (const e of b.events) add(e.i, { kind: "event", event: e });
  for (const key of ["prepared", "unprepared"] as ShipKey[]) {
    const s = b.ships[key];
    if (s.cut_i !== null && s.cut_fraction > 0) add(s.cut_i, { kind: "cut", ship: key, fraction: s.cut_fraction });
  }

  return {
    n,
    times,
    bookNotional,
    ships: {
      prepared: deriveShip(b, "prepared", bookNotional),
      unprepared: deriveShip(b, "unprepared", bookNotional),
    },
    alarmActive,
    alarms,
    watches,
    crates,
    priceDecimals: decimalsOf(b.series.mid),
    triggers,
  };
}

/** Linear interpolation of a per-frame array at fractional frame t. */
export function sampleAt(arr: ArrayLike<number>, t: number): number {
  const n = arr.length;
  if (n === 0) return 0;
  if (t <= 0) return arr[0];
  if (t >= n - 1) return arr[n - 1];
  const i = Math.floor(t);
  const f = t - i;
  return arr[i] + (arr[i + 1] - arr[i]) * f;
}

/** Value at the frame the playhead is in (no interpolation), for discrete series. */
export function stepAt(arr: ArrayLike<number>, t: number): number {
  const n = arr.length;
  return arr[clamp(Math.floor(t), 0, n - 1)];
}
