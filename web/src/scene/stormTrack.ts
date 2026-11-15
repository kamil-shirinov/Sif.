import type { Bundle } from "../types/bundle";
import type { Derived } from "../lib/derive";

// Where the storm cell is at every frame. Causal by construction: frame i is computed from frames 0..i only
// (series.risk and the alarm window up to i), in one forward pass, so the cell never knows what the market does
// next. It is precomputed once per bundle only so that pausing and scrubbing show the same cell as playing.

export interface StormTrack {
  /**
   * Along-track position per frame: -1 on the upwind horizon, 0 over the ships, +1 on the downwind horizon.
   * The cell only ever travels downwind (u never decreases while a cell lives).
   */
  u: Float32Array;
  /** How built the cell is, 0 (nothing) to 1 (a full cumulonimbus with its anvil). */
  life: Float32Array;
  /** How violent it is, 0 to 1 (darkness of the base, rain shafts): follows the smoothed risk. */
  power: Float32Array;
}

const smoothstep = (a: number, b: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

/** Frames of smoothing on risk (an exponential average over about this many frames). */
const RISK_EMA = 0.3;
/** Risk at which a cell starts to build on the horizon, and at which it would be overhead without an alarm. */
export const CELL_BUILD_RISK = 0.14;
export const CELL_OVERHEAD_RISK = 0.8;
/** Track speed in u per frame: closing in on rising risk, rushing in on an alarm, drifting away after. */
const SPEED_APPROACH = 0.035;
const SPEED_ALARM = 0.12;
const SPEED_PASS = 0.016;
/** While the alarm is on and risk has fallen, the cell has slid this far past the ships (it is leaving). */
const ALARM_SLIDE = 0.2;

export function makeStormTrack(b: Bundle, d: Derived): StormTrack {
  const n = d.n;
  const u = new Float32Array(n);
  const life = new Float32Array(n);
  const power = new Float32Array(n);
  const risk = b.series.risk;
  let ema = risk[0] ?? 0;
  let pos = -1;
  let built = 0;
  let passing = false; // true once the cell is on its way out: it does not come back, a new one builds upwind
  for (let i = 0; i < n; i++) {
    ema += ((risk[i] ?? 0) - ema) * RISK_EMA;
    const alarm = d.alarmActive[i] === 1;
    // How close the data says the storm is: overhead on an alarm, otherwise by smoothed risk.
    const want = alarm ? 1 : smoothstep(CELL_BUILD_RISK, CELL_OVERHEAD_RISK, ema);
    if (alarm) {
      // Over the ships. As risk falls under the alarm the cell slides on downwind: it is already leaving.
      const target = ALARM_SLIDE * (1 - smoothstep(0.15, 0.6, ema));
      if (pos < target) pos = Math.min(target, pos + (pos < 0 ? SPEED_ALARM : SPEED_PASS));
      passing = false;
      built = Math.min(1, built + 0.12);
    } else if (pos > -1 && (passing || pos >= 0)) {
      // No alarm (any more) and it has reached the ships: it drifts past and away, thinning as it goes.
      passing = true;
      pos += SPEED_PASS;
      built = Math.max(0, built - 0.006 - 0.02 * Math.max(0, pos - 0.6));
      if (pos >= 1 || built <= 0) {
        pos = -1;
        built = 0;
        passing = false;
      }
    } else if (want > 0.01 || built > 0) {
      // Building on the upwind horizon and closing in as risk climbs; it never backs away upwind. If risk
      // falls again before it arrives it keeps its distance and thins out where it stands, or, once it has come
      // more than half way, carries on past the ships.
      const target = -(1 - want);
      if (pos < target) pos = Math.min(target, pos + SPEED_APPROACH);
      const grow = 0.25 + 0.75 * want;
      built += want > 0.01 ? Math.min(0.05, Math.max(0, grow - built)) : -0.02;
      if (want <= 0.01 && pos > -0.5) passing = true;
      if (built <= 0) {
        built = 0;
        pos = -1;
      }
    }
    u[i] = pos;
    life[i] = Math.min(1, Math.max(0, built));
    power[i] = Math.min(1, Math.max(0, alarm ? Math.max(ema, 0.35) : ema));
  }
  return { u, life, power };
}
