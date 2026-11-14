import { create } from "zustand";
import { sampleAt, stepAt } from "../lib/derive";

/** Default pace: 1 market minute per 0.25 s of wall time (speed 1). */
export const FRAMES_PER_SECOND_AT_1X = 4;
export const SPEEDS = [0.5, 1, 2, 4, 8, 16] as const;

export interface TimelineState {
  /** Playhead in frames; fractional so the scene can interpolate between frames. */
  t: number;
  n: number;
  playing: boolean;
  speed: number;
  /** Increments on every seek, so the event driver does not fire everything it skipped. */
  seekEpoch: number;
  reset(n: number): void;
  play(): void;
  pause(): void;
  toggle(): void;
  setSpeed(speed: number): void;
  seek(t: number): void;
  /** Advance by dt seconds of wall time. */
  advance(dt: number): void;
}

const clampT = (t: number, n: number) => Math.min(Math.max(t, 0), Math.max(0, n - 1));

export const useTimeline = create<TimelineState>((set, get) => ({
  t: 0,
  n: 1,
  playing: false,
  speed: 1,
  seekEpoch: 0,
  reset: (n) => set({ n, t: 0, playing: false, seekEpoch: get().seekEpoch + 1 }),
  play: () => {
    const { t, n } = get();
    if (t >= n - 1) set({ t: 0, seekEpoch: get().seekEpoch + 1, playing: true });
    else set({ playing: true });
  },
  pause: () => set({ playing: false }),
  toggle: () => (get().playing ? get().pause() : get().play()),
  setSpeed: (speed) => set({ speed }),
  seek: (t) => set({ t: clampT(t, get().n), seekEpoch: get().seekEpoch + 1 }),
  advance: (dt) => {
    const { playing, t, n, speed } = get();
    if (!playing) return;
    const next = t + dt * FRAMES_PER_SECOND_AT_1X * speed;
    if (next >= n - 1) set({ t: n - 1, playing: false });
    else set({ t: next });
  },
}));

// ---- per-frame selectors ----

/** Integer frame index under the playhead. Components using this re-render once per market minute. */
export const selectFrame = (s: TimelineState) => Math.min(s.n - 1, Math.max(0, Math.floor(s.t)));
export const useFrameIndex = () => useTimeline(selectFrame);
export const usePlaying = () => useTimeline((s) => s.playing);

/** Read the playhead without subscribing (for useFrame / rAF loops). */
export const playhead = () => useTimeline.getState().t;

/** Interpolated value of a series at the current playhead. */
export const sampleNow = (arr: ArrayLike<number>) => sampleAt(arr, playhead());
/** Discrete value of a series at the current frame. */
export const stepNow = (arr: ArrayLike<number>) => stepAt(arr, playhead());
