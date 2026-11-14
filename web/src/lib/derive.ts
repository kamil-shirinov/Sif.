// Per-frame quantities the scene and UI need, computed once from bundle fields.
// Nothing here is invented: every array is a function of the bundle (see web/README.md).

import type { AlarmEvent, Bundle, BundleEvent, ShipKey, WatchEvent } from "../types/bundle";

/** Maintenance margin rate on current notional (contract: 2.5%). */
export const MAINTENANCE_RATE = 0.025;
/** One crate on deck per this much notional, until MAX_CRATES is reached; then crates grow. */
export const USD_PER_CRATE = 1_000_000;
export const MAX_CRATES = 24;
/** Frames between one crate and the next going over the side (or being hoisted back). */
export const CRATE_STAGGER = 0.4;
/** Frames a thrown crate spends in the air. */
export const THROW_FRAMES = 2.2;
/** Frames a hoisted crate spends rising from the water to its place on deck. */
export const HOIST_FRAMES = 3;

/** One change of cargo: the ship throws cargo overboard (cut) or hoists it back (restore). */
export interface BookAction {
  i: number;
  kind: "cut" | "restore";
}

/** One crate's trip: over the side at `out`, back aboard from `back` (null: it never comes back). */
export interface CrateTrip {
  crate: number; // index into Derived.crates (stow order)
  out: number;
  back: number | null;
}

/** A watch event that can draw a storm front: it names the frame of the scheduled release. */
export type FrontWatch = WatchEvent & { at_i: number };

export interface ShipDerived {
  key: ShipKey;
  label: string;
  startEquity: number;
  equity: Float64Array;
  /** Notional carried at frame i: book notional x held, zero after margin_call_i. */
  notional: Float64Array;
  /** Fraction of the full book held at frame i: 1, or 1 - cut_fraction between a cut and the next restore. */
  held: Float64Array;
  /** (equity - maintenance) / equity, clamped 0..1. 1 when flat (no margin needed). */
  buffer: Float64Array;
  /** Heel in degrees from equity / start_equity (losing ship lists). */
  heelDeg: Float64Array;
  /** 0..1 how fast equity is rising over the last 3 frames (sails and wake). */
  rising: Float64Array;
  /** First cut / first restore (from the events, else ships.*.cut_i / restore_i). */
  cutI: number | null;
  restoreI: number | null;
  cutFraction: number;
  marginCallI: number | null;
  /** Cuts and restores in order, as they change the cargo (a cut while cut, or a restore while whole, is dropped). */
  actions: BookAction[];
  /** True when the bundle has cut or restore events for this ship (the toasts come from the events). */
  actionsFromEvents: boolean;
  /** Every crate trip over the whole replay, and the same grouped by crate. */
  trips: CrateTrip[];
  tripsByCrate: CrateTrip[][];
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
  /** Watch events with a scheduled release frame (each draws a storm front). */
  watches: FrontWatch[];
  /** Frames of squall and fair_wind events (lighthouse amber flash; sun breaking through, sails filling). */
  squalls: number[];
  fairWinds: number[];
  crates: CrateSpec[];
  priceDecimals: number;
  /** Frames where the replay fires an audio/toast trigger. */
  triggers: Map<number, TriggerSpec[]>;
}

export type TriggerSpec =
  | { kind: "event"; event: BundleEvent }
  /** Made up from ships.*.cut_i / restore_i, only for bundles that carry no cut / restore events. */
  | { kind: "cut"; ship: ShipKey; fraction: number }
  | { kind: "restore"; ship: ShipKey }
  | { kind: "jump" };

const clamp = (x: number, a: number, b: number) => Math.min(b, Math.max(a, x));

export const HEEL_DEG_PER_LOSS = 60; // 10% equity lost -> 6 degrees of heel
export const HEEL_MAX_DEG = 30;

/**
 * The cuts and restores a ship makes. The events drive it (several per bundle); a bundle without
 * cut / restore events for the ship falls back to ships.*.cut_i and restore_i (one cut, one restore).
 */
function shipActions(b: Bundle, key: ShipKey): { actions: BookAction[]; fromEvents: boolean } {
  const info = b.ships[key];
  const raw: BookAction[] = [];
  let fromEvents = false;
  for (const e of b.events) {
    if ((e.type === "cut" || e.type === "restore") && (e.ship ?? "prepared") === key) {
      raw.push({ i: e.i, kind: e.type });
      fromEvents = true;
    }
  }
  if (!fromEvents && info.cut_i !== null && info.cut_fraction > 0) {
    raw.push({ i: info.cut_i, kind: "cut" });
    const r = info.restore_i;
    if (r !== null && r !== undefined && r > info.cut_i) raw.push({ i: r, kind: "restore" });
  }
  // A cut only counts while the cargo is whole, a restore only while it is cut.
  const actions: BookAction[] = [];
  let isCut = false;
  for (const a of raw) {
    if (a.kind === "cut" && !isCut && info.cut_fraction > 0) {
      isCut = true;
      actions.push(a);
    } else if (a.kind === "restore" && isCut) {
      isCut = false;
      actions.push(a);
    }
  }
  return { actions, fromEvents };
}

