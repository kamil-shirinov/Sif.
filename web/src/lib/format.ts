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
