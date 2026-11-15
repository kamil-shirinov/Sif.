import type {
  Bundle,
  BundleEvent,
  IndexMetrics,
  Inspector,
  Report,
  ShipKey,
  StormIndex,
  StormIndexEntry,
} from "../types/bundle";
import { SERIES_KEYS } from "../types/bundle";

export class BundleError extends Error {}

export const DEFAULT_STORM_ID = "mock_storm";

const STORM_ID_RE = /^[A-Za-z0-9_-]{1,80}$/;
const FILE_RE = /^[A-Za-z0-9_-][A-Za-z0-9_.-]{0,100}\.json$/;

/** The storm named by ?storm=, or null when the URL does not name one. Only safe file names are accepted. */
export function stormIdFromUrl(search = window.location.search): string | null {
  const id = new URLSearchParams(search).get("storm");
  if (id === null) return null;
  if (!STORM_ID_RE.test(id)) throw new BundleError(`Invalid storm id "${id}"`);
  return id;
}

const bundlesUrl = (name: string) => `${import.meta.env.BASE_URL}bundles/${name}`;

async function fetchJson(url: string): Promise<unknown> {
  let res: Response;
  try {
    res = await fetch(url, { cache: "no-cache" });
  } catch (e) {
    throw new BundleError(`Could not fetch ${url}: ${(e as Error).message}`);
  }
  if (!res.ok) throw new BundleError(`${url} returned HTTP ${res.status}`);
  try {
    return await res.json();
  } catch {
    throw new BundleError(`${url} is not valid JSON`);
  }
}

/** Load public/bundles/<file>. `file` defaults to <stormId>.json (index.json entries name their own file). */
export async function loadBundle(stormId: string, file?: string): Promise<Bundle> {
  if (!STORM_ID_RE.test(stormId)) throw new BundleError(`Invalid storm id "${stormId}"`);
  const name = file && FILE_RE.test(file) ? file : `${stormId}.json`;
  return validateBundle(await fetchJson(bundlesUrl(encodeURIComponent(name))));
}

/** Load public/bundles/index.json. Returns null when it is missing or unreadable: the app then plays mock_storm. */
export async function loadIndex(): Promise<StormIndex | null> {
  try {
    return parseIndex(await fetchJson(bundlesUrl("index.json")));
  } catch {
    return null;
  }
}

// ---------- helpers ----------

function fail(msg: string): never {
  throw new BundleError(`Bundle check failed: ${msg}`);
}

function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isInt = (v: unknown): v is number => isNum(v) && Number.isInteger(v);

function num(o: Record<string, unknown>, k: string, where: string): number {
  const v = o[k];
  if (!isNum(v)) fail(`${where}.${k} must be a finite number`);
  return v;
}

function int(o: Record<string, unknown>, k: string, where: string): number {
  const v = num(o, k, where);
  if (!Number.isInteger(v)) fail(`${where}.${k} must be an integer`);
  return v;
}

function str(o: Record<string, unknown>, k: string, where: string): string {
  const v = o[k];
  if (typeof v !== "string") fail(`${where}.${k} must be a string`);
  return v;
}

function intOrNull(o: Record<string, unknown>, k: string, where: string): number | null {
  if (o[k] === null) return null;
  return int(o, k, where);
}

function frameIn(i: number, n: number, where: string) {
  if (i < 0 || i >= n) fail(`${where} = ${i} is outside 0..${n - 1}`);
}

const inFrames = (v: unknown, n: number): v is number => isInt(v) && v >= 0 && v < n;

const SHIP_KEYS: ShipKey[] = ["prepared", "unprepared"];

/** Lenient report: a bundle without a usable report text simply has no report panel. */
function parseReport(raw: unknown): Report | null {
  if (!isObj(raw) || typeof raw.text !== "string" || raw.text.trim() === "") return null;
  let inspector: Inspector | null = null;
  if (isObj(raw.inspector) && typeof raw.inspector.verdict === "string") {
    const issues = Array.isArray(raw.inspector.issues) ? raw.inspector.issues.filter((x): x is string => typeof x === "string") : [];
    inspector = { verdict: raw.inspector.verdict, issues };
  }
  return {
    text: raw.text,
    verified: raw.verified === true,
    unverified_numbers: Array.isArray(raw.unverified_numbers) ? raw.unverified_numbers : [],
    model: typeof raw.model === "string" ? raw.model : "",
    inspector,
  };
}

/**
 * Runtime checks that the JSON matches contracts/replay_bundle.md (schema_version 1).
 * The core (series, ships, exposure) is strict: the scene cannot run without it. The additions
 * (restore_i, squall / fair_wind / cut / restore events, storm.event, report.inspector) are lenient:
 * a malformed addition is dropped, never fatal.
 */
