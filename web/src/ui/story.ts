// The words the presenter view shows, built from the bundle only: the scrubber's event ticks, the captions,
// the end card and the shortened stress rows. No number is typed here: every one is read from the bundle.
// Pure (one import, lib/format.ts, which imports nothing), so ui/hud.test.mjs runs it under Node.

import type { Bundle, ShipKey, StressRow } from "../types/bundle";
import { fmtClock, fmtUsd, fmtUtc, watchName } from "../lib/format";

/** Typographic minus for signed figures in short rows ("−58 bp", "−$118k"). */
const minus = (s: string) => s.replace(/^-/, "−");

// ---------- stress tests: one short line per earlier storm ----------

export interface ShortStress {
  /** "USDJPY 2 Jul 12:20" */
  what: string;
  /** "−58 bp", "−4.2%", or "" when the scenario names no move. */
  move: string;
  /** "−$118k" */
  pnl: string;
  marginCall: boolean;
  /** The scenario as the backend wrote it (tooltip): nothing is lost by shortening. */
  full: string;
}

/**
 * "USDJPY storm 02 Jul 12:20 UTC: -58 bp, applied as USD +58 bp" → what "USDJPY 2 Jul 12:20", move "−58 bp".
 * Anything that does not look like the backend's two formats is kept whole as `what`.
 */
export function shortStress(r: StressRow): ShortStress {
  const full = r.scenario;
  let what = full;
  let move = "";
  const m = /^(.*?):\s*([+-]?\d+(?:\.\d+)?\s*(?:bp|%))(?:,\s*applied\b.*)?$/.exec(full.trim());
  if (m) {
    what = m[1]
      .replace(/\s+storm\b/i, "")
      .replace(/\s+UTC$/i, "")
      .replace(/\b0(\d)\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b/, "$1 $2")
      .trim();
    move = minus(m[2].replace(/\s+/g, " ").replace(/^\+?(\d)/, "+$1"));
  }
  return { what, move, pnl: minus(fmtUsd(r.pnl_usd, true)), marginCall: r.margin_call, full };
}

/** "USDJPY 2 Jul 12:20 −58 bp → −$118k, afloat" */
export function stressLine(r: StressRow): string {
  const s = shortStress(r);
  return `${s.what}${s.move ? ` ${s.move}` : ""} → ${s.pnl}, ${s.marginCall ? "margin call" : "afloat"}`;
}

// ---------- story events: ticks on the scrubber and captions ----------

export type StoryKind = "watch" | "alarm" | "squall" | "fair_wind" | "cut" | "restore" | "margin_call" | "all_clear";

export interface StoryEvent {
  i: number;
  kind: StoryKind;
  /** Short name for the tick's tooltip: "Alarm", "Cut", ... */
  name: string;
  /** The caption's sentence, without the time. */
  text: string;
  ship?: ShipKey;
}

/** Tick colours, the same family as the chart's markers and the toasts. */
export const STORY_COLORS: Record<StoryKind, string> = {
  watch: "#d6c450",
  alarm: "#f5a623",
  squall: "#c9a0ff",
  fair_wind: "#5ecf9a",
  cut: "#7cc4ff",
  restore: "#bfe3ff",
  margin_call: "#ef5350",
  all_clear: "#e6edf4",
};

const NAMES: Record<StoryKind, string> = {
  watch: "Storm watch",
  alarm: "Alarm",
  squall: "Squall",
  fair_wind: "Fair wind",
  cut: "Cut",
  restore: "Restore",
  margin_call: "Margin call",
  all_clear: "All clear",
};

/** Same-frame order: what the viewer should read first. */
const ORDER: StoryKind[] = ["watch", "alarm", "squall", "fair_wind", "cut", "restore", "margin_call", "all_clear"];

