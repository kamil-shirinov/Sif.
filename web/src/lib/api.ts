// Hooks for the live server (CC-L). Every call here is optional: with no server running, each one
// resolves to null (or throws ApiError for the navigator) and the app plays the bundle as it is.
//
//   GET  /api/health                          -> { ok: true, tiger: bool, navigator: bool }
//   GET  /api/candles?symbol=&from=&to=       -> { candles: [...], query_ms }  (from and to: ISO 8601 UTC)
//                                                bars of ANY size (1 minute, 5 minutes, ...): the size is read from the
//                                                response (bucket_s, bucket, interval, ...) or from the bar spacing
//   POST /api/navigator/ask {question, storm_id} -> { answer, verified, inspector?, scenario? }
//
// The vite dev server proxies /api to http://localhost:8000 (vite.config.ts). Set VITE_API_BASE to
// point a built app at a server elsewhere (that server must then allow CORS).

import type { Bundle, Inspector } from "../types/bundle";
import type { Health, LiveCandles, LiveRow } from "../state/app";
import { validateBundle } from "./loadBundle";

// VITE_API_BASE=off (the public GitHub Pages build) means there is no live server: no request is made.
const API = ((import.meta.env.VITE_API_BASE as string | undefined) ?? "/api").replace(/\/$/, "");
const NO_API = API === "off";

export class ApiError extends Error {}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

/** fetch with a timeout; `outer` aborts it from the caller too. */
async function request(path: string, init: RequestInit, timeoutMs: number, outer?: AbortSignal): Promise<Response> {
  if (NO_API) throw new ApiError("no live server in this build");
  const ctl = new AbortController();
  const timer = window.setTimeout(() => ctl.abort(), timeoutMs);
  const onOuter = () => ctl.abort();
  outer?.addEventListener("abort", onOuter);
  try {
    return await fetch(`${API}${path}`, { ...init, signal: ctl.signal });
  } finally {
    window.clearTimeout(timer);
    outer?.removeEventListener("abort", onOuter);
  }
}

// ---------- health ----------

/** The server's health, or null when there is no server or it is not ok. */
export async function fetchHealth(signal?: AbortSignal): Promise<Health | null> {
  try {
    const res = await request("/health", { headers: { Accept: "application/json" } }, 3000, signal);
    if (!res.ok) return null;
    const j: unknown = await res.json();
    if (!isObj(j) || j.ok !== true) return null;
    return { tiger: j.tiger === true, navigator: j.navigator === true };
  } catch {
    return null;
  }
}

// ---------- candles ----------

const isoUtc = (epochSec: number) => new Date(epochSec * 1000).toISOString().replace(/\.\d{3}Z$/, "Z");

function pick(o: Record<string, unknown>, keys: string[]): unknown {
  for (const k of keys) if (o[k] !== undefined && o[k] !== null) return o[k];
  return undefined;
}

/** Epoch seconds from a number (seconds or milliseconds) or an ISO string (UTC when it names no zone). */
function toEpochSeconds(v: unknown): number | null {
  if (isNum(v)) return v > 1e11 ? v / 1000 : v;
  if (typeof v === "string") {
    let s = v.trim().replace(" ", "T");
    if (!/(Z|[+-]\d\d:?\d\d)$/i.test(s)) s += "Z";
    const ms = Date.parse(s);
    return Number.isFinite(ms) ? ms / 1000 : null;
  }
  return null;
}

interface Row {
  t: number;
  o: number;
  h: number;
  l: number;
  c: number;
}

function toRow(r: unknown): Row | null {
  let t: unknown, o: unknown, h: unknown, l: unknown, c: unknown;
  if (Array.isArray(r)) [t, o, h, l, c] = r;
  else if (isObj(r)) {
    t = pick(r, ["time", "t", "ts", "timestamp", "time_utc", "ts_utc", "bucket"]);
    o = pick(r, ["open", "o"]);
    h = pick(r, ["high", "h"]);
    l = pick(r, ["low", "l"]);
    c = pick(r, ["close", "c", "mid"]);
  } else return null;
  const ts = toEpochSeconds(t);
  if (ts === null || !isNum(o) || !isNum(h) || !isNum(l) || !isNum(c)) return null;
  return { t: ts, o, h, l, c };
}

