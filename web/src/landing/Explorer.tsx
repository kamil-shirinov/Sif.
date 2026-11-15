import { useEffect, useMemo, useState } from "react";
import { WITHHELD_NOTE } from "../lib/loadBundle";
import { useApp } from "../state/app";
import { openFromExplorer, showLanding } from "./actions";
import "./explorer.css";

// The Explorer: every dataset we tested, its headline numbers and every storm, from web/public/evidence.json
// (built by scripts/build_evidence.py from the published result files; no number is typed in here).

interface StormRow {
  id: string;
  date: string;
  instrument: string;
  kind: string | null;
  move_bp: number | null;
  alarmed: boolean;
  share_ahead_pct: number | null;
  caught: boolean;
  group: string | null;
  in_sample: boolean;
  bundle: string | null;
}
interface Headline {
  storms: number | null;
  alarmed: number | null;
  caught: number | null;
  median_move_ahead_pct: number | null;
  median_minutes_to_alarm: number | null;
  false_alarm_episodes_per_day: number | null;
  days: number | null;
}
interface Dataset {
  id: string;
  title: string;
  period: string;
  labels: string[];
  note: string;
  headline: Headline;
  headline_note: string | null;
  storms: StormRow[];
}
interface StatsGroup {
  id: string;
  title: string;
  storms: number;
  alarmed: number;
  caught: number;
  alarmed_share: number | null;
  alarmed_share_ci95: number[] | null;
  caught_share: number | null;
  caught_share_ci95: number[] | null;
  random_timing: { caught: number; null_median: number; null_ci95: number[]; p_value: number; holm_p_value: number | null; replicates: number } | null;
}
interface Evidence {
  book: string;
  datasets: Dataset[];
  stats: { note: string; groups: StatsGroup[] };
}

let cache: Promise<Evidence | null> | null = null;
function loadEvidence(): Promise<Evidence | null> {
  cache ??= fetch(`${import.meta.env.BASE_URL}evidence.json`)
    .then((r) => (r.ok ? (r.json() as Promise<Evidence>) : null))
    .catch(() => null);
  return cache;
}

const pct = (x: number | null | undefined, nd = 0) => (x === null || x === undefined ? "—" : `${x.toFixed(nd)}%`);
const share = (x: number | null | undefined) => (x === null || x === undefined ? "—" : `${Math.round(x * 100)}%`);
const ci = (v: number[] | null) => (v && v.length === 2 ? `${Math.round(v[0] * 100)}–${Math.round(v[1] * 100)}%` : "");
const moveText = (bp: number | null) => (bp === null ? "—" : `${bp > 0 ? "+" : "−"}${Math.abs(bp / 100).toFixed(Math.abs(bp) >= 1000 ? 1 : 2)}%`);
const LABEL_TONE: Record<string, string> = {
  "in-sample": "warn",
  "tuning month": "warn",
  partial: "warn",
  "NVDA in-sample": "warn",
  "pre-registered": "ok",
  "test month": "ok",
  "never seen in tuning": "ok",
  "out of sample": "ok",
};

