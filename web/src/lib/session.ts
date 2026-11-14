// Loading a storm into the running app: from the URL on start, from the picker, or a navigator scenario.
// The canvas, the audio engine and the camera stay; only the bundle (and what is derived from it) changes.

import type { Bundle, StormIndex } from "../types/bundle";
import { derive } from "./derive";
import { BundleError, DEFAULT_STORM_ID, loadBundle } from "./loadBundle";
import { useApp } from "../state/app";
import { useSurvive } from "../state/survive";
import { useTimeline } from "../state/timeline";

export const COLD_OPEN_MS = 2000;
const PICK_AUTOPLAY_MS = 700;

let autoplayTimer = 0;
let loadToken = 0;

interface ApplyOptions {
  /** Start playing after this many ms; null leaves the replay paused. */
  autoplayMs: number | null;
  /** Start at this frame. */
  at?: number | null;
}

/** Make `b` the running replay. Resets the playhead, toasts and per-bundle scene state. */
export function applyBundle(b: Bundle, opts: ApplyOptions) {
  window.clearTimeout(autoplayTimer);
  const base = derive(b);
  // Survive mode: the loaded storm becomes a fresh setup (leverage slider, no run yet), shown with the player's ship.
  const survive = useApp.getState().mode === "survive";
  const d = survive ? useSurvive.getState().begin(b, base) : base;
  useTimeline.getState().reset(b.n, base.closed);
  useApp.getState().setBundle(b, d);
  if (opts.at !== null && opts.at !== undefined && Number.isFinite(opts.at)) useTimeline.getState().seek(opts.at);
  document.title = `StormScore · ${b.title}`;
  if (opts.autoplayMs !== null && !survive) {
    autoplayTimer = window.setTimeout(() => useTimeline.getState().play(), opts.autoplayMs);
  }
}

/** Keep ?storm= in the address bar so a reload opens the same storm. Other parameters stay. */
function rememberInUrl(stormId: string) {
  try {
    const url = new URL(window.location.href);
    url.searchParams.set("storm", stormId);
    url.searchParams.delete("at");
    window.history.replaceState(null, "", url);
  } catch {
    /* no history API: the storm still loads */
  }
}

/** The headline storm: opened by default when index.json lists it. */
export const HEADLINE_STORM_ID = "usdjpy-2026-07-30";

/** The storm to open when the URL names none: usdjpy-2026-07-30 when listed, else the largest move in index.json, else mock_storm. */
export function defaultStorm(index: StormIndex | null): { id: string; file?: string } {
  if (index && index.storms.length > 0) {
    const headline = index.storms.find((s) => s.storm_id === HEADLINE_STORM_ID);
    if (headline) return { id: headline.storm_id, file: headline.file };
    const biggest = index.storms.reduce((a, b) => (Math.abs(b.move_bp) > Math.abs(a.move_bp) ? b : a));
    return { id: biggest.storm_id, file: biggest.file };
  }
  return { id: DEFAULT_STORM_ID };
}

/** Picker: load a storm into the running app. A failure is shown in the picker and the current replay plays on. */
export async function openStorm(id: string, file?: string): Promise<boolean> {
  const token = ++loadToken;
  const app = useApp.getState();
  app.setLoadingStorm(id);
  app.setLoadError(null);
  try {
    const b = await loadBundle(id, file);
    if (token !== loadToken) return false;
    applyBundle(b, { autoplayMs: PICK_AUTOPLAY_MS });
    useApp.getState().setBaseStormId(b.storm_id);
    rememberInUrl(id);
    return true;
  } catch (e) {
    if (token === loadToken) {
      const why = e instanceof BundleError ? e.message : String(e);
      useApp.getState().setLoadError(`Could not open ${id}: ${why}`);
    }
    return false;
  } finally {
    if (token === loadToken) useApp.getState().setLoadingStorm(null);
  }
}

/** Navigator: sail a what-if scenario bundle in the same scene. The base storm stays what the navigator is asked about. */
export function sailScenario(b: Bundle) {
  ++loadToken; // a picker load still in flight must not replace the scenario
  applyBundle(b, { autoplayMs: PICK_AUTOPLAY_MS });
  useApp.getState().setLoadingStorm(null);
}