/** "5m", "5 min", "300s", "1h", "PT5M", 300 (seconds) -> seconds; null when it is not a size. */
export function parseBucketSeconds(v: unknown): number | null {
  if (isNum(v)) return v > 0 ? v : null;
  if (typeof v !== "string") return null;
  const s = v.trim().toLowerCase();
  const iso = /^pt(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m)?(?:(\d+(?:\.\d+)?)s)?$/.exec(s);
  if (iso && (iso[1] || iso[2] || iso[3])) return Number(iso[1] ?? 0) * 3600 + Number(iso[2] ?? 0) * 60 + Number(iso[3] ?? 0);
  const m = /^(\d+(?:\.\d+)?)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours)$/.exec(s);
  if (!m) return null;
  const unit = m[2][0] === "s" ? 1 : m[2][0] === "m" ? 60 : 3600;
  return Number(m[1]) * unit;
}

/** The bar size in seconds: stated by the server, else the median spacing between bars. */
function barSeconds(raw: unknown, rows: Row[]): number | null {
  if (isObj(raw)) {
    const meta = isObj(raw.meta) ? raw.meta : {};
    for (const key of ["bucket_s", "bucket_seconds", "interval_s", "step_s", "bucket", "interval", "resolution", "timeframe"]) {
      const v = parseBucketSeconds(raw[key] ?? meta[key]);
      if (v !== null) return v;
    }
  }
  const gaps: number[] = [];
  for (let i = 1; i < rows.length; i++) {
    const d = rows[i].t - rows[i - 1].t;
    if (d > 0) gaps.push(d);
  }
  if (gaps.length === 0) return null;
  gaps.sort((a, b) => a - b);
  return gaps[Math.floor(gaps.length / 2)];
}

/**
 * Lay the server's candles onto the bundle's frames, whatever the bar size. One-minute (or finer) bars fill the
 * per-frame arrays, merged when several fall in one frame. Coarser bars (5 minutes, 15 minutes, ...) are kept as
 * rows that the chart aggregates; only bars that sit wholly inside the bundle's window count. Frames the server did
 * not cover keep the bundle's own values; if the server covers under 80% of the window the result is rejected, so
 * the chart never mixes sources in a way that would mislead.
 */
export function candlesOntoFrames(raw: unknown, b: Bundle, seq: number): LiveCandles | null {
  const list = Array.isArray(raw) ? raw : isObj(raw) ? pick(raw, ["candles", "rows", "bars", "data"]) : undefined;
  if (!Array.isArray(list)) return null;
  const meta = isObj(raw) && isObj(raw.meta) ? raw.meta : null;
  const q = isObj(raw) ? (raw.query_ms ?? meta?.query_ms) : undefined;
  const rows = list.map(toRow).filter((r): r is Row => r !== null).sort((a, b2) => a.t - b2.t);
  if (rows.length === 0) return null;
  const barS = barSeconds(raw, rows);
  if (barS === null) return null;
  const k = Math.max(1, Math.round(barS / b.step_s));

  const open = b.series.open.slice();
  const high = b.series.high.slice();
  const low = b.series.low.slice();
  const mid = b.series.mid.slice();
  const covered = new Uint8Array(b.n);

  if (k === 1) {
    const touched = new Uint8Array(b.n);
    for (const r of rows) {
      const i = Math.round((r.t - b.t0) / b.step_s);
      if (i < 0 || i >= b.n || Math.abs(r.t - (b.t0 + i * b.step_s)) > b.step_s / 2) continue;
      if (touched[i]) {
        // finer than the bundle's step: several bars in one frame
        high[i] = Math.max(high[i], r.h);
        low[i] = Math.min(low[i], r.l);
        mid[i] = r.c;
      } else {
        touched[i] = 1;
        open[i] = r.o;
        high[i] = Math.max(r.h, r.o, r.c);
        low[i] = Math.min(r.l, r.o, r.c);
        mid[i] = r.c;
      }
      covered[i] = 1;
    }
    const matched = covered.reduce((s, v) => s + v, 0);
    if (matched < b.n * 0.8) return null;
    return { seq, bucketFrames: 1, open, high, low, mid, rows: [], rowAt: new Int32Array(0), queryMs: isNum(q) ? q : null };
  }

  const bars: LiveRow[] = [];
  const rowAt = new Int32Array(b.n).fill(-1);
  for (const r of rows) {
    const first = Math.round((r.t - b.t0) / b.step_s);
    if (first < 0 || first + k > b.n || Math.abs(r.t - (b.t0 + first * b.step_s)) > b.step_s / 2) continue;
    if (rowAt[first] !== -1) continue;
    const idx = bars.length;
    bars.push({ first, span: k, open: r.o, high: Math.max(r.h, r.o, r.c), low: Math.min(r.l, r.o, r.c), close: r.c });
    for (let i = first; i < first + k; i++) {
      if (rowAt[i] === -1) {
        rowAt[i] = idx;
        covered[i] = 1;
      }
    }
  }
  const matched = covered.reduce((s, v) => s + v, 0);
  if (matched < b.n * 0.8) return null;
  return { seq, bucketFrames: k, open, high, low, mid, rows: bars, rowAt, queryMs: isNum(q) ? q : null };
}

