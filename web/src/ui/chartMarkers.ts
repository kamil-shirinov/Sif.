// The market chart's event markers and the words under them, in order, each with a unique, stable key. Pure code
// (types only from lightweight-charts), tested by hud.test.mjs.

import type { SeriesMarker, Time, UTCTimestamp } from "lightweight-charts";
import type { Bundle } from "../types/bundle";
import type { Derived } from "../lib/derive";

export const bucketTime = (b: Bundle, i: number, size: number) => (b.t0 + Math.floor(i / size) * size * b.step_s) as UTCTimestamp;

export interface ChartMarker {
  i: number;
  text: string;
  m: SeriesMarker<Time>;
  /** Unique and stable: "minute-text", then "#1", "#2" for repeats of the same word on the same minute. */
  key: string;
  /** A repeat of the same word on the same minute (both ships margin-called together): its shape draws, its label is shared. */
  repeat: boolean;
}

/** Every marker of the bundle (Replay) or of the player's run (Survive), sorted by minute; revealed as the playhead passes. */
export function chartMarkers(bundle: Bundle, derived: Pick<Derived, "ships">, player: Derived["player"], B: number): ChartMarker[] {
  const out: { i: number; text: string; m: SeriesMarker<Time> }[] = [];
  out.push({
    i: bundle.storm.onset_i,
    text: "Onset",
    m: { time: bucketTime(bundle, bundle.storm.onset_i, B), position: "aboveBar", shape: "circle", color: "#e0e6ee" },
  });
  const releases = new Set<number>();
  // The chart draws only the shapes. The words are our own DOM labels (see `labels` below): the library centres
  // every label on its marker, so two events in the same or neighbouring candles printed on top of each other.
  const mark = (i: number, position: "aboveBar" | "belowBar", shape: SeriesMarker<Time>["shape"], color: string, text: string) =>
    out.push({ i, text, m: { time: bucketTime(bundle, i, B), position, shape, color } });
  for (const e of bundle.events) {
    // In Survive the demo ships' trades are not the player's: the player's own are marked below.
    if (player && (e.type === "cut" || e.type === "restore" || e.type === "margin_call")) continue;
    if (e.type === "alarm") mark(e.i, "aboveBar", "arrowDown", "#f5a623", "Alarm");
    if (e.type === "margin_call") mark(e.i, "belowBar", "square", "#ef5350", "Margin call");
    if (e.type === "squall") mark(e.i, "aboveBar", "circle", "#f0b44c", "Squall");
    if (e.type === "fair_wind") mark(e.i, "aboveBar", "arrowUp", "#5ecf9a", "Fair wind");
    if (e.type === "watch" && e.at_i !== undefined) releases.add(e.at_i);
  }
  // Cuts and restores at their fill frames (cut_i: one bar after the alarm), from the ships' derived actions:
  // the cut / restore events when the bundle has them, else ships.*.cut_i / restore_i. Same frames as the splash and toast.
  if (!player) {
    for (const k of ["prepared", "unprepared"] as const) {
      for (const a of derived.ships[k].actions) mark(a.i, "belowBar", a.kind === "cut" ? "arrowDown" : "arrowUp", "#7cc4ff", a.kind === "cut" ? "Cut" : "Restore");
    }
  }
  if (bundle.storm.kind === "scheduled" && bundle.storm.event_i !== undefined) releases.add(bundle.storm.event_i);
  for (const i of releases) mark(i, "aboveBar", "circle", "#d6c450", "Release");
  if (player) {
    for (const a of player.actions) mark(a.i, "belowBar", a.kind === "cut" ? "arrowDown" : "arrowUp", "#ffd27a", a.kind === "cut" ? "You cut" : "You restore");
    if (player.marginCallI !== null) mark(player.marginCallI, "belowBar", "square", "#ef5350", "Sunk");
  }
  out.sort((a, b) => a.i - b.i);
  // A unique, stable key per marker: two ships can be margin-called (or cut) on the same minute, as on INTC
  // (both at minute 189), so minute and text alone repeat. The nth repeat gets "#n".
  const seen = new Map<string, number>();
  return out.map((mk) => {
    const base = `${mk.i}-${mk.text}`;
    const nth = seen.get(base) ?? 0;
    seen.set(base, nth + 1);
    return { ...mk, key: nth === 0 ? base : `${base}#${nth}`, repeat: nth > 0 };
  });
}
