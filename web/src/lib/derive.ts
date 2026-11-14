// Per-frame quantities the scene and UI need, computed once from bundle fields.
// Nothing here is invented: every array is a function of the bundle (see web/README.md).

import type { AlarmEvent, Bundle, BundleEvent, ShipKey, WatchEvent } from "../types/bundle";

/** Maintenance margin on the open notional: 2.5% for FX books, 15% for equity books (the backend's two books). */
export const MAINTENANCE_FX = 0.025;
export const MAINTENANCE_EQUITY = 0.15;
export function maintenanceFor(b: Pick<Bundle, "asset_class">): number {
  return b.asset_class === "fx" ? MAINTENANCE_FX : MAINTENANCE_EQUITY;
}

/** Equities keep their exchange's clock: the sun follows New York time, not UTC. FX and the rest follow UTC. */
export const EQUITY_TZ = "America/New_York";
export function exchangeTz(b: Pick<Bundle, "asset_class" | "source">): string | null {
  return b.asset_class === "equity" || b.source === "yahoo" ? EQUITY_TZ : null;
}

const tzFormats = new Map<string, Intl.DateTimeFormat>();
/** Seconds that local time in `tz` runs ahead of UTC at epoch second `epochS` (daylight saving included). 0 if the zone is unknown. */
export function tzOffsetSeconds(tz: string, epochS: number): number {
  try {
    let f = tzFormats.get(tz);
    if (!f) {
      f = new Intl.DateTimeFormat("en-US", {
        timeZone: tz,
        hourCycle: "h23",
        year: "numeric",
        month: "numeric",
        day: "numeric",
        hour: "numeric",
        minute: "numeric",
        second: "numeric",
      });
      tzFormats.set(tz, f);
    }
    const part: Record<string, number> = {};
    for (const p of f.formatToParts(new Date(Math.floor(epochS) * 1000))) if (p.type !== "literal") part[p.type] = Number(p.value);
    return Date.UTC(part.year, part.month - 1, part.day, part.hour, part.minute, part.second) / 1000 - Math.floor(epochS);
  } catch {
    return 0;
  }
}
/** One crate on deck per this much notional, until MAX_CRATES is reached; then crates grow. */
export const USD_PER_CRATE = 1_000_000;
export const MAX_CRATES = 24;
/** Frames between one crate and the next going over the side (or being hoisted back). */
export const CRATE_STAGGER = 0.4;
/** Frames a thrown crate spends in the air. */
export const THROW_FRAMES = 2.2;
/** Frames a hoisted crate spends rising from the water to its place on deck. */
export const HOIST_FRAMES = 3;
/** Frames a ship takes to go under after its margin call. */
export const SINK_FRAMES = 30;

/** A ship in the scene: the bundle's two demo ships, or the player's ship in Survive mode. */
export type SceneShip = ShipKey | "player";

