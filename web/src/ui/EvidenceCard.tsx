import { useApp } from "../state/app";

const MONTH_RE = /(January|February|March|April|May|June|July|August|September|October|November|December)/i;

const pct = (a: number, b: number) => `${Math.round((a / b) * 100)}%`;

/**
 * What the detector scored on data it never saw while it was tuned (index.json metrics).
 * Each row appears only when its number exists; the card is hidden when metrics is null.
 */
export function EvidenceCard() {
  const m = useApp((s) => s.index?.metrics ?? null);
  if (!m) return null;

  const rows: { label: string; value: string; hint?: string }[] = [];
  if (m.alarmed !== null) rows.push({ label: "Storms alarmed", value: m.storms !== null ? `${m.alarmed} of ${m.storms}` : String(m.alarmed) });
  if (m.caught !== null && m.storms !== null && m.storms > 0) {
    rows.push({
      label: "Half the move ahead",
      value: `${m.caught} of ${m.storms} (${pct(m.caught, m.storms)})`,
      hint: "Storms alarmed while at least half of the move was still ahead",
    });
  }
  if (m.median_minutes_to_alarm !== null) {
    const v = m.median_minutes_to_alarm;
    rows.push({
      label: "Median time to alarm",
      value: `${Math.abs(v).toFixed(1)} min`,
      hint: v >= 0 ? "Minutes after the storm began" : "Minutes before the storm began",
    });
  }
  if (m.false_alarms_per_day !== null) rows.push({ label: "False alarms per day", value: m.false_alarms_per_day.toFixed(2) });
  if (rows.length === 0) return null;

  // "measured on August": the month comes from the backtest's own split label when it names one.
  const month = m.split ? MONTH_RE.exec(m.split)?.[1] : undefined;
  const label = `measured on ${month ?? "August"}, never seen in tuning`;

  return (
    <div className="panel stack-item evidence" title={m.split ?? undefined}>
      <div className="panel-head">
        <span>Evidence</span>
      </div>
      {rows.map((r) => (
        <div className="evidence-row" key={r.label} title={r.hint}>
          <span>{r.label}</span>
          <span className="num">{r.value}</span>
        </div>
      ))}
      <div className="evidence-note">{label}</div>
    </div>
  );
}
