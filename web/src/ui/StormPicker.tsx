import { useEffect, useRef, useState } from "react";
import type { Bundle, StormIndexEntry } from "../types/bundle";
import { useApp } from "../state/app";
import { DEFAULT_STORM_ID } from "../lib/loadBundle";
import { openStorm } from "../lib/session";

/** Mock entry shown when index.json is missing (and offered beside real storms): the synthetic example. */
const MOCK_ENTRY: StormIndexEntry = {
  storm_id: DEFAULT_STORM_ID,
  title: "Synthetic storm (mock data)",
  symbol: "USDJPY",
  asset_class: "fx",
  kind: "unscheduled",
  move_bp: -247.2,
  file: `${DEFAULT_STORM_ID}.json`,
};

/** "30 July 2026" from "USDJPY, 30 July 2026": the title without its symbol prefix. */
function dateOf(e: StormIndexEntry): string {
  const prefix = `${e.symbol}, `;
  return e.symbol && e.title.startsWith(prefix) ? e.title.slice(prefix.length) : e.title;
}

const fmtMove = (bp: number) => `${bp >= 0 ? "+" : "-"}${(Math.abs(bp) / 100).toFixed(1)}%`;

function Group({ title, rows, current, busy, onPick }: { title: string; rows: StormIndexEntry[]; current: string | null; busy: string | null; onPick: (e: StormIndexEntry) => void }) {
  if (rows.length === 0) return null;
  return (
    <div className="picker-group">
      <div className="picker-group-title">
        {title} <span className="muted">{rows.length}</span>
      </div>
      {rows.map((e) => (
        <button
          key={e.storm_id}
          className={`picker-row ${e.storm_id === current ? "current" : ""}`}
          onClick={() => onPick(e)}
          disabled={busy !== null}
          aria-current={e.storm_id === current ? "true" : undefined}
        >
          <span className="picker-symbol">{e.symbol || "?"}</span>
          <span className="picker-date">{e.storm_id === DEFAULT_STORM_ID ? "synthetic example" : dateOf(e)}</span>
          <span className={`picker-move num ${e.move_bp >= 0 ? "up" : "down"}`}>{fmtMove(e.move_bp)}</span>
          {busy === e.storm_id && <span className="picker-busy">loading…</span>}
        </button>
      ))}
    </div>
  );
}

/** Storms from /bundles/index.json, grouped scheduled vs unscheduled. Choosing one loads it. */
export function StormPicker({ bundle }: { bundle: Bundle }) {
  const index = useApp((s) => s.index);
  const busy = useApp((s) => s.loadingStorm);
  const loadError = useApp((s) => s.loadError);
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const onDown = (e: PointerEvent) => {
      if (root.current && !root.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("pointerdown", onDown);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", onDown);
    };
  }, [open]);

  const storms = index?.storms ?? [];
  const hasMock = storms.some((s) => s.storm_id === DEFAULT_STORM_ID);
  const scheduled = storms.filter((s) => s.kind === "scheduled");
  const unscheduled = storms.filter((s) => s.kind !== "scheduled");
  const synthetic = hasMock ? [] : [MOCK_ENTRY];
  const isScenario = bundle.source === "scenario";
  const current = isScenario ? null : bundle.storm_id;

  const pick = (e: StormIndexEntry) => {
    setOpen(false);
    if (e.storm_id !== current) void openStorm(e.storm_id, e.file);
  };

  return (
    <div className="panel stack-item picker" ref={root}>
      <button className="picker-head" onClick={() => setOpen(!open)} aria-expanded={open} aria-haspopup="listbox">
        <span className="picker-label">Storm</span>
        <span className="picker-current">{bundle.title}</span>
        {isScenario && <span className="badge scenario">scenario</span>}
        <span className="picker-chevron" aria-hidden="true">
          {open ? "▴" : "▾"}
        </span>
      </button>
      {loadError && <div className="picker-error">{loadError}</div>}
      {open && (
        <div className="picker-list" role="listbox">
          <Group title="Scheduled events" rows={scheduled} current={current} busy={busy} onPick={pick} />
          <Group title="Unscheduled storms" rows={unscheduled} current={current} busy={busy} onPick={pick} />
          <Group title="Synthetic example" rows={synthetic} current={current} busy={busy} onPick={pick} />
          {index === null && (
            <div className="picker-note">
              No <code>bundles/index.json</code> yet. Real storms appear here after <code>python -m storm.export --all</code>.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
