import { useEffect } from "react";
import { useApp, type Toast } from "../state/app";
import type { Derived } from "../lib/derive";
import { useFrameIndex } from "../state/timeline";
import { MarketBanner } from "./MarketBanner";

const LIFETIME_MS = 6500;
const TICK_MS = 250;

/**
 * One toast. The newest shows its title and text; an older one still on screen shrinks to its title, so two toasts
 * stay above the ships' labels at the default camera (the full text is the tooltip).
 */
function ToastItem({ toast, compact }: { toast: Toast; compact: boolean }) {
  const drop = useApp((s) => s.dropToast);
  useEffect(() => {
    const id = window.setTimeout(() => drop(toast.id), LIFETIME_MS);
    return () => window.clearTimeout(id);
  }, [toast.id, drop]);
  return (
    <div className={`toast toast-${toast.kind}${compact ? " compact" : ""}`} role="status" title={`${toast.title}: ${toast.text}`}>
      <div className="toast-title">{toast.title}</div>
      {!compact && <div className="toast-text">{toast.text}</div>}
    </div>
  );
}

/** Event toasts, top centre: at most two (one while the market-closed banner shows), throttled by ui/toastQueue.ts. */
export function Toasts({ derived }: { derived: Derived }) {
  const toasts = useApp((s) => s.toasts);
  const waiting = useApp((s) => s.toastQ.queue.length > 0);
  const tick = useApp((s) => s.tickToasts);
  const i = useFrameIndex();
  const bannerUp = derived.closed !== null && derived.closed[i] === 1;

  // While toasts wait, promote them as their turn comes (a slot frees, or the oldest has been up long enough).
  useEffect(() => {
    if (!waiting) return;
    const id = window.setInterval(tick, TICK_MS);
    return () => window.clearInterval(id);
  }, [waiting, tick]);

  const shown = bannerUp ? toasts.slice(-1) : toasts;
  return (
    <div className="toasts" aria-live="polite">
      <MarketBanner derived={derived} />
      {shown.map((t, k) => (
        <ToastItem key={t.id} toast={t} compact={k < shown.length - 1} />
      ))}
    </div>
  );
}
