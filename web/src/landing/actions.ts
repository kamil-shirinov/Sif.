// What the landing's buttons and the presenter keys do to the running app. The canvas, the audio engine and the camera
// stay; only the overlay, the mode and the loaded storm change.

import { useApp, type Mode } from "../state/app";
import { useTimeline } from "../state/timeline";
import { applyBundle, HEADLINE_STORM_ID, openStorm } from "../lib/session";
import { setLandingUrl } from "./route";
import { NVDA_STORM_ID } from "./facts";

const AUTOPLAY_MS = 700;

/** Back to the landing page: the replay rewinds to its calm first minute and waits, paused, in replay mode. */
export function showLanding() {
  const app = useApp.getState();
  if (app.landing) return;
  useTimeline.getState().pause();
  if (app.mode !== "replay") app.setMode("replay");
  if (app.bundle) applyBundle(app.bundle, { autoplayMs: null });
  useApp.getState().setLanding(true);
  document.title = "StormScore";
  setLandingUrl({ storm: null, mode: null });
}

/** Close the overlay over whatever is loaded, paused where it is. */
export function closeLanding() {
  const app = useApp.getState();
  if (!app.landing) return;
  app.setLanding(false);
  if (app.bundle) document.title = `StormScore · ${app.bundle.title}`;
  if (app.baseStormId) setLandingUrl({ storm: app.baseStormId });
}

/** Open a storm in a mode. A storm already loaded restarts from calm water instead of being fetched again. */
export function openFromLanding(id: string, mode: Mode = "replay") {
  const app = useApp.getState();
  app.setLanding(false);
  setLandingUrl({ mode: mode === "survive" ? "survive" : null });
  const file = app.index?.storms.find((s) => s.storm_id === id)?.file;
  const loaded = app.bundle !== null && app.bundle.storm_id === id && app.bundle.source !== "scenario";
  if (app.mode !== mode) {
    useTimeline.getState().pause();
    app.setMode(mode);
    // Rebuild the loaded storm for the new mode now, so the panels never see the old mode's derived data.
    if (app.bundle && !loaded) applyBundle(app.bundle, { autoplayMs: null });
  }
  if (loaded) {
    applyBundle(app.bundle!, { autoplayMs: mode === "replay" ? AUTOPLAY_MS : null });
    setLandingUrl({ storm: id });
    return;
  }
  void openStorm(id, file);
}

/** Survive opens on the headline storm when the index lists it (or nothing says otherwise), else on what is loaded. */
export function openSurvive() {
  const app = useApp.getState();
  const listed = app.index === null || app.index.storms.some((s) => s.storm_id === HEADLINE_STORM_ID);
  openFromLanding(listed ? HEADLINE_STORM_ID : (app.baseStormId ?? app.bundle?.storm_id ?? HEADLINE_STORM_ID), "survive");
}

export const openHeadline = () => openFromLanding(HEADLINE_STORM_ID);
export const openNvda = () => openFromLanding(NVDA_STORM_ID);
