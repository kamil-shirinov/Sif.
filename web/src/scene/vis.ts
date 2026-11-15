import { Vector3 } from "three";
import type { Bundle } from "../types/bundle";
import type { Derived } from "../lib/derive";
import { sampleAt, stepAt } from "../lib/derive";
import { waveUniforms, type WaveParams } from "./waves";

// Shared, mutable visual state. Written once per animation frame by <VisDriver/> (priority -1),
// read by every scene element. All targets come from bundle fields; smoothing only removes pops.

export interface Vis {
  t: number; // playhead (fractional frame)
  frame: number;
  volRatio: number; // series.vol_ratio, interpolated + smoothed
  risk: number; // series.risk, interpolated + smoothed
  state: number; // series.state at frame
  wind: number; // 0..1 from state
  wave: WaveParams; // amp & chop from vol_ratio, time advanced by wind
  sunDir: Vector3; // from the solar clock (UTC for FX, exchange-local for equities); pushed below the horizon while the market is closed
  dayFactor: number; // 0 night .. 1 day
  utcHours: number;
  solarHours: number; // hour of day the sun follows: utcHours for FX, New York time for equities
  closed: number; // 0..1 smoothed series.market_open = 0: night, whatever the clock says
  lantern: number; // 0..1: the ships' lanterns, lit as daylight fails
  alarm: number; // 0..1 smoothed alarmActive
  flash: number; // lightning flash 0..1 (set by Lightning)
  flashPos: Vector3; // where the last bolt came out of the cloud (lights the cloud base around it)
  /**
   * The true wind. Its strength is `wind` (from series.state). Its direction comes from the book: `windTail` is the
   * smoothed, signed change of the book's equity over the last 3 frames (+1 = equity rising fast: the wind is astern;
   * -1 = falling fast: it is ahead; 0 = on the beam), and `windDir` is the unit vector it blows toward.
   */
  windTail: number;
  windDir: Vector3;
  // The storm cell (StormCell.tsx, from stormTrack.ts): where it stands, how built it is, how nearly overhead (0..1).
  cellX: number;
  cellZ: number;
  cellLife: number;
  cellNear: number;
  squall: number; // 0..1: lighthouse amber flash after a squall event
  fairWind: number; // 0..1: sun breaking through and sails filling after a fair_wind event
  elapsed: number; // wall-clock seconds
  dt: number;
}

export const vis: Vis = {
  t: 0,
  frame: 0,
  volRatio: 1,
  risk: 0,
  state: 0,
  wind: 0.15,
  wave: { amp: 0.35, chop: 0.2, steep: 0.4, time: 0 },
  sunDir: new Vector3(0, 1, -1).normalize(),
  dayFactor: 1,
  utcHours: 12,
  solarHours: 12,
  closed: 0,
  lantern: 0,
  alarm: 0,
  flash: 0,
  flashPos: new Vector3(0, 500, -300),
  windTail: 0,
  windDir: new Vector3(0, 0, 1),
  cellX: 0,
  cellZ: -1500,
  cellLife: 0,
  cellNear: 0,
  squall: 0,
  fairWind: 0,
  elapsed: 0,
  dt: 0.016,
};

/** Where the moon stands at night: behind the ships and to the left, so they are rim-lit and the sea glitters toward the camera. */
export const MOON_DIR = new Vector3(-0.5, 0.58, -0.64).normalize();

/** Equity change over 3 frames (as a share of start equity, per unit of cargo held) that puts the wind dead astern. */
export const WIND_FULL_PER_RETURN = 400;

export const WIND_BY_STATE = [0.15, 0.55, 1.0];

/** Wave amplitude (scene units) from vol_ratio. 1 = gentle swell, 7+ = heavy sea. */
export function waveAmpFromVol(v: number): number {
  return Math.min(2.8, 0.32 * Math.pow(Math.max(0.05, v), 0.78));
}
/** Chop (short steep waves, foam, normal-map distortion) from vol_ratio. */
export function chopFromVol(v: number): number {
  return Math.min(1.6, Math.max(0.1, (v - 0.4) * 0.22));
}

/** Gerstner steepness (how sharp the crests are) from vol_ratio: 0.44 at 1x normal, 1 from about 7x. */
export function steepFromVol(v: number): number {
  return Math.min(1, Math.max(0.35, 0.35 + 0.09 * v));
}

/** Sun direction from UTC time of day: rises in the east (-x) at 06:00, south (-z) at 12:00, sets west (+x) at 18:00. */
export function sunFromUtcHours(h: number, out: Vector3): { dayFactor: number } {
  const a = (Math.PI * (h - 6)) / 12;
  const elev = (62 * Math.PI) / 180 * Math.sin(a);
  const ce = Math.cos(elev);
  out.set(-Math.cos(a) * ce, Math.sin(elev), -Math.abs(Math.sin(a)) * ce - 0.15).normalize();
  const dayFactor = Math.min(1, Math.max(0, (out.y + 0.06) / 0.3));
  return { dayFactor };
}

const damp = (cur: number, target: number, rate: number, dt: number) =>
  cur + (target - cur) * (1 - Math.exp(-rate * dt));

// ---- squall and fair wind ----
// Two sources, take the larger: (1) the playhead's distance from the event frame, so a paused
// frame (?at=) shows the effect and scrubbing is exact; (2) a wall-clock pulse started when the replay
// crosses the event while playing, so the effect stays visible at 8x and 16x.
export const SQUALL_FRAMES = 6; // flashing for this many market minutes after a squall
export const FAIR_WIND_RISE = 4; // frames for the sun to break through
export const FAIR_WIND_HOLD = 10; // frames at full effect
export const FAIR_WIND_FRAMES = 34; // frames until the effect has gone
const SQUALL_PULSE_S = 1.8;
const FAIR_WIND_PULSE_S = 8;
let squallPulseLeft = 0;
let fairWindPulseLeft = 0;
let prevT = 0;

