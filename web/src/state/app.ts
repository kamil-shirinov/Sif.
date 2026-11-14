import { create } from "zustand";
import type { Bundle, BundleEventType, StormIndex } from "../types/bundle";
import type { Derived } from "../lib/derive";

export interface Toast {
  id: number;
  kind: BundleEventType | "cut";
  title: string;
  text: string;
}

/** What GET /api/health reported. Null in the store means no server (or it did not answer ok). */
export interface Health {
  tiger: boolean;
  navigator: boolean;
}

/** The chart's candles as fetched from GET /api/candles, laid onto the bundle's frames. */
export interface LiveCandles {
  /** bundleSeq of the bundle they were fetched for. */
  seq: number;
  open: number[];
  high: number[];
  low: number[];
  mid: number[];
  /** Server-reported query time in ms, when it reported one. */
  queryMs: number | null;
}

export type LiveStatus = "idle" | "loading" | "ok" | "failed";

export interface AppState {
  bundle: Bundle | null;
  derived: Derived | null;
  /** Increments on every loaded bundle (a new storm, a scenario). */
  bundleSeq: number;
  error: string | null;
  lowQuality: boolean;
  soundOn: boolean;
  audioStarted: boolean;
  webglOk: boolean;
  toasts: Toast[];
  /** index.json: null while loading or when it is missing. */
  index: StormIndex | null;
  /** The storm the picker is loading, if any. */
  loadingStorm: string | null;
  /** A failed picker load (not fatal: the current replay keeps playing). */
  loadError: string | null;
  /** The last storm loaded from a file; the navigator is asked about this one even while a scenario sails. */
  baseStormId: string | null;
  health: Health | null;
  live: LiveCandles | null;
  liveStatus: LiveStatus;
  setBundle(b: Bundle, d: Derived): void;
  setError(e: string): void;
  setLowQuality(v: boolean): void;
  setSoundOn(v: boolean): void;
  setAudioStarted(): void;
  setWebglOk(v: boolean): void;
  setIndex(i: StormIndex | null): void;
  setLoadingStorm(id: string | null): void;
  setLoadError(e: string | null): void;
  setBaseStormId(id: string | null): void;
  setHealth(h: Health | null): void;
  setLive(live: LiveCandles | null, status: LiveStatus): void;
  pushToast(t: Omit<Toast, "id">): void;
  dropToast(id: number): void;
  clearToasts(): void;
}

let toastId = 1;

function initialLowQuality(): boolean {
  try {
    const q = new URLSearchParams(window.location.search).get("quality");
    if (q === "low") return true;
    if (q === "high") return false;
    return window.localStorage.getItem("stormscore.lowQuality") === "1";
  } catch {
    return false;
  }
}

export const useApp = create<AppState>((set, get) => ({
  bundle: null,
  derived: null,
  bundleSeq: 0,
  error: null,
  lowQuality: initialLowQuality(),
  soundOn: true,
  audioStarted: false,
  webglOk: true,
  toasts: [],
  index: null,
  loadingStorm: null,
  loadError: null,
  baseStormId: null,
  health: null,
  live: null,
  liveStatus: "idle",
  setBundle: (bundle, derived) =>
    set({ bundle, derived, error: null, bundleSeq: get().bundleSeq + 1, toasts: [], live: null, liveStatus: "idle", loadError: null }),
  setError: (error) => set({ error }),
  setLowQuality: (lowQuality) => {
    try {
      window.localStorage.setItem("stormscore.lowQuality", lowQuality ? "1" : "0");
    } catch {
      /* storage unavailable */
    }
    set({ lowQuality });
  },
  setSoundOn: (soundOn) => set({ soundOn }),
  setAudioStarted: () => set({ audioStarted: true }),
  setWebglOk: (webglOk) => set({ webglOk }),
  setIndex: (index) => set({ index }),
  setLoadingStorm: (loadingStorm) => set({ loadingStorm }),
  setLoadError: (loadError) => set({ loadError }),
  setBaseStormId: (baseStormId) => set({ baseStormId }),
  setHealth: (health) => set({ health }),
  setLive: (live, liveStatus) => set({ live, liveStatus }),
  pushToast: (t) => {
    const toast: Toast = { ...t, id: toastId++ };
    set({ toasts: [...get().toasts.slice(-3), toast] });
  },
  dropToast: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),
  clearToasts: () => set({ toasts: [] }),
}));
