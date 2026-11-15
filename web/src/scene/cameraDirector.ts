// Where the camera should be: the landing page's wide shot or the replay's default view, and a flight between them.
// No imports (not even three), so the landing's actions can drive it without pulling the 3D code into the first chunk.
// CameraRig.tsx reads it every frame.

export type CameraView = "landing" | "home";

interface Flight {
  to: CameraView;
  /** performance.now() at take-off, and the length of the flight, ms. */
  start: number;
  duration: number;
  done: () => void;
}

export const cameraDirector: {
  /** The view the camera holds when no flight is under way. */
  view: CameraView;
  flight: Flight | null;
} = { view: "home", flight: null };

/** Flight time between the landing's wide shot and the replay's view. */
export const FLIGHT_MS = 1500;

/** Put the camera on a view at once (page load). */
export function placeCamera(view: CameraView) {
  cameraDirector.flight?.done();
  cameraDirector.flight = null;
  cameraDirector.view = view;
}

/** Fly to a view; resolves when the camera has settled there. A new flight replaces one under way (from where it is). */
export function flyCamera(to: CameraView, duration = FLIGHT_MS): Promise<void> {
  cameraDirector.flight?.done();
  return new Promise((resolve) => {
    let settled = false;
    const done = () => {
      if (settled) return;
      settled = true;
      resolve();
    };
    cameraDirector.view = to;
    cameraDirector.flight = { to, start: performance.now(), duration, done };
    // Without a 3D scene (no WebGL, the scene still loading) nobody flies the camera: settle on time anyway.
    window.setTimeout(done, duration + 400);
  });
}

/**
 * True while the scene's warm-up draw (Warmup.tsx) is still to come after a rebuild: the landing's transition waits for
 * it before the camera moves. Here, in this import-free module, so the landing does not pull in the 3D code.
 */
export const warmupState = { pending: false };

/** Ease in and out (cubic): a gentle take-off, a gentle landing. */
export const easeInOutCubic = (u: number) => (u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2);
