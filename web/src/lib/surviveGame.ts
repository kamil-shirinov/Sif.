// Survive mode, the game's rules in motion: switching mode, sailing, the Cut and Restore buttons, the margin call,
// the end of the run. The pure numbers live in survive.ts; this file moves the stores, the replay and the sound.

import { useEffect } from "react";
import type { AudioEngine } from "../audio/engine";
import { useApp, type Mode } from "../state/app";
import { recordScore, saveBest, useSurvive } from "../state/survive";
import { useTimeline } from "../state/timeline";
import { emitSceneEvent } from "./bus";
import { reopenFrame, SINK_FRAMES } from "./derive";
import { fmtClock, fmtPct, fmtUsd } from "./format";
import { applyBundle } from "./session";
import { CUT_FRACTION, summarize } from "./survive";

let audio: AudioEngine | null = null;
/** The page's one audio engine (App.tsx), so the game can play its cues. */
export function bindSurviveAudio(engine: AudioEngine) {
  audio = engine;
}

const PICK_AUTOPLAY_MS = 700;

/** Replay | Survive. Either way the loaded storm restarts from calm water, paused (Survive) or auto-playing (Replay). */
export function setMode(mode: Mode) {
  const app = useApp.getState();
  if (app.mode === mode || !app.bundle) return;
  useTimeline.getState().pause();
  useApp.getState().setMode(mode);
  applyBundle(app.bundle, { autoplayMs: mode === "replay" ? PICK_AUTOPLAY_MS : null });
}

/** The leverage slider (setup only): the player's ship is rebuilt with the new cargo and margin-call line. */
export function chooseLeverage(leverage: number) {
  const { bundle } = useApp.getState();
  if (!bundle) return;
  const d = useSurvive.getState().setLeverage(bundle, leverage);
  if (d) useApp.getState().setDerived(d);
}

/** Sail: the replay starts from the first minute with the player's ship. */
export function sail() {
  const app = useApp.getState();
  const sv = useSurvive.getState();
  if (!app.bundle || !app.derived || sv.phase !== "setup" || sv.line === null) return;
  sv.sail();
  app.clearToasts();
  useTimeline.getState().reset(app.bundle.n, app.derived.closed);
  useTimeline.getState().play();
  app.pushToast({
    kind: "sail",
    title: "Anchors aweigh!",
    text: `${sv.line.leverage}x: ${fmtUsd(sv.line.notional, true)} of cargo on a ${fmtUsd(sv.sim?.startEquity ?? 0, true)} ship. Cut or restore the cargo when the sea turns.`,
  });
}

/** Back to the setup for the same storm, to try again with another leverage. */
export function tryAgain() {
  const { bundle } = useApp.getState();
  if (!bundle) return;
  useTimeline.getState().pause();
  applyBundle(bundle, { autoplayMs: null });
}

/** Where the player is: the frame the HUD shows, and whether the player may trade now. */
export interface TradeState {
  sailing: boolean;
  frame: number;
  /** Why the buttons are off, in words; null when trading is possible. */
  blocked: string | null;
  canCut: boolean;
  canRestore: boolean;
}

export function tradeState(frame: number): TradeState {
  const app = useApp.getState();
  const sv = useSurvive.getState();
  const off = (blocked: string | null): TradeState => ({ sailing: false, frame, blocked, canCut: false, canRestore: false });
  if (!app.bundle || !app.derived || sv.phase !== "sailing" || !sv.sim) return off(null);
  const f = Math.min(app.bundle.n - 1, Math.max(0, frame));
  const sim = sv.sim;
  if (sim.marginCallI !== null && f >= sim.marginCallI) return { sailing: true, frame: f, blocked: "The ship is sunk.", canCut: false, canRestore: false };
  if (app.derived.closed && app.derived.closed[f] === 1) {
    const r = reopenFrame(app.derived, f);
    const when = r !== null ? ` until ${fmtClock(app.derived.times[r])} UTC` : "";
    return { sailing: true, frame: f, blocked: `The market is closed: no trading${when}.`, canCut: false, canRestore: false };
  }
  return { sailing: true, frame: f, blocked: null, canCut: sim.held[f] === 1, canRestore: sim.restorable[f] === 1 };
}