/** One change of cargo: the ship throws cargo overboard (cut) or hoists it back (restore). */
export interface BookAction {
  i: number;
  kind: "cut" | "restore";
  /** Fractional playhead of a player's button press: the crates fly from there instead of from frame `i`. */
  at?: number;
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
  key: SceneShip;
  label: string;
  startEquity: number;
  equity: Float64Array;
  /** Notional carried at frame i: book notional x held, zero after margin_call_i. */
  notional: Float64Array;
  /** Fraction of the full book held at frame i: 1, or 1 - cut_fraction between a cut and the next restore. */
  held: Float64Array;
  /** (equity - maintenance x notional) / equity, clamped 0..1. 1 when flat (no margin needed). */
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
  /** Seconds to add to `times` for the clock the sun follows: 0 (UTC) for FX, the New York offset for equities. */
  solarOffsetS: Float64Array;
  /** IANA zone of the exchange for equity bundles (the sun and the HUD's local time follow it), else null. */
  exchangeTz: string | null;
  /** 1 while the market is closed (series.market_open = 0); null when the bundle has no market_open series. */
  closed: Uint8Array | null;
  /** Maintenance margin rate of this bundle's book: 2.5% FX, 15% equity. */
  maintenance: number;
  bookNotional: number;
  ships: Record<ShipKey, ShipDerived>;
  /** Survive mode: the player's ship (the scene then draws only this ship). Null in Replay mode. */
  player: ShipDerived | null;
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
  /** The market closes (resumeAt: epoch seconds of reopening, null if it stays closed) or reopens (gapPct from the last price before the close). */
  | { kind: "market"; open: false; resumeAt: number | null }
  | { kind: "market"; open: true; price: number; gapPct: number | null }
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
        const trip: CrateTrip = { crate: total - 1 - j, out: (a.at ?? a.i) + j * CRATE_STAGGER, back: null };
        trips.push(trip);
        open.push(trip);
      }
    } else {
      // Lowest of the thrown crates first, so the stack is rebuilt from the bottom.
      open.sort((x, y) => x.crate - y.crate);
      open.forEach((trip, m) => (trip.back = (a.at ?? a.i) + m * CRATE_STAGGER));
      open.length = 0;
    }
  }
  return trips;
}

/** What buildShip needs: the series of one ship, whoever computed them (the bundle, or the player's simulation). */
interface ShipSeries {
  key: SceneShip;
  label: string;
  startEquity: number;
  equity: Float64Array;
  /** Open notional per frame, USD (0 once sunk). */
  notional: Float64Array;
  /** Share of the full book held at frame i. */
  held: Float64Array;
  maintenance: number;
  cutFraction: number;
  marginCallI: number | null;
  actions: BookAction[];
  actionsFromEvents: boolean;
  /** Fallbacks for cutI / restoreI when `actions` holds none (the bundle's ships.*.cut_i / restore_i). */
  cutI: number | null;
  restoreI: number | null;
  crateCount: number;
}

/** The per-frame quantities the scene and the labels read (buffer, heel, sails, crate trips) from a ship's series. */
function buildShip(s: ShipSeries): ShipDerived {
  const { equity, notional, held, startEquity } = s;
  const n = equity.length;
  const buffer = new Float64Array(n);
  const heelDeg = new Float64Array(n);
  const rising = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    const maint = s.maintenance * notional[i];
    buffer[i] = notional[i] <= 0 ? 1 : equity[i] <= 0 ? 0 : clamp((equity[i] - maint) / equity[i], 0, 1);
    heelDeg[i] = clamp((1 - equity[i] / startEquity) * HEEL_DEG_PER_LOSS, 0, HEEL_MAX_DEG);
    const back = Math.max(0, i - 3);
    const d = (equity[i] - equity[back]) / startEquity;
    rising[i] = clamp(d * 400, 0, 1); // +0.25% of start equity in 3 minutes = full sail
  }
  const trips = planTrips(s.actions, s.crateCount, s.cutFraction);
  const tripsByCrate: CrateTrip[][] = Array.from({ length: s.crateCount }, () => []);
  for (const t of trips) tripsByCrate[t.crate].push(t);
  return {
    key: s.key,
    label: s.label,
    startEquity,
    equity,
    notional,
    held,
    buffer,
    heelDeg,
    rising,
    cutI: s.actions.find((x) => x.kind === "cut")?.i ?? s.cutI,
    restoreI: s.actions.find((x) => x.kind === "restore")?.i ?? s.restoreI,
    cutFraction: s.cutFraction,
    marginCallI: s.marginCallI,
    actions: s.actions,
    actionsFromEvents: s.actionsFromEvents,
    trips,
    tripsByCrate,
  };
}