const SHIP_WORDS: Record<ShipKey, string> = { prepared: "the prepared ship", unprepared: "the unprepared ship" };
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** A cut or restore that changed a ship's cargo (derive.ts: ShipDerived.actions, which falls back to ships.*.cut_i). */
export interface ShipAction {
  i: number;
  kind: "cut" | "restore";
}

/** Clock time of frame i, "10:19" (UTC; a scenario's what-if clock). */
export const frameClock = (b: Pick<Bundle, "t0" | "step_s">, i: number) => fmtClock(b.t0 + i * b.step_s);

/**
 * Every event of the replay in order: the bundle's watch, alarm, squall, fair_wind, margin_call and all_clear events,
 * and each ship's cuts and restores as they changed its cargo (`actions`: the cut / restore events, or the bundle's
 * ships.*.cut_i / restore_i when it has none). A ship's margin_call_i without a margin_call event counts too.
 */
export function storyEvents(b: Bundle, actions: Record<ShipKey, ShipAction[]>): StoryEvent[] {
  const out: StoryEvent[] = [];
  const inRange = (i: number) => Number.isFinite(i) && i >= 0 && i < b.n;
  const called = new Set<ShipKey>();
  for (const e of b.events) {
    if (!inRange(e.i)) continue;
    switch (e.type) {
      case "watch": {
        const name = watchName(e);
        const due = e.at_i !== undefined && inRange(e.at_i) ? ` due at ${frameClock(b, e.at_i)}` : "";
        out.push({ i: e.i, kind: "watch", name: NAMES.watch, text: `Storm watch: ${name}${due}` });
        break;
      }
      case "alarm":
        out.push({
          i: e.i,
          kind: "alarm",
          name: NAMES.alarm,
          text: e.move_ahead_pct === null ? "The alarm fires" : `The alarm fires with ${Math.round(e.move_ahead_pct)}% of the move still ahead`,
        });
        break;
      case "squall":
        out.push({ i: e.i, kind: "squall", name: NAMES.squall, text: "A squall: a sharp move against the book, no cut" });
        break;
      case "fair_wind":
        out.push({ i: e.i, kind: "fair_wind", name: NAMES.fair_wind, text: "Fair wind: a sharp move in the book's favour" });
        break;
      case "margin_call":
        called.add(e.ship);
        out.push({ i: e.i, kind: "margin_call", name: NAMES.margin_call, ship: e.ship, text: `Margin call: ${SHIP_WORDS[e.ship]} goes down` });
        break;
      case "all_clear":
        out.push({ i: e.i, kind: "all_clear", name: NAMES.all_clear, text: "All clear: the storm has passed" });
        break;
      default:
        break; // cut and restore come from `actions` (the cargo that actually changed)
    }
  }
  for (const k of ["prepared", "unprepared"] as ShipKey[]) {
    const mc = b.ships[k].margin_call_i;
    if (!called.has(k) && mc !== null && inRange(mc)) {
      out.push({ i: mc, kind: "margin_call", name: NAMES.margin_call, ship: k, text: `Margin call: ${SHIP_WORDS[k]} goes down` });
    }
    const pct = Math.round(b.ships[k].cut_fraction * 100);
    for (const a of actions[k]) {
      if (!inRange(a.i)) continue;
      out.push(
        a.kind === "cut"
          ? { i: a.i, kind: "cut", name: NAMES.cut, ship: k, text: `${cap(SHIP_WORDS[k])} cuts ${pct}% of its cargo` }
          : { i: a.i, kind: "restore", name: NAMES.restore, ship: k, text: `${cap(SHIP_WORDS[k])} hoists its cargo back aboard` },
      );
    }
  }
  out.sort((x, y) => x.i - y.i || ORDER.indexOf(x.kind) - ORDER.indexOf(y.kind));
  return out;
}

/** "10:19 · The prepared ship cuts 75% of its cargo" */
export function captionLine(b: Pick<Bundle, "t0" | "step_s">, e: StoryEvent): string {
  return `${frameClock(b, e.i)} · ${e.text}`;
}