export function validateBundle(raw: unknown): Bundle {
  if (!isObj(raw)) fail("top level must be an object");
  if (raw.schema_version !== 1) fail(`schema_version must be 1, got ${String(raw.schema_version)}`);
  str(raw, "storm_id", "bundle");
  str(raw, "title", "bundle");
  str(raw, "symbol", "bundle");
  str(raw, "asset_class", "bundle");
  str(raw, "source", "bundle");
  if (typeof raw.book_is_synthetic !== "boolean") fail("book_is_synthetic must be a boolean");
  int(raw, "t0", "bundle");
  const step = int(raw, "step_s", "bundle");
  if (step <= 0) fail("step_s must be positive");
  const n = int(raw, "n", "bundle");
  if (n < 2) fail("n must be at least 2");

  // storm
  if (!isObj(raw.storm)) fail("storm must be an object");
  const st = raw.storm;
  frameIn(int(st, "onset_i", "storm"), n, "storm.onset_i");
  frameIn(int(st, "trough_i", "storm"), n, "storm.trough_i");
  num(st, "move_bp", "storm");
  const kind = str(st, "kind", "storm");
  if (kind !== "scheduled" && kind !== "unscheduled") fail(`storm.kind must be scheduled or unscheduled`);
  str(st, "label", "storm");
  if (typeof st.event !== "string" || st.event.trim() === "") delete st.event;
  if (!inFrames(st.event_i, n)) delete st.event_i;

  // series: every array has length n
  if (!isObj(raw.series)) fail("series must be an object");
  const series = raw.series;
  for (const k of SERIES_KEYS) {
    const arr = series[k];
    if (!Array.isArray(arr)) fail(`series.${k} is missing or not an array`);
    if (arr.length !== n) fail(`series.${k} has length ${arr.length}, expected n = ${n}`);
    for (let i = 0; i < arr.length; i++) {
      const v = arr[i];
      if (!isNum(v)) fail(`series.${k}[${i}] is not a finite number`);
    }
  }
  // market_open is optional and lenient: anything that is not 0/1 per frame means "always open".
  if (series.market_open !== undefined) {
    const mo = series.market_open;
    if (!Array.isArray(mo) || mo.length !== n || !mo.every((v) => v === 0 || v === 1)) {
      console.warn("Ignoring series.market_open: it must hold 0 or 1 for each of the n frames");
      delete series.market_open;
    }
  }
  const s = series as unknown as Record<string, number[]>;
  for (let i = 0; i < n; i++) {
    if (s.risk[i] < 0 || s.risk[i] > 1) fail(`series.risk[${i}] = ${s.risk[i]} is outside 0..1`);
    if (![0, 1, 2].includes(s.state[i])) fail(`series.state[${i}] must be 0, 1 or 2`);
    if (s.jump[i] !== 0 && s.jump[i] !== 1) fail(`series.jump[${i}] must be 0 or 1`);
  }

  // ships
  if (!isObj(raw.ships)) fail("ships must be an object");
  for (const key of SHIP_KEYS) {
    const sh = raw.ships[key];
    const w = `ships.${key}`;
    if (!isObj(sh)) fail(`${w} must be an object`);
    str(sh, "label", w);
    if (num(sh, "start_equity_usd", w) <= 0) fail(`${w}.start_equity_usd must be positive`);
    const mc = intOrNull(sh, "margin_call_i", w);
    if (mc !== null) frameIn(mc, n, `${w}.margin_call_i`);
    const cut = intOrNull(sh, "cut_i", w);
    if (cut !== null) frameIn(cut, n, `${w}.cut_i`);
    const cf = num(sh, "cut_fraction", w);
    if (cf < 0 || cf > 1) fail(`${w}.cut_fraction must be between 0 and 1`);
    // restore_i is optional: anything that is not a frame in range counts as "no restore".
    sh.restore_i = inFrames(sh.restore_i, n) ? sh.restore_i : null;
  }

  // events
  if (!Array.isArray(raw.events)) fail("events must be an array");
  const events: BundleEvent[] = [];
  raw.events.forEach((e: unknown, idx: number) => {
    const w = `events[${idx}]`;
    if (!isObj(e)) fail(`${w} must be an object`);
    const type = str(e, "type", w);
    switch (type) {
      case "watch": {
        frameIn(int(e, "i", w), n, `${w}.i`);
        str(e, "text", w);
        // at_i and event are optional: without at_i there is no storm front, only the toast.
        if (!inFrames(e.at_i, n)) delete e.at_i;
        if (typeof e.event !== "string" || e.event.trim() === "") delete e.event;
        events.push(e as unknown as BundleEvent);
        return;
      }
      case "alarm":
        frameIn(int(e, "i", w), n, `${w}.i`);
        str(e, "text", w);
        // null (or absent) for an alarm that no storm followed: a false alarm has no move ahead of it.
        if (e.move_ahead_pct === null || e.move_ahead_pct === undefined) e.move_ahead_pct = null;
        else num(e, "move_ahead_pct", w);
        events.push(e as unknown as BundleEvent);
        return;
      case "margin_call": {
        frameIn(int(e, "i", w), n, `${w}.i`);
        str(e, "text", w);
        const ship = str(e, "ship", w);
        if (ship !== "prepared" && ship !== "unprepared") fail(`${w}.ship must be prepared or unprepared`);
        events.push(e as unknown as BundleEvent);
        return;
      }
      case "all_clear":
        frameIn(int(e, "i", w), n, `${w}.i`);
        str(e, "text", w);
        events.push(e as unknown as BundleEvent);
        return;
      case "squall":
      case "fair_wind":
      case "cut":
      case "restore": {
        if (!inFrames(e.i, n)) {
          console.warn(`Ignoring ${w}: ${type} with frame ${String(e.i)} outside 0..${n - 1}`);
          return;
        }
        if (typeof e.text !== "string") e.text = "";
        if (e.ship !== "prepared" && e.ship !== "unprepared") delete e.ship;
        events.push(e as unknown as BundleEvent);
        return;
      }
      default:
        console.warn(`Ignoring ${w}: unknown event type "${type}"`);
    }
  });

  // exposure
  if (!isObj(raw.exposure)) fail("exposure must be an object");
  const ex = raw.exposure;
  frameIn(int(ex, "as_of_i", "exposure"), n, "exposure.as_of_i");
  if (!Array.isArray(ex.positions)) fail("exposure.positions must be an array");
  ex.positions.forEach((p: unknown, idx: number) => {
    const w = `exposure.positions[${idx}]`;
    if (!isObj(p)) fail(`${w} must be an object`);
    str(p, "instrument", w);
    str(p, "side", w);
    if (num(p, "notional_usd", w) < 0) fail(`${w}.notional_usd must be non-negative`);
  });
  if (!isObj(ex.net_usd_by_ccy)) fail("exposure.net_usd_by_ccy must be an object");
  for (const k of Object.keys(ex.net_usd_by_ccy)) num(ex.net_usd_by_ccy, k, "exposure.net_usd_by_ccy");
  num(ex, "leverage", "exposure");
  num(ex, "margin_buffer_pct", "exposure");

  // stress
  if (!Array.isArray(raw.stress)) fail("stress must be an array");
  raw.stress.forEach((r: unknown, idx: number) => {
    const w = `stress[${idx}]`;
    if (!isObj(r)) fail(`${w} must be an object`);
    str(r, "scenario", w);
    num(r, "pnl_usd", w);
    if (typeof r.margin_call !== "boolean") fail(`${w}.margin_call must be a boolean`);
  });

  // report: optional, lenient
  const bundle = raw as unknown as Bundle;
  bundle.report = parseReport(raw.report);
  bundle.events = events.sort((a, b) => a.i - b.i);
  return bundle;
}

