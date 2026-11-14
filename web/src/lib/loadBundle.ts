import type { Bundle, BundleEvent, ShipKey } from "../types/bundle";
import { SERIES_KEYS } from "../types/bundle";

export class BundleError extends Error {}

const STORM_ID_RE = /^[A-Za-z0-9_-]{1,80}$/;

/** The storm named by ?storm=, default mock_storm. Only safe file names are accepted. */
export function stormIdFromUrl(search = window.location.search): string {
  const id = new URLSearchParams(search).get("storm") ?? "mock_storm";
  if (!STORM_ID_RE.test(id)) throw new BundleError(`Invalid storm id "${id}"`);
  return id;
}

export async function loadBundle(stormId: string): Promise<Bundle> {
  const url = `${import.meta.env.BASE_URL}bundles/${encodeURIComponent(stormId)}.json`;
  let res: Response;
  try {
    res = await fetch(url, { cache: "no-cache" });
  } catch (e) {
    throw new BundleError(`Could not fetch ${url}: ${(e as Error).message}`);
  }
  if (!res.ok) throw new BundleError(`Bundle ${url} returned HTTP ${res.status}`);
  let raw: unknown;
  try {
    raw = await res.json();
  } catch {
    throw new BundleError(`Bundle ${url} is not valid JSON`);
  }
  return validateBundle(raw);
}

function fail(msg: string): never {
  throw new BundleError(`Bundle check failed: ${msg}`);
}

function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function num(o: Record<string, unknown>, k: string, where: string): number {
  const v = o[k];
  if (typeof v !== "number" || !Number.isFinite(v)) fail(`${where}.${k} must be a finite number`);
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

/** Runtime checks that the JSON matches contracts/replay_bundle.md (schema_version 1). */
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

  // series: every array has length n
  if (!isObj(raw.series)) fail("series must be an object");
  const series = raw.series;
  for (const k of SERIES_KEYS) {
    const arr = series[k];
    if (!Array.isArray(arr)) fail(`series.${k} is missing or not an array`);
    if (arr.length !== n) fail(`series.${k} has length ${arr.length}, expected n = ${n}`);
    for (let i = 0; i < arr.length; i++) {
      const v = arr[i];
      if (typeof v !== "number" || !Number.isFinite(v)) fail(`series.${k}[${i}] is not a finite number`);
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
  for (const key of ["prepared", "unprepared"] as ShipKey[]) {
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
  }

  // events
  if (!Array.isArray(raw.events)) fail("events must be an array");
  raw.events.forEach((e: unknown, idx: number) => {
    const w = `events[${idx}]`;
    if (!isObj(e)) fail(`${w} must be an object`);
    frameIn(int(e, "i", w), n, `${w}.i`);
    str(e, "text", w);
    const type = str(e, "type", w) as BundleEvent["type"];
    switch (type) {
      case "watch":
        frameIn(int(e, "at_i", w), n, `${w}.at_i`);
        break;
      case "alarm":
        num(e, "move_ahead_pct", w);
        break;
      case "margin_call": {
        const ship = str(e, "ship", w);
        if (ship !== "prepared" && ship !== "unprepared") fail(`${w}.ship must be prepared or unprepared`);
        break;
      }
      case "all_clear":
        break;
      default:
        fail(`${w}.type "${String(type)}" is not watch, alarm, margin_call or all_clear`);
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

  // report
  if (raw.report !== null) {
    if (!isObj(raw.report)) fail("report must be an object or null");
    str(raw.report, "text", "report");
    if (typeof raw.report.verified !== "boolean") fail("report.verified must be a boolean");
    if (!Array.isArray(raw.report.unverified_numbers)) fail("report.unverified_numbers must be an array");
    str(raw.report, "model", "report");
  }

  const bundle = raw as unknown as Bundle;
  bundle.events = [...bundle.events].sort((a, b) => a.i - b.i);
  return bundle;
}
