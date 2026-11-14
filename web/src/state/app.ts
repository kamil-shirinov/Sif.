import { create } from "zustand";
import type { Bundle, BundleEventType } from "../types/bundle";
import type { Derived } from "../lib/derive";

export interface Toast {
  id: number;
  kind: BundleEventType | "cut";
  title: string;
  text: string;
}

export interface AppState {
  bundle: Bundle | null;
  derived: Derived | null;
  error: string | null;
  lowQuality: boolean;
  soundOn: boolean;
  audioStarted: boolean;
  webglOk: boolean;
  toasts: Toast[];
  setBundle(b: Bundle, d: Derived): void;
  setError(e: string): void;
  setLowQuality(v: boolean): void;
  setSoundOn(v: boolean): void;
  setAudioStarted(): void;
  setWebglOk(v: boolean): void;
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
  error: null,
  lowQuality: initialLowQuality(),
  soundOn: true,
  audioStarted: false,
  webglOk: true,
  toasts: [],
  setBundle: (bundle, derived) => set({ bundle, derived, error: null }),
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
  pushToast: (t) => {
    const toast: Toast = { ...t, id: toastId++ };
    set({ toasts: [...get().toasts.slice(-3), toast] });
  },
  dropToast: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),
  clearToasts: () => set({ toasts: [] }),
}));
