// What the landing's buttons and the presenter keys do to the running app. The canvas, the audio engine and the camera
// stay; only the overlay, the mode and the loaded storm change. Between the landing page and the replay the change is
// one piece of motion (transition.ts), never a cut.

import { useApp, type Mode } from "../state/app";
import { useTimeline } from "../state/timeline";
import { applyBundle, HEADLINE_STORM_ID, openStorm } from "../lib/session";
import { BundleError, isWithheld, loadBundle, WITHHELD_NOTE } from "../lib/loadBundle";
import { setLandingUrl } from "./route";
import { NVDA_STORM_ID } from "./facts";
import { runClosing, runOpening, settleFrames, useTransition } from "./transition";
import { useExplore } from "./explore";

const AUTOPLAY_MS = 700;
/** The rewind on L waits this long: the panels, captions and end card fade first. */
const REWIND_DELAY_MS = 380;
const busy = () => useTransition.getState().phase !== "idle";
let opening = 0; // a newer open (a second key press while a storm loads) wins

/**
 * Back to the landing page: the HUD leaves, the camera flies back to the wide shot while the replay rewinds to its calm
 * first minute, and the text rises in. The replay waits there, paused, in replay mode.
 */
export function showLanding() {
  const app = useApp.getState();
  if (app.landing || busy()) return;
  opening++;
  useTimeline.getState().pause();
  void runClosing(
    () => {
      useApp.getState().setLanding(true);
      useExplore.getState().set(false);
      document.title = "Sif";
      setLandingUrl({ storm: null, mode: null });
    },
    (ms) => {
      // Replay mode: rewind alongside the flight, so the sea calms as the camera pulls back. (Survive's ship is the
      // player's: it is swapped for the two demo ships once the page covers the scene, below.)
      // It starts once the panels, the captions and the end card have faded (the end card goes the moment the playhead
      // leaves the last frame, so it must be invisible by then).
      if (useApp.getState().mode === "replay") {
        const seq = useTransition.getState().seq;
        window.setTimeout(() => {
          if (useTransition.getState().seq === seq) rewind(Math.max(1, ms * 0.92 - REWIND_DELAY_MS));
        }, REWIND_DELAY_MS);
      }
    },
    () => {
      const st = useApp.getState();
      if (st.mode !== "replay") {
        st.setMode("replay");
        if (st.bundle) applyBundle(st.bundle, { autoplayMs: null });
      } else {
        useTimeline.getState().seek(0);
      }
    },
  );
}

