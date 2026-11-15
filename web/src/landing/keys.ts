// Presenter keys. L returns to the landing page from anywhere, 1 opens 30 July, 2 opens Survive, 3 opens NVDA, Esc
// closes the landing overlay. Space (play/pause), C and R (Survive's cut and restore) are left alone.
// Pure: no imports, so landing.test.mjs runs it under Node with a plain EventTarget.

export type PresenterAction = "landing" | "headline" | "survive" | "nvda" | "close";

/** The parts of a KeyboardEvent the keys read. */
export interface KeyLike {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
  repeat?: boolean;
  target?: unknown;
}

/** Typing in a field (the navigator's question, the leverage slider, a select) never triggers a presenter key. */
function inField(target: unknown): boolean {
  if (typeof target !== "object" || target === null) return false;
  const t = target as { tagName?: unknown; isContentEditable?: unknown };
  const tag = typeof t.tagName === "string" ? t.tagName.toUpperCase() : "";
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || t.isContentEditable === true;
}

/** The action a key press asks for, or null. `landingOpen` says whether the landing overlay is showing. */
export function presenterAction(e: KeyLike, landingOpen: boolean): PresenterAction | null {
  if (e.ctrlKey || e.metaKey || e.altKey || e.repeat) return null;
  if (inField(e.target)) return null;
  switch (e.key) {
    case "l":
    case "L":
      return landingOpen ? null : "landing";
    case "1":
      return "headline";
    case "2":
      return "survive";
    case "3":
      return "nvda";
    case "Escape":
      return landingOpen ? "close" : null;
    default:
      return null;
  }
}

/** Listen for presenter keys on `target` (the window). Returns the unbind function. */
export function bindPresenterKeys(target: EventTarget, isLandingOpen: () => boolean, run: (a: PresenterAction) => void): () => void {
  const onKey = (ev: Event) => {
    const e = ev as Event & KeyLike;
    const action = presenterAction(e, isLandingOpen());
    if (action === null) return;
    ev.preventDefault();
    run(action);
  };
  target.addEventListener("keydown", onKey);
  return () => target.removeEventListener("keydown", onKey);
}