function press(kind: "cut" | "restore"): boolean {
  const app = useApp.getState();
  const tl = useTimeline.getState();
  const frame = Math.min(tl.n - 1, Math.floor(tl.t));
  const st = tradeState(frame);
  if (!st.sailing || !app.bundle) return false;
  if (st.blocked !== null) {
    app.pushToast({ kind: "market", title: kind === "cut" ? "Cannot cut" : "Cannot restore", text: st.blocked });
    return false;
  }
  if (kind === "restore" && !st.canRestore) {
    const sim = useSurvive.getState().sim;
    if (sim && sim.held[frame] === 1) return false; // nothing was thrown overboard
    app.pushToast({ kind: "market", title: "Cannot restore yet", text: "Taking the cargo back aboard would leave you under the margin line. Wait for the sea to ease." });
    return false;
  }
  if (kind === "cut" && !st.canCut) return false;
  // One order per minute: it fills at the next open, so a second press on the same bar would change nothing.
  if (useSurvive.getState().actions.some((x) => x.i === frame)) return false;
  const d = useSurvive.getState().addAction(app.bundle, { i: frame, at: tl.t, kind });
  if (!d) return false;
  app.setDerived(d);
  // The order fills at the next traded bar's open (side-correct), as the backend executes: its price is not known yet.
  const next = frame + 1 < d.n ? fmtClock(d.times[frame + 1]) : null;
  const when = next !== null ? `at the ${next} UTC open` : "never: the replay ends here";
  if (kind === "cut") {
    audio?.trigger({ type: "cut" });
    emitSceneEvent({ type: "cut", frame });
    app.pushToast({ kind: "cut", title: "Cut ordered", text: `${Math.round(CUT_FRACTION * 100)}% of the cargo goes overboard ${when}, at the bid or ask.` });
  } else {
    emitSceneEvent({ type: "restore", frame });
    app.pushToast({ kind: "restore", title: "Restore ordered", text: `The cargo comes back aboard ${when}, unless that would put you under the margin line.` });
  }
  return true;
}

export const cut = () => press("cut");
export const restore = () => press("restore");

function announceSunk(frame: number) {
  const app = useApp.getState();
  const sv = useSurvive.getState();
  if (!app.bundle || !sv.sim) return;
  sv.markSunk();
  useTimeline.getState().setSpeed(1); // the sinking is meant to be seen
  audio?.trigger({ type: "margin_call" });
  emitSceneEvent({ type: "margin_call", frame });
  const left = sv.sim.equity[frame];
  app.pushToast({
    kind: "sunk",
    title: "Margin call: she is going down!",
    text: `Your margin ran out. The broker closes the position and you keep ${fmtUsd(Math.max(0, left))}.`,
  });
}

function finishRun() {
  const app = useApp.getState();
  const sv = useSurvive.getState();
  if (!app.bundle || !sv.sim || sv.phase !== "sailing") return;
  const b = app.bundle;
  const result = summarize(b, sv.sim);
  let best = sv.best;
  let rank: number | null = null;
  if (!result.scenario) {
    // What-if runs are practice: they do not go in the table.
    const r = recordScore(best, { storm_id: b.storm_id, title: b.title, leverage: result.leverage, score: result.score, sunk: result.sunk, at: new Date().toISOString() });
    best = r.all;
    rank = r.rank;
    saveBest(best);
  }
  // Phase first: pausing notifies the timeline subscriber below, which must already see the run as over.
  sv.finish(result, rank, best);
  useTimeline.getState().pause();
  if (!result.sunk) {
    audio?.trigger({ type: "all_clear" });
    app.pushToast({
      kind: "land",
      title: "Land ho! You made it through the storm",
      text: `Your ship comes into harbour with ${fmtUsd(result.score)} (${fmtPct(result.changePct)}).`,
    });
  }
}

/**
 * Watches the playhead while a run is on: announces the margin call when the playhead reaches it, lets the ship go
 * under, and ends the run when it has sunk or the storm has passed.
 */
export function useSurviveDriver() {
  useEffect(
    () =>
      useTimeline.subscribe((tl) => {
        const sv = useSurvive.getState();
        if (sv.phase !== "sailing" || !sv.sim) return;
        const frame = Math.min(tl.n - 1, Math.floor(tl.t));
        const mc = sv.sim.marginCallI;
        if (mc !== null && frame >= mc) {
          if (!sv.sunkAnnounced) announceSunk(mc);
          // The ship is under: show the card once the sinking is done (or the replay has ended).
          if (tl.t >= mc + SINK_FRAMES + 8 || (!tl.playing && tl.t >= tl.n - 1)) finishRun();
          return;
        }
        if (!tl.playing && tl.t >= tl.n - 1) finishRun();
      }),
    [],
  );

  // C cuts, R restores.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.repeat) return;
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement || e.target instanceof HTMLTextAreaElement) return;
      if (useSurvive.getState().phase !== "sailing" || useApp.getState().mode !== "survive") return;
      if (e.key === "c" || e.key === "C") cut();
      else if (e.key === "r" || e.key === "R") restore();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
