import { useEffect } from "react";
import { useApp, type Toast } from "../state/app";
import type { Derived } from "../lib/derive";
import { MarketBanner } from "./MarketBanner";

const LIFETIME_MS = 6500;

function ToastItem({ toast }: { toast: Toast }) {
  const drop = useApp((s) => s.dropToast);
  useEffect(() => {
    const id = window.setTimeout(() => drop(toast.id), LIFETIME_MS);
    return () => window.clearTimeout(id);
  }, [toast.id, drop]);
  return (
    <div className={`toast toast-${toast.kind}`} role="status">
      <div className="toast-title">{toast.title}</div>
      <div className="toast-text">{toast.text}</div>
    </div>
  );
}

export function Toasts({ derived }: { derived: Derived }) {
  const toasts = useApp((s) => s.toasts);
  return (
    <div className="toasts" aria-live="polite">
      <MarketBanner derived={derived} />
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </div>
  );
}