function deriveShip(b: Bundle, key: ShipKey, bookNotional: number, crateCount: number, maintenance: number): ShipDerived {
  const info = b.ships[key];
  const eq = key === "prepared" ? b.series.prepared_equity : b.series.unprepared_equity;
  const n = b.n;
  const notional = new Float64Array(n);
  const held = new Float64Array(n);
  const { actions, fromEvents } = shipActions(b, key);

  let a = 0;
  let level = 1;
  for (let i = 0; i < n; i++) {
    while (a < actions.length && actions[a].i <= i) {
      level = actions[a].kind === "cut" ? 1 - info.cut_fraction : 1;
      a++;
    }
    held[i] = level;
    notional[i] = info.margin_call_i !== null && i >= info.margin_call_i ? 0 : bookNotional * level;
  }
  return buildShip({
    key,
    label: info.label,
    startEquity: info.start_equity_usd,
    equity: Float64Array.from(eq),
    notional,
    held,
    maintenance,
    cutFraction: info.cut_fraction,
    marginCallI: info.margin_call_i,
    actions,
    actionsFromEvents: fromEvents,
    cutI: info.cut_i,
    restoreI: info.restore_i ?? null,
    crateCount,
  });
}

/**
 * Crates on deck: one per USD_PER_CRATE of notional, capped at MAX_CRATES (then each crate grows), split across the
 * positions by notional. Used for the bundle's book and for the player's book at the chosen leverage.
 */
export function makeCrates(positions: { instrument: string; notional_usd: number }[]): CrateSpec[] {
  const bookNotional = positions.reduce((s, p) => s + p.notional_usd, 0);
  const crates: CrateSpec[] = [];
  if (bookNotional <= 0) return crates;
  const total = clamp(Math.round(bookNotional / USD_PER_CRATE), 1, MAX_CRATES);
  const perCrate = bookNotional / total;
  const size = clamp(Math.cbrt(perCrate / USD_PER_CRATE) * 1.05, 0.7, 1.7);
  positions.forEach((p, idx) => {
    const k = Math.max(p.notional_usd > 0 ? 1 : 0, Math.round(p.notional_usd / perCrate));
    for (let j = 0; j < k && crates.length < MAX_CRATES; j++) {
      crates.push({ positionIndex: idx, instrument: p.instrument, notionalUsd: p.notional_usd / k, size });
    }
  });
  return crates;
}

/** The player's ship from a Survive simulation: the base derivation with the player's own ship, cargo and triggers. */
export function withPlayer(
  base: Derived,
  sim: {
    equity: Float64Array;
    notional: Float64Array;
    held: Float64Array;
    maintenance: number;
    startEquity: number;
    marginCallI: number | null;
    applied: BookAction[];
  },
  crates: CrateSpec[],
): Derived {
  // The demo ships' own cut, restore and margin-call cues must not fire for the player: it makes those itself.
  const triggers = new Map<number, TriggerSpec[]>();
  base.triggers.forEach((specs, i) => {
    const keep = specs.filter(
      (t) => t.kind === "jump" || t.kind === "market" || (t.kind === "event" && t.event.type !== "cut" && t.event.type !== "restore" && t.event.type !== "margin_call"),
    );
    if (keep.length > 0) triggers.set(i, keep);
  });
  const player = buildShip({
    key: "player",
    label: "Your ship",
    startEquity: sim.startEquity,
    equity: sim.equity,
    notional: sim.notional,
    held: sim.held,
    maintenance: sim.maintenance,
    cutFraction: 0.75,
    marginCallI: sim.marginCallI,
    actions: sim.applied,
    actionsFromEvents: true,
    cutI: null,
    restoreI: null,
    crateCount: crates.length,
  });
  return { ...base, player, crates, triggers, bookNotional: crates.reduce((s, c) => s + c.notionalUsd, 0) };
}

/** A ship of the scene by key (the player's ship exists only in Survive mode). */
export function shipOf(d: Derived, key: SceneShip): ShipDerived {
  if (key === "player") {
    if (!d.player) throw new Error("no player ship outside Survive mode");
    return d.player;
  }
  return d.ships[key];
}

