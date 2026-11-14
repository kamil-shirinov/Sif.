// Hooks for the live server (CC-L). Every call here is optional: with no server running, each one
// resolves to null (or throws ApiError for the navigator) and the app plays the bundle as it is.
//
//   GET  /api/health                          -> { ok: true, tiger: bool, navigator: bool }
//   GET  /api/candles?symbol=&from=&to=       -> { candles: [...], query_ms }  (from and to: ISO 8601 UTC)
//   POST /api/navigator/ask {question, storm_id} -> { answer, verified, inspector?, scenario? }
//
// The vite dev server proxies /api to http://localhost:8000 (vite.config.ts). Set VITE_API_BASE to
// point a built app at a server elsewhere (that server must then allow CORS).

import type { Bundle, Inspector } from "../types/bundle";
import type { Health, LiveCandles } from "../state/app";
import { validateBundle } from "./loadBundle";

const API = ((import.meta.env.VITE_API_BASE as string | undefined) ?? "/api").replace(/\/$/, "");

export class ApiError extends Error {}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

/** fetch with a timeout; `outer` aborts it from the caller too. */
async function request(path: string, init: RequestInit, timeoutMs: number, outer?: AbortSignal): Promise<Response> {
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
    t = pick(r, ["time", "t", "ts", "timestamp", "time_utc", "ts_utc"]);
    o = pick(r, ["open", "o"]);
    h = pick(r, ["high", "h"]);
    l = pick(r, ["low", "l"]);
    c = pick(r, ["close", "c", "mid"]);
  } else return null;
  const ts = toEpochSeconds(t);
  if (ts === null || !isNum(o) || !isNum(h) || !isNum(l) || !isNum(c)) return null;
  return { t: ts, o, h, l, c };
}

/**
 * Lay server candles onto the bundle's frames. Expects one-minute bars. Frames the server did not return
 * keep the bundle's own values; if the server covers less than 80% of the window the result is rejected,
 * so the chart never mixes sources in a way that would mislead.
 */
export function candlesOntoFrames(raw: unknown, b: Bundle, seq: number): LiveCandles | null {
  const rows = Array.isArray(raw) ? raw : isObj(raw) ? pick(raw, ["candles", "rows", "bars", "data"]) : undefined;
  if (!Array.isArray(rows)) return null;
  const meta = isObj(raw) && isObj(raw.meta) ? raw.meta : null;
  const q = isObj(raw) ? (raw.query_ms ?? meta?.query_ms) : undefined;
  const open = b.series.open.slice();
  const high = b.series.high.slice();
  const low = b.series.low.slice();
  const mid = b.series.mid.slice();
  const seen = new Uint8Array(b.n);
  let matched = 0;
  for (const raw1 of rows) {
    const r = toRow(raw1);
    if (!r) continue;
    const i = Math.round((r.t - b.t0) / b.step_s);
    if (i < 0 || i >= b.n || Math.abs(r.t - (b.t0 + i * b.step_s)) > b.step_s / 2 || seen[i]) continue;
    seen[i] = 1;
    matched++;
    open[i] = r.o;
    high[i] = Math.max(r.h, r.o, r.c);
    low[i] = Math.min(r.l, r.o, r.c);
    mid[i] = r.c;
  }
  if (matched < b.n * 0.8) return null;
  return { seq, open, high, low, mid, queryMs: isNum(q) ? q : null };
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