/** Run the playhead back to frame 0 over `ms`, eased: the sea, sky and ships calm down as time runs backwards. */
function rewind(ms: number) {
  const tl = useTimeline.getState();
  const from = tl.t;
  if (from <= 0 || ms <= 1) {
    tl.seek(0);
    return;
  }
  const start = performance.now();
  const seq = useTransition.getState().seq;
  const step = (now: number) => {
    if (useTransition.getState().seq !== seq) return;
    const u = Math.min(1, (now - start) / ms);
    const e = u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2;
    useTimeline.getState().seek(from * (1 - e));
    if (u < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/** Close the overlay over whatever is loaded, paused where it is (Esc, "Open the replay"). */
export function closeLanding() {
  const app = useApp.getState();
  if (!app.landing || busy()) return;
  opening++;
  const token = opening;
  useTransition.getState().setPreparing(true);
  void (async () => {
    await settleFrames(3);
    if (token !== opening) return;
    await runOpening(enterReplay, () => {});
  })();
}

function enterReplay() {
  const app = useApp.getState();
  app.setLanding(false);
  if (app.bundle) document.title = `Sif · ${app.bundle.title}`;
  setLandingUrl({ storm: app.baseStormId ?? app.bundle?.storm_id ?? null, mode: app.mode === "survive" ? "survive" : null });
}

/**
 * Open a storm in a mode. From the landing page: the storm and mode are made ready behind the page (fetched if it is
 * not the one loaded), then the page gives way to the replay in one move, and a replay starts playing when the camera
 * settles. A storm already loaded restarts from calm water instead of being fetched again.
 * From the replay itself (1, 2, 3 pressed there) the switch is in place, as before: the camera is already home.
 */
export function openFromLanding(id: string, mode: Mode = "replay") {
  const app = useApp.getState();
  if (busy()) return;
  if (useExplore.getState().open) {
    openFromExplorer(id, mode);
    return;
  }
  if (!app.landing) {
    switchInPlace(id, mode);
    return;
  }
  const token = ++opening;
  useTransition.getState().setPreparing(true);
  void (async () => {
    const changed = await prepare(id, mode);
    if (changed === null) useTransition.getState().setPreparing(false);
    if (token !== opening || changed === null) return;
    // A rebuilt scene (new storm, new mode) is drawn once offscreen first, and the replay's Controls mount under the
    // page: start the flight on steady frames.
    await settleFrames(changed ? 5 : 3);
    if (token !== opening) return;
    await runOpening(enterReplay, () => {
      if (useApp.getState().mode === "replay" && !useApp.getState().landing) useTimeline.getState().play();
    });
  })();
}

/**
 * Behind the landing page: load the storm and set the mode, paused at calm water. Returns whether the scene was rebuilt
 * (so the caller lets it settle), or null when loading failed (the page stays, with the reason in the console and the
 * picker's error line).
 */
async function prepare(id: string, mode: Mode): Promise<boolean | null> {
  const app = useApp.getState();
  if (isWithheld(app.index, id)) {
    // The public build has no bundle for this storm: stay where we are, with the reason on the picker's error line.
    app.setLoadError(`${id}: ${WITHHELD_NOTE}`);
    return null;
  }
  useTimeline.getState().pause();
  const loaded = app.bundle !== null && app.bundle.storm_id === id && app.bundle.source !== "scenario";
  let changed = false;
  if (app.mode !== mode) {
    app.setMode(mode);
    changed = true;
  }
  if (!loaded) {
    try {
      const file = app.index?.storms.find((s) => s.storm_id === id)?.file;
      const b = await loadBundle(id, file);
      applyBundle(b, { autoplayMs: null });
      useApp.getState().setBaseStormId(b.storm_id);
      return true;
    } catch (e) {
      const why = e instanceof BundleError ? e.message : String(e);
      console.warn(`Could not open ${id}: ${why}`);
      useApp.getState().setLoadError(`Could not open ${id}: ${why}`);
      return null;
    }
  }
  if (changed) applyBundle(app.bundle!, { autoplayMs: null });
  else useTimeline.getState().seek(0);
  return changed;
}

/** 1, 2, 3 pressed in the replay: load and switch where the camera is (no landing page to leave). */
function switchInPlace(id: string, mode: Mode) {
  const app = useApp.getState();
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

/**
 * Start (the landing's one button, or Enter): the page gives way exactly as when opening a storm (the text slides
 * away, the camera flies to the replay's view), but the Explorer arrives instead of the HUD. Nothing is loaded:
 * the storm under the page stays, paused at calm water, until one is picked.
 */
export function startExplorer() {
  const app = useApp.getState();
  if (!app.landing || busy()) return;
  const token = ++opening;
  useTransition.getState().setPreparing(false);
  void (async () => {
    await settleFrames(2);
    if (token !== opening) return;
    await runOpening(
      () => {
        useExplore.getState().set(true);
        useApp.getState().setLanding(false);
        document.title = "Sif · Explorer";
        setLandingUrl({ storm: null, mode: null });
      },
      () => {},
    );
  })();
}

/** Back to the Explorer from a replay (E): the HUD gives way to it in place; the replay pauses. */
export function showExplorer() {
  const app = useApp.getState();
  if (app.landing || busy() || useExplore.getState().open) return;
  useTimeline.getState().pause();
  useExplore.getState().set(true);
  document.title = "Sif · Explorer";
}

/**
 * A storm picked in the Explorer: it fades while the storm and mode are made ready under it, then the HUD arrives in
 * sequence (the camera is already on the replay's view) and a replay starts playing.
 */
export function openFromExplorer(id: string, mode: Mode = "replay") {
  if (busy()) return;
  const token = ++opening;
  useExplore.getState().set(true, true);
  useTransition.getState().setPreparing(true);
  void (async () => {
    const changed = await prepare(id, mode);
    if (changed === null) {
      useTransition.getState().setPreparing(false);
      useExplore.getState().set(true, false); // could not load: the Explorer comes back
      return;
    }
    if (token !== opening) return;
    await settleFrames(changed ? 5 : 3);
    if (token !== opening) return;
    await runOpening(
      () => {
        useExplore.getState().set(false);
        enterReplay();
        setLandingUrl({ storm: id, mode: mode === "survive" ? "survive" : null });
      },
      () => {
        if (useApp.getState().mode === "replay" && !useApp.getState().landing) useTimeline.getState().play();
      },
    );
  })();
}

/** Survive opens on the headline storm when the index lists it (or nothing says otherwise), else on what is loaded. */
export function openSurvive() {
  const app = useApp.getState();
  const listed = app.index === null || app.index.storms.some((s) => s.storm_id === HEADLINE_STORM_ID);
  openFromLanding(listed ? HEADLINE_STORM_ID : (app.baseStormId ?? app.bundle?.storm_id ?? HEADLINE_STORM_ID), "survive");
}

export const openHeadline = () => openFromLanding(HEADLINE_STORM_ID);
export const openNvda = () => openFromLanding(NVDA_STORM_ID);