// ---------- index.json ----------

const numOrNull = (v: unknown): number | null => (isNum(v) ? v : null);

function parseMetrics(raw: unknown): IndexMetrics | null {
  if (!isObj(raw)) return null;
  const m: IndexMetrics = {
    split: typeof raw.split === "string" ? raw.split : null,
    storms: numOrNull(raw.storms),
    alarmed: numOrNull(raw.alarmed),
    caught: numOrNull(raw.caught),
    median_move_ahead_pct: numOrNull(raw.median_move_ahead_pct),
    median_minutes_to_alarm: numOrNull(raw.median_minutes_to_alarm),
    false_alarms_per_day: numOrNull(raw.false_alarms_per_day),
    false_alarm_episodes_per_day: numOrNull(raw.false_alarm_episodes_per_day),
  };
  return m;
}

/** Lenient: bad entries are skipped; anything unreadable gives null. */
export function parseIndex(raw: unknown): StormIndex | null {
  if (!isObj(raw) || !Array.isArray(raw.storms)) return null;
  const storms: StormIndexEntry[] = [];
  // The public build's index lists the storms and the metrics but ships no bundle for them.
  const withheld = raw.bundles === "withheld";
  for (const e of raw.storms) {
    if (!isObj(e) || typeof e.storm_id !== "string" || !STORM_ID_RE.test(e.storm_id)) continue;
    storms.push({
      storm_id: e.storm_id,
      title: typeof e.title === "string" ? e.title : e.storm_id,
      symbol: typeof e.symbol === "string" ? e.symbol : "",
      asset_class: typeof e.asset_class === "string" ? e.asset_class : "fx",
      kind: e.kind === "scheduled" ? "scheduled" : "unscheduled",
      move_bp: isNum(e.move_bp) ? e.move_bp : 0,
      file: typeof e.file === "string" && FILE_RE.test(e.file) ? e.file : `${e.storm_id}.json`,
    });
  }
  const metrics = parseMetrics(raw.metrics);
  return withheld ? { schema_version: 1, storms: [], metrics, withheld: storms } : { schema_version: 1, storms, metrics };
}

/** True when the index lists this storm but this build does not ship its bundle (the public Pages build). */
export function isWithheld(index: StormIndex | null | undefined, id: string): boolean {
  return !!index?.withheld?.some((s) => s.storm_id === id);
}

/** What a reader sees in place of a replay whose market data is not redistributed. */
export const WITHHELD_NOTE = "Replay in the local demo (market data not redistributed)";