/**
 * Price decimals shown everywhere (HUD, chart axis, tooltips, toasts): 2 for equities (anything that is not FX),
 * 3 for yen pairs (USDJPY), 5 for other FX pairs (EURUSD, USDSGD).
 */
export function priceDecimalsFor(b: Pick<Bundle, "asset_class" | "source" | "symbol">): number {
  const fx = b.asset_class === "fx" && b.source !== "yahoo";
  if (!fx) return 2;
  return /JPY/i.test(b.symbol) ? 3 : 5;
}

export function derive(b: Bundle): Derived {
  const n = b.n;
  const times = new Float64Array(n);
  for (let i = 0; i < n; i++) times[i] = b.t0 + i * b.step_s;
  const bookNotional = b.exposure.positions.reduce((s, p) => s + p.notional_usd, 0);
  const maintenance = maintenanceFor(b);
  const tz = exchangeTz(b);
  const solarOffsetS = new Float64Array(n);
  if (tz) {
    const byHour = new Map<number, number>(); // one Intl lookup per UTC hour is enough: offsets change at most twice a year
    for (let i = 0; i < n; i++) {
      const h = Math.floor(times[i] / 3600);
      let off = byHour.get(h);
      if (off === undefined) byHour.set(h, (off = tzOffsetSeconds(tz, times[i])));
      solarOffsetS[i] = off;
    }
  }
  const closed = b.series.market_open ? Uint8Array.from(b.series.market_open, (v) => (v === 0 ? 1 : 0)) : null;

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

  const crates = makeCrates(b.exposure.positions);

  const triggers = new Map<number, TriggerSpec[]>();
  const add = (i: number, t: TriggerSpec) => {
    const arr = triggers.get(i);
    if (arr) arr.push(t);
    else triggers.set(i, [t]);
  };
  for (let i = 0; i < n; i++) if (b.series.jump[i] === 1) add(i, { kind: "jump" });
  for (const e of b.events) add(e.i, { kind: "event", event: e });
  if (closed) {
    for (let i = 1; i < n; i++) {
      if (closed[i - 1] === 0 && closed[i] === 1) {
        let r = i;
        while (r < n && closed[r] === 1) r++;
        add(i, { kind: "market", open: false, resumeAt: r < n ? times[r] : null });
      } else if (closed[i - 1] === 1 && closed[i] === 0) {
        const last = b.series.mid[i - 1];
        const first = b.series.open[i];
        add(i, { kind: "market", open: true, price: first, gapPct: last > 0 ? (first / last - 1) * 100 : null });
      }
    }
  }
  const prepared = deriveShip(b, "prepared", bookNotional, crates.length, maintenance);
  const unprepared = deriveShip(b, "unprepared", bookNotional, crates.length, maintenance);
  for (const [key, ship] of [["prepared", prepared], ["unprepared", unprepared]] as const) {
    if (ship.actionsFromEvents) continue; // the cut / restore events already trigger toasts and sound
    for (const act of ship.actions) {
      add(act.i, act.kind === "cut" ? { kind: "cut", ship: key, fraction: ship.cutFraction } : { kind: "restore", ship: key });
    }
  }

  return {
    n,
    times,
    solarOffsetS,
    exchangeTz: tz,
    closed,
    maintenance,
    bookNotional,
    ships: { prepared, unprepared },
    player: null,
    alarmActive,
    alarms,
    watches,
    squalls,
    fairWinds,
    crates,
    priceDecimals: priceDecimalsFor(b),
    triggers,
  };
}

/** First frame after `i` where the market trades again, or null when it stays closed to the end (or is open at `i`). */
export function reopenFrame(d: Pick<Derived, "closed" | "n">, i: number): number | null {
  if (!d.closed || d.closed[i] !== 1) return null;
  for (let r = i + 1; r < d.n; r++) if (d.closed[r] === 0) return r;
  return null;
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