/** The events whose frame the playhead crossed going from `prev` to `cur` (prev < i <= cur). */
export function crossed(events: StoryEvent[], prev: number, cur: number): StoryEvent[] {
  return events.filter((e) => e.i > prev && e.i <= cur);
}

/** Ticks closer than `minGap` frames are drawn as one tick with every event in its tooltip. */
export function groupTicks(events: StoryEvent[], minGap: number): StoryEvent[][] {
  const groups: StoryEvent[][] = [];
  for (const e of events) {
    const g = groups[groups.length - 1];
    if (g && e.i - g[0].i <= minGap) g.push(e);
    else groups.push([e]);
  }
  return groups;
}

// ---------- end card ----------

export interface EndShip {
  key: ShipKey;
  label: string;
  start: number;
  final: number;
  /** Change from the start, percent. */
  changePct: number;
  /** The ship's margin call, if it had one: frame and clock ("14:22 UTC"). */
  marginCall: { i: number; time: string } | null;
}

export interface EndFacts {
  ships: [EndShip, EndShip];
  /** prepared final − unprepared final, USD. */
  diff: number;
  /** "Following the alarm kept $353,377 more", from the sign of diff. */
  verdict: string;
}

/** The last frame's equities from the bundle's series, each ship's margin call (ships.*.margin_call_i, else its event). */
export function endFacts(b: Bundle): EndFacts {
  const last = b.n - 1;
  const ship = (key: ShipKey): EndShip => {
    const info = b.ships[key];
    const final = (key === "prepared" ? b.series.prepared_equity : b.series.unprepared_equity)[last];
    const ev = b.events.find((e) => e.type === "margin_call" && e.ship === key);
    const mcI = info.margin_call_i ?? (ev ? ev.i : null);
    return {
      key,
      label: info.label,
      start: info.start_equity_usd,
      final,
      changePct: info.start_equity_usd > 0 ? (final / info.start_equity_usd - 1) * 100 : 0,
      marginCall: mcI === null ? null : { i: mcI, time: fmtUtc(b.t0 + mcI * b.step_s, false) },
    };
  };
  const p = ship("prepared");
  const u = ship("unprepared");
  const diff = p.final - u.final;
  const verdict =
    Math.round(diff) === 0
      ? "Both ships ended level"
      : diff > 0
        ? `Following the alarm kept ${fmtUsd(diff)} more`
        : `Ignoring the alarm kept ${fmtUsd(-diff)} more`;
  return { ships: [p, u], diff, verdict };
}

// ---------- presenter clean view: H ----------

/** The parts of a KeyboardEvent the H key reads. */
export interface KeyLike {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
  repeat?: boolean;
  target?: unknown;
}

function inField(target: unknown): boolean {
  if (typeof target !== "object" || target === null) return false;
  const t = target as { tagName?: unknown; isContentEditable?: unknown };
  const tag = typeof t.tagName === "string" ? t.tagName.toUpperCase() : "";
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || t.isContentEditable === true;
}

/**
 * True for a press of H that should toggle the clean view: no modifier, no auto-repeat, not typing in a field.
 * Only H: L, 1, 2, 3, Esc (landing/keys.ts), Space (play), C and R (Survive) keep their meaning.
 */
export function isCleanViewKey(e: KeyLike): boolean {
  if (e.ctrlKey || e.metaKey || e.altKey || e.repeat) return false;
  if (inField(e.target)) return false;
  return e.key === "h" || e.key === "H";
}

/** Listen for H on `target` (the window). Returns the unbind function. */
export function bindCleanViewKey(target: EventTarget, toggle: () => void): () => void {
  const onKey = (ev: Event) => {
    if (!isCleanViewKey(ev as Event & KeyLike)) return;
    ev.preventDefault();
    toggle();
  };
  target.addEventListener("keydown", onKey);
  return () => target.removeEventListener("keydown", onKey);
}
