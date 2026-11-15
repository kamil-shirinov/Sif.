import { useState } from "react";
import { useApp } from "../state/app";

const MONTH_RE = /(January|February|March|April|May|June|July|August|September|October|November|December)/i;

const pct = (a: number, b: number) => `${Math.round((a / b) * 100)}%`;

/**
 * Open at first on screens 16:9 or wider. Narrower ones (16:10 laptops) frame the ships wider, and the open card would
 * reach the prepared ship's stern, so it starts as one summary line there; a click opens it.
 */
function startOpen(): boolean {
  try {
    return window.matchMedia("(min-aspect-ratio: 17/10)").matches;
  } catch {
    return true;
  }
}

/**
 * What the detector scored on data it never saw while it was tuned (index.json metrics).
 * Each row appears only when its number exists; the card is hidden when metrics is null.
 */
export function EvidenceCard() {
  const m = useApp((s) => s.index?.metrics ?? null);
  const [open, setOpen] = useState(startOpen);
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
  // Labelled exactly as metrics.json defines them: alert episodes per observed day is the main figure,
  // the per-pair rate sits beside it (docs/metrics.md, section 6).
  const ep = m.false_alarm_episodes_per_day;
  const pair = m.false_alarms_per_day;
  // Two lines at most: the main figure, then the per-pair rate under it. The full definitions are the tooltips.
  const falseRow =
    ep !== null || pair !== null ? (
      <div
        className="evidence-false"
        title="False alarm: a storm alarm outside [onset - 60 min, end + 60 min] of every storm on its pair. Per observed day: 1,440 minutes with a bar on any pair."
      >
        <div className="evidence-row" title={ep !== null ? "distinct alert episodes per observed day" : "pair alarms per observed day"}>
          <span>
            False alarms <small>{ep !== null ? "episodes / day" : "pair alarms / day"}</small>
          </span>
          <span className="num strong">{(ep ?? pair)!.toFixed(2)}</span>
        </div>
        {ep !== null && pair !== null && (
          <div className="evidence-row evidence-sub" title="pair alarms per observed day: each pair's false alarm counts on its own">
            <span>counting each pair on its own</span>
            <span className="num">{pair.toFixed(2)}</span>
          </div>
        )}
      </div>
    ) : null;
  if (rows.length === 0 && !falseRow) return null;

  // "measured on August": the month comes from the backtest's own split label when it names one.
  const month = m.split ? MONTH_RE.exec(m.split)?.[1] : undefined;
  const label = `measured on ${month ?? "August"}, never seen in tuning`;

  return (
    <div className="panel stack-item evidence" title={m.split ?? undefined}>
      <button className="panel-head panel-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span>Evidence</span>
        <span className="evidence-summary">
          {!open && rows[0] && <span className="num">{rows[0].value} alarmed</span>}
          <span className="toggle-chevron" aria-hidden="true">
            {open ? "▴" : "▾"}
          </span>
        </span>
      </button>
      {open && rows.map((r) => (
        <div className="evidence-row" key={r.label} title={r.hint}>
          <span>{r.label}</span>
          <span className="num">{r.value}</span>
        </div>
      ))}
      {open && falseRow}
      {open && <div className="evidence-note">{label}</div>}
    </div>
  );
}