/** Which crates go over the side at each cut and come back at each restore. */
function planTrips(actions: BookAction[], total: number, cutFraction: number): CrateTrip[] {
  const trips: CrateTrip[] = [];
  const open: CrateTrip[] = [];
  const k = Math.round(cutFraction * total);
  for (const a of actions) {
    if (a.kind === "cut") {
      // Top (last stowed) crate first.
      for (let j = 0; j < k; j++) {
        const trip: CrateTrip = { crate: total - 1 - j, out: a.i + j * CRATE_STAGGER, back: null };
        trips.push(trip);
        open.push(trip);
      }
    } else {
      // Lowest of the thrown crates first, so the stack is rebuilt from the bottom.
      open.sort((x, y) => x.crate - y.crate);
      open.forEach((trip, m) => (trip.back = a.i + m * CRATE_STAGGER));
      open.length = 0;
    }
  }
  return trips;
}

function deriveShip(b: Bundle, key: ShipKey, bookNotional: number, crateCount: number): ShipDerived {
  const info = b.ships[key];
  const eq = key === "prepared" ? b.series.prepared_equity : b.series.unprepared_equity;
  const n = b.n;
  const equity = Float64Array.from(eq);
  const notional = new Float64Array(n);
  const held = new Float64Array(n);
  const buffer = new Float64Array(n);
  const heelDeg = new Float64Array(n);
  const rising = new Float64Array(n);
  const { actions, fromEvents } = shipActions(b, key);

  let a = 0;
  let level = 1;
  for (let i = 0; i < n; i++) {
    while (a < actions.length && actions[a].i <= i) {
      level = actions[a].kind === "cut" ? 1 - info.cut_fraction : 1;
      a++;
    }
    held[i] = level;
    let notl = bookNotional * level;
    if (info.margin_call_i !== null && i >= info.margin_call_i) notl = 0;
    notional[i] = notl;
    const maint = MAINTENANCE_RATE * notl;
    buffer[i] = notl <= 0 ? 1 : equity[i] <= 0 ? 0 : clamp((equity[i] - maint) / equity[i], 0, 1);
    heelDeg[i] = clamp((1 - equity[i] / info.start_equity_usd) * HEEL_DEG_PER_LOSS, 0, HEEL_MAX_DEG);
    const back = Math.max(0, i - 3);
    const d = (equity[i] - equity[back]) / info.start_equity_usd;
    rising[i] = clamp(d * 400, 0, 1); // +0.25% of start equity in 3 minutes = full sail
  }
  const trips = planTrips(actions, crateCount, info.cut_fraction);
  const tripsByCrate: CrateTrip[][] = Array.from({ length: crateCount }, () => []);
  for (const t of trips) tripsByCrate[t.crate].push(t);
  return {
    key,
    label: info.label,
    startEquity: info.start_equity_usd,
    equity,
    notional,
    held,
    buffer,
    heelDeg,
    rising,
    cutI: actions.find((x) => x.kind === "cut")?.i ?? info.cut_i,
    restoreI: actions.find((x) => x.kind === "restore")?.i ?? info.restore_i ?? null,
    cutFraction: info.cut_fraction,
    marginCallI: info.margin_call_i,
    actions,
    actionsFromEvents: fromEvents,
    trips,
    tripsByCrate,
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
  const watches = b.events.filter((e): e is FrontWatch => e.type === "watch" && e.at_i !== undefined);
  const squalls = b.events.filter((e) => e.type === "squall").map((e) => e.i);
  const fairWinds = b.events.filter((e) => e.type === "fair_wind").map((e) => e.i);
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
  const prepared = deriveShip(b, "prepared", bookNotional, crates.length);
  const unprepared = deriveShip(b, "unprepared", bookNotional, crates.length);
  for (const ship of [prepared, unprepared]) {
    if (ship.actionsFromEvents) continue; // the cut / restore events already trigger toasts and sound
    for (const act of ship.actions) {
      add(act.i, act.kind === "cut" ? { kind: "cut", ship: ship.key, fraction: ship.cutFraction } : { kind: "restore", ship: ship.key });
    }
  }

  return {
    n,
    times,
    bookNotional,
    ships: { prepared, unprepared },
    alarmActive,
    alarms,
    watches,
    squalls,
    fairWinds,
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
