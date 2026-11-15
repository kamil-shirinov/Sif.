import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import type { Bundle, StormIndexEntry } from "../../types/bundle";
import { DEFAULT_STORM_ID } from "../../lib/loadBundle";
import { HEADLINE_STORM_ID, openStorm } from "../../lib/session";
import { useApp } from "../../state/app";
import { DIFFICULTY_NAMES, groupByDifficulty, rate, type Rating } from "./difficulty";
import { factsFor, rememberBundle, requestFacts, useFactsVersion } from "./stormFacts";

const dateOf = (e: StormIndexEntry) => {
  const prefix = `${e.symbol}, `;
  return e.symbol && e.title.startsWith(prefix) ? e.title.slice(prefix.length) : e.title;
};

interface Row {
  entry: StormIndexEntry;
  rating: Rating;
}

/** The mock bundle as a list entry, when index.json does not list it (or there is no index.json). */
function mockEntry(b: Bundle): StormIndexEntry {
  const own = b.storm_id === DEFAULT_STORM_ID;
  return {
    storm_id: DEFAULT_STORM_ID,
    title: "Synthetic example",
    symbol: own ? b.symbol : "",
    asset_class: own ? b.asset_class : "fx",
    kind: own ? b.storm.kind : "unscheduled",
    move_bp: own ? b.storm.move_bp : 0,
    file: `${DEFAULT_STORM_ID}.json`,
  };
}

/** Survive's storm choice: every storm in index.json, grouped Easy, Medium, Hard, with one plain sentence each. */
export function StormList({ bundle }: { bundle: Bundle }) {
  const index = useApp((s) => s.index);
  const busy = useApp((s) => s.loadingStorm);
  const loadError = useApp((s) => s.loadError);
  useFactsVersion();
  rememberBundle(bundle);

  const entries = useMemo(() => {
    const storms = index?.storms ?? [];
    return storms.some((s) => s.storm_id === DEFAULT_STORM_ID) ? storms : [...storms, mockEntry(bundle)];
  }, [index, bundle]);

  useEffect(() => requestFacts(entries), [entries]);

  const rows: Row[] = entries.map((entry) => ({ entry, rating: rate(factsFor(entry)) }));
  const groups = groupByDifficulty(rows);
  const order = groups.map((g) => g.level + ":" + g.rows.map((r) => r.entry.storm_id).join(",")).join("|");
  const current = bundle.source === "scenario" ? null : bundle.storm_id;

  // Keep the chosen storm in view inside the list (not the page) when the list opens or the choice changes.
  const listRef = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const list = listRef.current;
    const el = list?.querySelector<HTMLElement>(".storm-row.on");
    if (!list || !el) return;
    const top = el.getBoundingClientRect().top - list.getBoundingClientRect().top + list.scrollTop;
    if (top < list.scrollTop || top + el.offsetHeight > list.scrollTop + list.clientHeight) list.scrollTop = Math.max(0, top - 22);
  }, [current, order]);

  return (
    <div className="survive-field">
      <span className="survive-label">
        <span>Choose your storm</span>
        <span className="muted storm-count">{rows.length}</span>
      </span>
      {bundle.source === "scenario" && <p className="survive-note">Sailing a what-if: {bundle.title}. Pick a storm below to go back to real data.</p>}
      <div className="storm-list" ref={listRef} role="list">
        {groups.map((g) => (
          <div key={g.level} role="presentation">
            <div className={`storm-level lvl-${g.level}`}>{DIFFICULTY_NAMES[g.level]}</div>
            {g.rows.map(({ entry, rating }) => {
              const on = entry.storm_id === current;
              const loading = busy === entry.storm_id;
              const synthetic = entry.storm_id === DEFAULT_STORM_ID;
              return (
                <button
                  key={entry.storm_id}
                  role="listitem"
                  className={`storm-row${on ? " on" : ""}`}
                  aria-current={on || undefined}
                  disabled={busy !== null}
                  onClick={() => {
                    if (!on) void openStorm(entry.storm_id, entry.file);
                  }}
                >
                  <span className="storm-row-top">
                    <span className={`diff-chip lvl-${rating.level}`}>{DIFFICULTY_NAMES[rating.level]}</span>
                    <b>{synthetic ? "Practice" : entry.symbol || "?"}</b>
                    <span className="muted">{synthetic ? "synthetic prices" : dateOf(entry)}</span>
                    {entry.storm_id === HEADLINE_STORM_ID && <span className="storm-tag">headline</span>}
                    {entry.kind === "scheduled" && <span className="storm-tag sched">scheduled</span>}
                    {loading && <span className="storm-tag">loading…</span>}
                  </span>
                  <span className="storm-row-text">
                    {rating.sentence}
                    {rating.fast === null ? " (Timing still loading.)" : ""}
                  </span>
                </button>
              );
            })}
          </div>
        ))}
      </div>
      {loadError && <span className="picker-error">{loadError}</span>}
    </div>
  );
}

/** The loaded storm's difficulty chip and sentence, for the setup's "sea ahead" line. */
export function useCurrentRating(bundle: Bundle): Rating | null {
  useFactsVersion();
  if (bundle.source === "scenario") return null;
  rememberBundle(bundle);
  return rate(factsFor({ storm_id: bundle.storm_id, symbol: bundle.symbol, asset_class: bundle.asset_class, move_bp: bundle.storm.move_bp }));
}
