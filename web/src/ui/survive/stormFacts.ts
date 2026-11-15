// The storm list's timing facts. index.json gives each storm's move but not how fast it came, so the list reads each
// listed bundle once, in the background (two at a time), and keeps only its StormFacts. The loaded bundle is used
// directly. A bundle that fails to load keeps its size-only rating.

import { useSyncExternalStore } from "react";
import type { Bundle, StormIndexEntry } from "../../types/bundle";
import { loadBundle } from "../../lib/loadBundle";
import { factsFromBundle, factsFromEntry, type StormFacts } from "./difficulty";

const known = new Map<string, StormFacts>();
const pending = new Set<string>();
const failed = new Set<string>();
const queue: { id: string; file?: string }[] = [];
const listeners = new Set<() => void>();
let version = 0;
let running = 0;
const CONCURRENCY = 2;

function notify() {
  version++;
  for (const l of listeners) l();
}

/**
 * The loaded bundle's own facts (not a what-if: its storm is someone else's). Called while rendering, so it does not
 * notify: the component calling it reads the facts straight after, and the others catch up on the next arrival.
 */
export function rememberBundle(b: Bundle) {
  if (b.source === "scenario" || known.has(b.storm_id)) return;
  known.set(b.storm_id, factsFromBundle(b));
}

export function factsFor(e: Pick<StormIndexEntry, "storm_id" | "symbol" | "asset_class" | "move_bp">): StormFacts {
  return known.get(e.storm_id) ?? factsFromEntry(e);
}

function pump() {
  while (running < CONCURRENCY && queue.length > 0) {
    const job = queue.shift()!;
    running++;
    loadBundle(job.id, job.file)
      .then((b) => known.set(job.id, factsFromBundle(b)))
      .catch(() => failed.add(job.id))
      .finally(() => {
        pending.delete(job.id);
        running--;
        notify();
        pump();
      });
  }
}

/** Ask for the timing of every listed storm not known yet. Cheap to call on every render. */
export function requestFacts(entries: readonly Pick<StormIndexEntry, "storm_id" | "file">[]) {
  let added = false;
  for (const e of entries) {
    if (known.has(e.storm_id) || pending.has(e.storm_id) || failed.has(e.storm_id)) continue;
    pending.add(e.storm_id);
    queue.push({ id: e.storm_id, file: e.file });
    added = true;
  }
  if (added) pump();
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};
/** Re-render when facts arrive. */
export function useFactsVersion(): number {
  return useSyncExternalStore(subscribe, () => version);
}
