// The move between the landing page and the replay, as one piece of motion instead of a cut.
//
// Opening (a landing button, 1, 2, 3, Esc): the storm and mode are made ready behind the page first (a new storm is
// fetched, a mode switch rebuilds the ships), then, in one go: the text fades and slides away to the left, the scrim
// lifts, the camera flies from the landing's wide shot to the replay's view (1.5 s, eased), the HUD panels arrive one
// after another, and the replay starts playing when the camera settles.
// Closing (L) runs it backwards: the panels leave, the camera flies back while the replay rewinds to its calm first
// minute, and the text rises in again.
//
// App.tsx renders the landing while `landing || phase === "opening"` and the HUD while `!landing || phase === "closing"`,
// and adds the classes in transition.css from `phase`.

import { create } from "zustand";
import { flyCamera, FLIGHT_MS, warmupState } from "../scene/cameraDirector";

export type TransitionPhase = "idle" | "opening" | "closing";

interface TransitionState {
  phase: TransitionPhase;
  /**
   * An opening is being made ready behind the page (a storm loading, the scene settling). App.tsx mounts the replay's
   * Controls then, still hidden, so its mount (the timeline, the captions' layer) is not paid at take-off.
   */
  preparing: boolean;
  setPreparing(v: boolean): void;
  /** Increments with every transition, so a stale one (a key pressed again mid-flight) cannot finish a newer one. */
  seq: number;
  set(phase: TransitionPhase): number;
}

export const useTransition = create<TransitionState>((set, get) => ({
  phase: "idle",
  seq: 0,
  preparing: false,
  setPreparing: (preparing) => set({ preparing }),
  set: (phase) => {
    const seq = get().seq + 1;
    set({ phase, seq });
    return seq;
  },
}));

/** Reduced motion: everything still happens, without the flight (a short fade instead). */
export const reducedMotion = () => {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
};

const nextFrame = () => new Promise<void>((r) => requestAnimationFrame(() => r()));

/**
 * Let the scene settle after a change behind the page (a new storm or mode remounts the ships, and the warm-up draws
 * the new scene once offscreen): the flight then starts on a steady frame rate instead of with a long frame.
 */
export async function settleFrames(n = 4) {
  for (let i = 0; i < n; i++) await nextFrame();
  // The scene's warm-up draw (scene/Warmup.tsx) may come a few frames after React has committed the new scene: wait
  // for it, so its long frame lands while the page still stands, not in the flight. Never more than 1.5 s.
  const until = performance.now() + 1500;
  while (warmupState.pending && performance.now() < until) await nextFrame();
  await nextFrame();
}

/**
 * Run the opening move. `ready` has already been awaited by the caller. `onSettled` runs when the camera has landed
 * (the replay starts playing there). Returns false when a newer transition took over.
 */
export async function runOpening(enterReplay: () => void, onSettled: () => void): Promise<boolean> {
  const seq = useTransition.getState().set("opening");
  useTransition.getState().setPreparing(false);
  enterReplay(); // landing false: the HUD mounts (arriving), the page stays mounted (leaving) while phase is opening
  await flyCamera("home", reducedMotion() ? 1 : FLIGHT_MS);
  if (useTransition.getState().seq !== seq) return false;
  useTransition.getState().set("idle");
  onSettled();
  return true;
}

/**
 * Run the closing move. `during` gets the flight's length (to rewind the replay alongside it); `onArrived` runs when the
 * camera is back on the wide shot and the HUD has gone (a mode switch back to replay happens there, under the page).
 */
export async function runClosing(enterLanding: () => void, during: (ms: number) => void, onArrived: () => void): Promise<boolean> {
  const seq = useTransition.getState().set("closing");
  enterLanding();
  const ms = reducedMotion() ? 1 : FLIGHT_MS;
  during(ms);
  await flyCamera("landing", ms);
  if (useTransition.getState().seq !== seq) return false;
  useTransition.getState().set("idle");
  onArrived();
  return true;
}
