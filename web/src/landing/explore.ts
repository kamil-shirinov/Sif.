// The Explorer: the screen Start opens, listing every dataset we tested. Open or closed, and fading out.
import { create } from "zustand";

interface ExploreState {
  /** The Explorer is showing over the sea (the HUD is hidden under it). */
  open: boolean;
  /** It is fading out (a storm was picked; the HUD arrives next). */
  leaving: boolean;
  set(open: boolean, leaving?: boolean): void;
}

export const useExplore = create<ExploreState>((set) => ({
  open: false,
  leaving: false,
  set: (open, leaving = false) => set({ open, leaving }),
}));