/** The Explorer over the sea: filters, one block per dataset (headline and storm table), then the statistics. */
export function Explorer({ leaving }: { leaving: boolean }) {
  const [ev, setEv] = useState<Evidence | null | undefined>(undefined);
  const [ds, setDs] = useState<string>("all");
  const [inst, setInst] = useState<string>("all");
  const index = useApp((s) => s.index);
  useEffect(() => {
    let live = true;
    void loadEvidence().then((e) => live && setEv(e));
    return () => {
      live = false;
    };
  }, []);
  // A replay can be opened only when its bundle is on this machine (index.json lists it).
  const playable = useMemo(() => new Set((index?.storms ?? []).map((s) => s.storm_id)), [index]);
  // The public build lists these storms without their bundles (market data not redistributed).
  const withheld = useMemo(() => new Set((index?.withheld ?? []).map((s) => s.storm_id)), [index]);
  const instruments = useMemo(() => {
    const set = new Set<string>();
    for (const d of ev?.datasets ?? []) if (ds === "all" || d.id === ds) for (const r of d.storms) set.add(r.instrument);
    return [...set].sort();
  }, [ev, ds]);
  useEffect(() => {
    if (inst !== "all" && !instruments.includes(inst)) setInst("all");
  }, [instruments, inst]);

  return (
    <div className={`ex ${leaving ? "ex-leave" : ""}`} role="dialog" aria-label="Explorer: every dataset we tested">
      <div className="ex-scrim" aria-hidden="true" />
      <div className="ex-sheet">
        <header className="ex-head">
          <div>
            <h1 className="ex-title">Explorer</h1>
            <p className="ex-sub">Every dataset we tested the alarm on. Pick a storm with a replay to sail it, or survive it yourself.</p>
          </div>
          <button className="ex-back" onClick={showLanding} title="Back to the landing page">
            Landing <kbd>L</kbd>
          </button>
        </header>

        {ev === undefined && <p className="ex-quiet">Loading the evidence…</p>}
        {ev === null && <p className="ex-quiet">evidence.json is missing: run scripts/build_evidence.py.</p>}
        {ev && (
          <>
            <div className="ex-filters" role="group" aria-label="Filters">
              <div className="ex-chips" role="tablist" aria-label="Dataset">
                <button className={ds === "all" ? "on" : ""} onClick={() => setDs("all")}>
                  All datasets
                </button>
                {ev.datasets.map((d) => (
                  <button key={d.id} className={ds === d.id ? "on" : ""} onClick={() => setDs(d.id)}>
                    {d.title}
                  </button>
                ))}
              </div>
              <label className="ex-select">
                Instrument
                <select value={inst} onChange={(e) => setInst(e.target.value)}>
                  <option value="all">All</option>
                  {instruments.map((i) => (
                    <option key={i} value={i}>
                      {i}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p className="ex-book">{ev.book}</p>

            {ev.datasets
              .filter((d) => ds === "all" || d.id === ds)
              .map((d) => (
                <DatasetBlock key={d.id} d={d} inst={inst} playable={playable} withheld={withheld} />
              ))}

            {ds === "all" && inst === "all" && <StatsBlock stats={ev.stats} />}
          </>
        )}
      </div>
    </div>
  );
}

function DatasetBlock({ d, inst, playable, withheld }: { d: Dataset; inst: string; playable: Set<string>; withheld: Set<string> }) {
  const rows = d.storms.filter((r) => inst === "all" || r.instrument === inst);
  if (rows.length === 0) return null;
  const h = d.headline;
  return (
    <section className="ex-ds">
      <div className="ex-ds-head">
        <h2>{d.title}</h2>
        <span className="ex-period">{d.period}</span>
        {d.labels.map((l) => (
          <span key={l} className={`ex-label ${LABEL_TONE[l] ?? ""}`}>
            {l}
          </span>
        ))}
      </div>
      <p className="ex-note">{d.note}</p>
      <div className="ex-figs">
        <Fig n={h.alarmed !== null && h.storms !== null ? `${h.alarmed} of ${h.storms}` : "—"} label="storms alarmed" />
        <Fig n={h.caught !== null && h.storms !== null ? `${h.caught} of ${h.storms}` : "—"} label="caught (half the move still ahead)" />
        <Fig n={pct(h.median_move_ahead_pct)} label="median share of the move ahead" />
        {h.false_alarm_episodes_per_day !== null && <Fig n={h.false_alarm_episodes_per_day.toFixed(2)} label="false alert episodes a day" />}
      </div>
      {d.headline_note && <p className="ex-quiet small">{d.headline_note}</p>}
      <div className="ex-table-wrap">
        <table className="ex-table">
          <thead>
            <tr>
              <th>Date (UTC)</th>
              <th>Instrument</th>
              <th className="num">Move</th>
              <th>Alarmed</th>
              <th className="num">Ahead</th>
              <th>Result</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const canPlay = r.bundle !== null && playable.has(r.id);
              return (
                <tr key={`${d.id}-${r.id}`}>
                  <td className="mono">
                    {r.date}
                    {r.group && <span className="ex-group">{r.group}</span>}
                  </td>
                  <td>
                    {r.instrument}
                    {r.in_sample && d.id !== "sgx-july" && <span className="ex-label warn tiny">in-sample</span>}
                  </td>
                  <td className={`num mono ${r.move_bp !== null && r.move_bp < 0 ? "down" : "up"}`}>{moveText(r.move_bp)}</td>
                  <td>{r.alarmed ? "yes" : <span className="dim">no</span>}</td>
                  <td className="num mono">{pct(r.share_ahead_pct)}</td>
                  <td>
                    <span className={`ex-res ${r.caught ? "caught" : "missed"}`}>{r.caught ? "caught" : "missed"}</span>
                  </td>
                  <td className="ex-actions">
                    {canPlay ? (
                      <>
                        <button className="ex-btn primary" onClick={() => openFromExplorer(r.id, "replay")}>
                          Replay
                        </button>
                        <button className="ex-btn" onClick={() => openFromExplorer(r.id, "survive")}>
                          Survive this storm
                        </button>
                      </>
                    ) : withheld.has(r.id) ? (
                      <span className="dim">{WITHHELD_NOTE}</span>
                    ) : (
                      <span className="dim">results only</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Fig({ n, label }: { n: string; label: string }) {
  return (
    <div className="ex-fig">
      <span className="ex-fig-n">{n}</span>
      <span className="ex-fig-l">{label}</span>
    </div>
  );
}

function StatsBlock({ stats }: { stats: Evidence["stats"] }) {
  return (
    <section className="ex-ds">
      <div className="ex-ds-head">
        <h2>Across all of them</h2>
        <span className="ex-label ok">statistics</span>
      </div>
      <p className="ex-note">{stats.note}</p>
      <div className="ex-table-wrap">
        <table className="ex-table">
          <thead>
            <tr>
              <th>Group</th>
              <th className="num">Storms</th>
              <th className="num">Alarmed (95% interval)</th>
              <th className="num">Caught (95% interval)</th>
              <th className="num">Caught by random timing</th>
              <th className="num">p</th>
            </tr>
          </thead>
          <tbody>
            {stats.groups.map((g) => (
              <tr key={g.id}>
                <td>{g.title}</td>
                <td className="num mono">{g.storms}</td>
                <td className="num mono">
                  {share(g.alarmed_share)} <span className="dim">{ci(g.alarmed_share_ci95)}</span>
                </td>
                <td className="num mono">
                  {share(g.caught_share)} <span className="dim">{ci(g.caught_share_ci95)}</span>
                </td>
                <td className="num mono">
                  {g.random_timing ? (
                    <>
                      {g.random_timing.null_median} <span className="dim">(vs {g.random_timing.caught})</span>
                    </>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="num mono">{g.random_timing ? g.random_timing.p_value.toFixed(4) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
