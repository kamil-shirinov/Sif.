export function fmtUsd(v: number, compact = false): string {
  if (compact) {
    const a = Math.abs(v);
    const sign = v < 0 ? "-" : "";
    if (a >= 1e9) return `${sign}$${(a / 1e9).toFixed(1)}B`;
    if (a >= 1e6) return `${sign}$${(a / 1e6).toFixed(1)}M`;
    if (a >= 1e3) return `${sign}$${(a / 1e3).toFixed(0)}k`;
    return `${sign}$${a.toFixed(0)}`;
  }
  return (v < 0 ? "-$" : "$") + Math.round(Math.abs(v)).toLocaleString("en-US");
}

export function fmtPct(v: number, digits = 1): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

export function fmtUtc(epochSec: number, withDate = true): string {
  const d = new Date(epochSec * 1000);
  const p = (x: number) => String(x).padStart(2, "0");
  const time = `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`;
  if (!withDate) return `${time} UTC`;
  return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())} ${time} UTC`;
}

export const STATE_NAMES = ["Calm", "Watch", "Storm"] as const;

/** Name of the scheduled release a watch event announces: `event`, else parsed from "Watch: <name> at HH:MM UTC", else the text. */
export function watchName(w: { event?: string; text: string }): string {
  if (w.event) return w.event;
  const m = /^\s*Watch:\s*(.+?)\s+at\s+\d{1,2}:\d{2}/i.exec(w.text);
  return m ? m[1] : w.text;
}

/** "in 12 min", "in under a minute", "now" for a signed number of minutes until a release. */
export function fmtCountdown(minutes: number): string {
  if (minutes <= 0) return "now";
  if (minutes < 1) return "in under a minute";
  return `in ${Math.ceil(minutes)} min`;
}

/** "12:58" for an epoch time shifted by `offsetS` seconds (the clock of the exchange); the date is left out. */
export function fmtClock(epochSec: number, offsetS = 0): string {
  const d = new Date((epochSec + offsetS) * 1000);
  const p = (x: number) => String(x).padStart(2, "0");
  return `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`;
}
