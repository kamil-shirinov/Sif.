// Replay bundle, schema_version 1. Mirrors contracts/replay_bundle.md exactly,
// plus the optional additions (restore_i, squall / fair_wind / cut / restore events,
// storm.event / storm.event_i, report.inspector, source "scenario"). Optional fields are
// parsed leniently by loadBundle.ts: a missing or malformed one never stops the replay.

export type ShipKey = "prepared" | "unprepared";

export type StormKind = "scheduled" | "unscheduled";

export interface StormInfo {
  onset_i: number;
  trough_i: number;
  move_bp: number; // signed basis points
  kind: StormKind;
  label: string; // e.g. "-2.9% in 54 min"
  /** Scheduled storms: name of the release, e.g. "US Employment Situation". */
  event?: string;
  /** Scheduled storms: frame of the release. */
  event_i?: number;
}

/** Every array has length n and is indexed by frame i. */
export interface BundleSeries {
  open: number[];
  high: number[];
  low: number[];
  mid: number[]; // the close
  spread_bp: number[];
  vol_ratio: number[]; // 1 = normal
  risk: number[]; // 0 to 1
  state: number[]; // 0 calm, 1 watch, 2 storm
  jump: number[]; // 0 or 1
  prepared_equity: number[];
  unprepared_equity: number[];
}

export interface ShipInfo {
  label: string;
  start_equity_usd: number;
  margin_call_i: number | null;
  cut_i: number | null; // first cut
  cut_fraction: number; // 0 to 1
  /** First restore after the first cut. Optional. */
  restore_i?: number | null;
}

export interface WatchEvent {
  i: number;
  type: "watch";
  text: string;
  /** Frame of the scheduled release. Optional: without it there is no storm front. */
  at_i?: number;
  /** Name of the scheduled release, e.g. "US Employment Situation". Optional. */
  event?: string;
}

export interface AlarmEvent {
  i: number;
  type: "alarm";
  text: string;
  move_ahead_pct: number;
}

export interface MarginCallEvent {
  i: number;
  type: "margin_call";
  text: string;
  ship: ShipKey;
}

export interface AllClearEvent {
  i: number;
  type: "all_clear";
  text: string;
}

/** A sharp move against the book that does not warrant a cut: lighthouse amber flash. */
export interface SquallEvent {
  i: number;
  type: "squall";
  text: string;
}

/** A sharp move in the book's favour: sun breaks through, sails fill. */
export interface FairWindEvent {
  i: number;
  type: "fair_wind";
  text: string;
}

/** The prepared ship throws cargo overboard (ship defaults to "prepared"). */
export interface CutEvent {
  i: number;
  type: "cut";
  text: string;
  ship?: ShipKey;
}

/** The prepared ship hoists the cargo back aboard (ship defaults to "prepared"). */
export interface RestoreEvent {
  i: number;
  type: "restore";
  text: string;
  ship?: ShipKey;
}

export type BundleEvent =
  | WatchEvent
  | AlarmEvent
  | MarginCallEvent
  | AllClearEvent
  | SquallEvent
  | FairWindEvent
  | CutEvent
  | RestoreEvent;
export type BundleEventType = BundleEvent["type"];

export interface Position {
  instrument: string;
  side: string;
  notional_usd: number;
}

export interface Exposure {
  as_of_i: number;
  positions: Position[];
  net_usd_by_ccy: Record<string, number>;
  leverage: number;
  margin_buffer_pct: number;
}

export interface StressRow {
  scenario: string;
  pnl_usd: number;
  margin_call: boolean;
}

export interface Inspector {
  verdict: string; // "ok" or "flag" from the backend; anything else is shown as is
  issues: string[];
}

export interface Report {
  text: string;
  verified: boolean; // every number was checked by code against the facts
  unverified_numbers: unknown[];
  model: string;
  inspector?: Inspector | null;
}

export interface Bundle {
  schema_version: 1;
  storm_id: string;
  title: string;
  symbol: string;
  asset_class: string; // "fx" for SGX data; "equity" or "crypto" later
  source: "sgx" | "synthetic" | "scenario" | string;
  book_is_synthetic: boolean;
  t0: number; // UTC epoch seconds of frame 0
  step_s: number; // 60
  n: number;
  storm: StormInfo;
  series: BundleSeries;
  ships: Record<ShipKey, ShipInfo>;
  events: BundleEvent[];
  exposure: Exposure;
  stress: StressRow[];
  report: Report | null;
}

export interface StormIndexEntry {
  storm_id: string;
  title: string;
  symbol: string;
  asset_class: string;
  kind: StormKind;
  move_bp: number;
  file: string;
}

/**
 * Backtest metrics in index.json. The contract lists split, storms, caught, median_move_ahead_pct
 * and false_alarms_per_day; alarmed and median_minutes_to_alarm are optional extras (the backtest
 * reports both). Anything missing or null hides its row on the evidence card.
 */
export interface IndexMetrics {
  split: string | null;
  storms: number | null;
  /** Storms that raised an alarm at all. */
  alarmed: number | null;
  /** Storms alarmed with at least half of the move still ahead. */
  caught: number | null;
  median_move_ahead_pct: number | null;
  median_minutes_to_alarm: number | null;
  false_alarms_per_day: number | null;
}

export interface StormIndex {
  schema_version: 1;
  storms: StormIndexEntry[];
  metrics: IndexMetrics | null;
}

export const SERIES_KEYS: (keyof BundleSeries)[] = [
  "open",
  "high",
  "low",
  "mid",
  "spread_bp",
  "vol_ratio",
  "risk",
  "state",
  "jump",
  "prepared_equity",
  "unprepared_equity",
];