export function pulseSquall() {
  squallPulseLeft = SQUALL_PULSE_S;
}
export function pulseFairWind() {
  fairWindPulseLeft = FAIR_WIND_PULSE_S;
}

/** Strength 0..1 of a squall `age` frames after its event frame. */
export function squallEnvelope(age: number): number {
  return age < 0 || age >= SQUALL_FRAMES ? 0 : 1 - age / SQUALL_FRAMES;
}

/** Strength 0..1 of a fair wind `age` frames after its event frame. */
export function fairWindEnvelope(age: number): number {
  if (age < 0 || age >= FAIR_WIND_FRAMES) return 0;
  if (age < FAIR_WIND_RISE) {
    const u = age / FAIR_WIND_RISE;
    return u * u * (3 - 2 * u);
  }
  if (age < FAIR_WIND_RISE + FAIR_WIND_HOLD) return 1;
  return 1 - (age - FAIR_WIND_RISE - FAIR_WIND_HOLD) / (FAIR_WIND_FRAMES - FAIR_WIND_RISE - FAIR_WIND_HOLD);
}

export function updateVis(b: Bundle, d: Derived, t: number, dt: number) {
  vis.dt = dt;
  vis.elapsed += dt;
  vis.t = t;
  vis.frame = Math.min(d.n - 1, Math.max(0, Math.floor(t)));
  vis.volRatio = damp(vis.volRatio, sampleAt(b.series.vol_ratio, t), 2.5, dt);
  vis.risk = damp(vis.risk, sampleAt(b.series.risk, t), 2.0, dt);
  vis.state = stepAt(b.series.state, t);
  vis.wind = damp(vis.wind, WIND_BY_STATE[vis.state] ?? 0.15, 0.8, dt);
  vis.wave.amp = damp(vis.wave.amp, waveAmpFromVol(vis.volRatio), 1.2, dt);
  vis.wave.chop = damp(vis.wave.chop, chopFromVol(vis.volRatio), 1.2, dt);
  vis.wave.steep = damp(vis.wave.steep, steepFromVol(vis.volRatio), 1.2, dt);
  vis.wave.time += dt * (0.8 + 0.7 * vis.wind);
  waveUniforms.uWaveAmp.value = vis.wave.amp;
  waveUniforms.uWaveChop.value = vis.wave.chop;
  waveUniforms.uWaveSteep.value = vis.wave.steep;
  waveUniforms.uWaveTime.value = vis.wave.time;
  const time = sampleAt(d.times, t);
  const hourOf = (sec: number) => (((sec % 86400) + 86400) % 86400) / 3600;
  vis.utcHours = hourOf(time);
  // The sun keeps the exchange's clock for equities (NVDA at 12:58 New York is noon, not 17:58 UTC) and UTC for FX.
  vis.solarHours = hourOf(time + stepAt(d.solarOffsetS, t));
  vis.dayFactor = sunFromUtcHours(vis.solarHours, vis.sunDir).dayFactor;
  // Market closed (series.market_open = 0) is night: the sun goes down and the lanterns come on.
  vis.closed = damp(vis.closed, d.closed ? stepAt(d.closed, t) : 0, 1.6, dt);
  if (vis.closed > 0.001) {
    vis.dayFactor *= 1 - vis.closed;
    vis.sunDir.y = vis.sunDir.y * (1 - vis.closed) - 0.3 * vis.closed;
    vis.sunDir.normalize();
  }
  vis.lantern = Math.min(1, Math.max(0, (0.75 - vis.dayFactor) / 0.5));
  vis.alarm = damp(vis.alarm, stepAt(d.alarmActive, t), 3, dt);

  // Wind direction. The book's equity over the last 3 frames, per unit of cargo still held (a cut book moves less
  // for the same market): +0.25% of start equity in 3 minutes on a full book is a wind dead astern, the same loss a
  // wind dead ahead. Between them it veers through the beam (blowing from the far side of the scene toward the
  // camera). The ships head roughly along +x.
  const book = d.player ?? d.ships.prepared;
  const held = Math.max(0.2, sampleAt(book.held, t));
  const mom = (sampleAt(book.equity, t) - sampleAt(book.equity, Math.max(0, t - 3))) / book.startEquity / held;
  const tail = Math.min(1, Math.max(-1, mom * WIND_FULL_PER_RETURN));
  vis.windTail = Math.abs(t - prevT) > 8 ? tail : damp(vis.windTail, tail, 0.9, dt);
  const ang = (Math.PI / 2) * (1 - vis.windTail);
  vis.windDir.set(Math.cos(ang), 0, Math.sin(ang));
  vis.flash = Math.max(0, vis.flash - dt * 3.5);

  // A jump of the playhead (seek, reload) drops any pulse left over from the old position.
  if (Math.abs(t - prevT) > 8) {
    squallPulseLeft = 0;
    fairWindPulseLeft = 0;
  }
  prevT = t;
  squallPulseLeft = Math.max(0, squallPulseLeft - dt);
  fairWindPulseLeft = Math.max(0, fairWindPulseLeft - dt);
  let sq = Math.min(1, squallPulseLeft / (SQUALL_PULSE_S * 0.66));
  for (const f of d.squalls) sq = Math.max(sq, squallEnvelope(t - f));
  let fw = Math.min(1, fairWindPulseLeft / (FAIR_WIND_PULSE_S * 0.75));
  for (const f of d.fairWinds) fw = Math.max(fw, fairWindEnvelope(t - f));
  vis.squall = sq;
  vis.fairWind = damp(vis.fairWind, fw, 4, dt);
}
