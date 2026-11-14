// Replay bundle, schema_version 1. Mirrors contracts/replay_bundle.md exactly.
// If the contract changes, this file changes with it (and loadBundle.ts checks it at runtime).

export type ShipKey = "prepared" | "unprepared";

export type StormKind = "scheduled" | "unscheduled";

export interface StormInfo {
  onset_i: number;
  trough_i: number;
  move_bp: number; // signed basis points
  kind: StormKind;
  label: string; // e.g. "-2.9% in 54 min"
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
  cut_i: number | null;
  cut_fraction: number; // 0 to 1
}

export interface WatchEvent {
  i: number;
  type: "watch";
  text: string;
  at_i: number; // frame of the scheduled release
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

export type BundleEvent = WatchEvent | AlarmEvent | MarginCallEvent | AllClearEvent;
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

export interface Report {
  text: string;
  verified: boolean;
  unverified_numbers: unknown[];
  model: string;
}

export interface Bundle {
  schema_version: 1;
  storm_id: string;
  title: string;
  symbol: string;
  asset_class: string; // "fx" for SGX data; "equity" or "crypto" later
  source: "sgx" | "synthetic" | string;
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

export interface StormIndex {
  schema_version: 1;
  storms: StormIndexEntry[];
  metrics: {
    split: string;
    storms: number;
    caught: number;
    median_move_ahead_pct: number | null;
    false_alarms_per_day: number | null;
  } | null;
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