/** The bundle's window as the server's candles, or null (no server, an error, or too few bars). */
export async function fetchCandles(b: Bundle, seq: number, signal?: AbortSignal): Promise<LiveCandles | null> {
  const qs = new URLSearchParams({
    symbol: b.symbol,
    from: isoUtc(b.t0),
    to: isoUtc(b.t0 + (b.n - 1) * b.step_s),
  });
  try {
    const res = await request(`/candles?${qs}`, { headers: { Accept: "application/json" } }, 8000, signal);
    if (!res.ok) return null;
    return candlesOntoFrames(await res.json(), b, seq);
  } catch {
    return null;
  }
}

// ---------- navigator ----------

export interface NavigatorAnswer {
  answer: string;
  /** Every number in the answer was checked by code. */
  verified: boolean;
  unverified: unknown[];
  inspector: Inspector | null;
  /** A what-if bundle (source "scenario") the navigator built, validated and ready to sail. */
  scenario: Bundle | null;
  /** Why a scenario in the response could not be used. */
  scenarioError: string | null;
}

export const NAVIGATOR_MAX_QUESTION = 500;

export async function askNavigator(question: string, stormId: string, signal?: AbortSignal): Promise<NavigatorAnswer> {
  let res: Response;
  try {
    res = await request(
      "/navigator/ask",
      {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ question: question.slice(0, NAVIGATOR_MAX_QUESTION), storm_id: stormId }),
      },
      90_000,
      signal,
    );
  } catch (e) {
    if (signal?.aborted) throw new ApiError("Cancelled");
    throw new ApiError(e instanceof DOMException && e.name === "AbortError" ? "The navigator took too long to answer." : "The navigator is not reachable.");
  }
  let j: unknown = null;
  try {
    j = await res.json();
  } catch {
    /* not JSON */
  }
  if (!res.ok) {
    const detail = isObj(j) ? pick(j, ["detail", "error", "message"]) : undefined;
    throw new ApiError(typeof detail === "string" ? detail : `The navigator answered HTTP ${res.status}.`);
  }
  if (!isObj(j)) throw new ApiError("The navigator sent an answer this app cannot read.");
  const text = pick(j, ["answer", "text"]);
  if (typeof text !== "string" || text.trim() === "") throw new ApiError("The navigator sent no answer.");

  let inspector: Inspector | null = null;
  if (isObj(j.inspector) && typeof j.inspector.verdict === "string") {
    inspector = {
      verdict: j.inspector.verdict,
      issues: Array.isArray(j.inspector.issues) ? j.inspector.issues.filter((x): x is string => typeof x === "string") : [],
    };
  }
  let scenario: Bundle | null = null;
  let scenarioError: string | null = null;
  const rawScenario = pick(j, ["scenario", "bundle"]);
  if (rawScenario !== undefined) {
    try {
      scenario = validateBundle(rawScenario);
    } catch (e) {
      scenarioError = e instanceof Error ? e.message : "The scenario is not a valid replay bundle.";
    }
  }
  return {
    answer: text,
    verified: j.verified === true,
    unverified: Array.isArray(j.unverified_numbers) ? j.unverified_numbers : [],
    inspector,
    scenario,
    scenarioError,
  };
}
