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
  sunDir: Vector3; // from frame time of day (UTC)
  dayFactor: number; // 0 night .. 1 day
  utcHours: number;
  alarm: number; // 0..1 smoothed alarmActive
  flash: number; // lightning flash 0..1 (set by Lightning)
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
  wave: { amp: 0.35, chop: 0.2, time: 0 },
  sunDir: new Vector3(0, 1, -1).normalize(),
  dayFactor: 1,
  utcHours: 12,
  alarm: 0,
  flash: 0,
  elapsed: 0,
  dt: 0.016,
};

export const WIND_BY_STATE = [0.15, 0.55, 1.0];

/** Wave amplitude (scene units) from vol_ratio. 1 = gentle swell, 7+ = heavy sea. */
export function waveAmpFromVol(v: number): number {
  return Math.min(2.8, 0.32 * Math.pow(Math.max(0.05, v), 0.78));
}
/** Chop (short steep waves, foam, normal-map distortion) from vol_ratio. */
export function chopFromVol(v: number): number {
  return Math.min(1.6, Math.max(0.1, (v - 0.4) * 0.22));
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
  vis.wave.time += dt * (0.8 + 0.7 * vis.wind);
  waveUniforms.uWaveAmp.value = vis.wave.amp;
  waveUniforms.uWaveChop.value = vis.wave.chop;
  waveUniforms.uWaveTime.value = vis.wave.time;
  const time = sampleAt(d.times, t);
  vis.utcHours = (((time % 86400) + 86400) % 86400) / 3600;
  vis.dayFactor = sunFromUtcHours(vis.utcHours, vis.sunDir).dayFactor;
  vis.alarm = damp(vis.alarm, stepAt(d.alarmActive, t), 3, dt);
  vis.flash = Math.max(0, vis.flash - dt * 3.5);
}
