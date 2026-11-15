import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { DynamicDrawUsage, InstancedBufferAttribute, InstancedMesh, Matrix4, PlaneGeometry, Quaternion, ShaderMaterial, Vector3 } from "three";
import { CRANE_LEAD, HOIST_FRAMES, shipOf, type Derived, type SceneShip } from "../lib/derive";
import type { Bundle } from "../types/bundle";
import { WAVE_GLSL, waveAt, waveUniforms, type WaveSample } from "./waves";
import { vis, WIND_BY_STATE, WIND_FULL_PER_RETURN } from "./vis";
import { crateAboard, crateSlots, freeboardAt, SHIP_LAYOUT, shipPose, type CrateSlot } from "./Ship";
import { splash } from "./Particles";
import { containerGeometry, containerMaterial } from "./shipModel";
import { FOAM_NOISE_GLSL, foamLight } from "./foam";
import { BACKGROUND_BUDGET_MS, CutSim, SIM_PER_FRAME, type SimCrate } from "./cargoSim";

/** Frames afloat before a container with no restore ahead starts to go down, and the frames that takes. */
export const FLOAT_FRAMES = 24;
export const SETTLE_FRAMES = 44;
/** Simulated seconds the foam ring of a splash lasts. */
const RING_S = 2.2;
/** Simulated seconds over which a box hands over from riding with the ship to riding the waves, once it is wet. */
const WET_BLEND_S = 0.8;
/** Drift after the simulation: away from the ship (always), plus the wind; units per simulated second. */
const DRIFT_AWAY = 0.1;
const DRIFT_WIND = 0.16;
/** Spreading apart after the simulation: the group grows about its centre by this share per simulated second. */
const SPREAD_PER_S = 0.012;
const SPREAD_MAX = 1.7;

const _w: WaveSample = { h: 0, dhdx: 0, dhdz: 0 };
const _p = new Vector3();
const _p0 = new Vector3();
const _pf = new Vector3();
const _e3 = new Vector3();
const _n = new Vector3();
const _s = new Vector3();
const _q = new Quaternion();
const _q0 = new Quaternion();
const _qf = new Quaternion();
const _qs = new Quaternion();
const _qw = new Quaternion();
const _qk = new Quaternion();
const _m = new Matrix4();
const _rel = new Matrix4();
const UP = new Vector3(0, 1, 0);
const ZERO = new Matrix4().makeScale(0, 0, 0);
const smooth = (u: number) => {
  const t = Math.min(1, Math.max(0, u));
  return t * t * (3 - 2 * t);
};

interface PlanEntry {
  trip: { crate: number; out: number; back: number | null };
  slot: CrateSlot;
  sim: CutSim;
  /** Index of this box inside its simulation. */
  i: number;
  j: number;
}

/**
 * Where the group drifts after its simulation: a running sum, per frame, of the drift velocity (away from the ship, plus
 * the wind from the book's momentum as in vis.ts, unsmoothed so it is the same for every frame however it is reached).
 */
function makeDrift(b: Bundle, d: Derived, heading: number): Float32Array {
  const n = d.n;
  const out = new Float32Array(n * 2);
  const book = d.player ?? d.ships.prepared;
  const sx = Math.sin(heading);
  const sz = Math.cos(heading);
  let x = 0;
  let z = 0;
  for (let i = 0; i < n; i++) {
    out[i * 2] = x;
    out[i * 2 + 1] = z;
    const held = Math.max(0.2, book.held[i] ?? 1);
    const mom = ((book.equity[i] ?? 0) - (book.equity[Math.max(0, i - 3)] ?? 0)) / book.startEquity / held;
    const tail = Math.min(1, Math.max(-1, mom * WIND_FULL_PER_RETURN));
    const ang = (Math.PI / 2) * (1 - tail);
    const wind = WIND_BY_STATE[b.series.state[i] ?? 0] ?? 0.15;
    let vx = Math.cos(ang) * DRIFT_WIND * wind + sx * DRIFT_AWAY;
    let vz = Math.sin(ang) * DRIFT_WIND * wind + sz * DRIFT_AWAY;
    // Never back toward the ship: the component toward it is cut to a slow drift away.
    const along = vx * sx + vz * sz;
    if (along < 0.04) {
      vx += (0.04 - along) * sx;
      vz += (0.04 - along) * sz;
    }
    x += vx * SIM_PER_FRAME;
    z += vz * SIM_PER_FRAME;
  }
  return out;
}

/**
 * Containers off the deck. At each cut event the right number of containers go over the side as rigid bodies
 * (cargoSim.ts, cannon-es): shoved toward the rail, tipping over it, knocking each other, falling, splashing, floating
 * with freeboard showing, then drifting with the wind and away from the ship and slowly spreading apart, riding the
 * live waves all along. With no restore ahead a container goes down after a while. At each restore the ship's derrick
 * lifts them out one at a time and sets them back in their slots.
 * Everything is a function of the playhead (the simulation is a table, run ahead of it), so a paused or scrubbed frame
 * shows the same boxes as playing.
 */
export function Jettison({ bundle, shipKey, derived }: { bundle: Bundle; shipKey: SceneShip; derived: Derived }) {
  const ship = shipOf(derived, shipKey);
  const lay = SHIP_LAYOUT[shipKey];
  const slots = useMemo(() => crateSlots(derived.crates), [derived.crates]);
  const drift = useMemo(() => makeDrift(bundle, derived, lay.heading), [bundle, derived, lay]);

  // Simulations by cut, kept across plan changes (Survive rebuilds the plan at every cut and restore; a restore must
  // not throw away the simulation of the boxes it is lifting).
  const sims = useRef(new Map<string, CutSim>());
  const plan = useMemo(() => {
    const trips = ship.trips.filter((t) => slots[t.crate]).slice().sort((a, b) => a.out - b.out);
    // One simulation per cut: the trips that go over the side together.
    const groups: (typeof trips)[] = [];
    for (const t of trips) {
      const g = groups[groups.length - 1];
      if (g && t.out - g[g.length - 1].out < 1.5) g.push(t);
      else groups.push([t]);
    }
    const keep = new Map<string, CutSim>();
    const out: PlanEntry[] = [];
    let j = 0;
    for (const g of groups) {
      const start = g[0].out;
      const key = `${start.toFixed(3)}|${g.map((t) => t.crate).join(",")}`;
      let sim = sims.current.get(key);
      if (!sim) {
        const inGroup = new Set(g.map((t) => t.crate));
        const aboard = slots.filter((_, i) => !inGroup.has(i) && crateAboard(ship, i, start - 0.01));
        const crates: SimCrate[] = g.map((t, k) => ({ k, slot: slots[t.crate], release: (t.out - start) * SIM_PER_FRAME }));
        sim = new CutSim(start, crates, aboard, lay, freeboardAt(ship, start));
      }
      keep.set(key, sim);
      g.forEach((t, i) => out.push({ trip: t, slot: slots[t.crate], sim: sim!, i, j: j++ }));
    }
    sims.current = keep;
    return out;
  }, [ship, slots, lay]);

  const count = Math.max(1, plan.length);
  const boxes = useMemo(() => {
    const im = new InstancedMesh(containerGeometry(), containerMaterial(), count);
    im.instanceMatrix.setUsage(DynamicDrawUsage);
    for (let k = 0; k < count; k++) im.setMatrixAt(k, ZERO);
    plan.forEach((c, k) => im.setColorAt(k, c.slot.color));
    if (im.instanceColor) im.instanceColor.needsUpdate = true;
    im.frustumCulled = false;
    return im;
  }, [plan, count]);
  // Foam rings where containers hit the water: instanced quads lying on the sea.
  const rings = useMemo(() => {
    const g = new PlaneGeometry(1, 1, 6, 6);
    g.rotateX(-Math.PI / 2);
    const aRing = new InstancedBufferAttribute(new Float32Array(count * 2), 2);
    aRing.setUsage(DynamicDrawUsage);
    g.setAttribute("aRing", aRing);
    const mat = new ShaderMaterial({
      uniforms: { ...waveUniforms, uLight: { value: 1 } },
      vertexShader: /* glsl */ `
        ${WAVE_GLSL}
        attribute vec2 aRing;
        varying vec2 vUv; varying vec2 vRing;
        void main() {
          vUv = uv; vRing = aRing;
          vec4 wp = modelMatrix * instanceMatrix * vec4(position, 1.0);
          wp.y = waveEval(wp.xz).x + 0.09;
          gl_Position = projectionMatrix * viewMatrix * wp;
        }`,
      fragmentShader: /* glsl */ `
        uniform float uLight;
        varying vec2 vUv; varying vec2 vRing;
        ${FOAM_NOISE_GLSL}
        void main() {
          float prog = clamp(vRing.x, 0.0, 1.0);
          vec2 c = (vUv - 0.5) * 2.0;
          float r = length(c);
          float n = fmFbm(c * 4.5 + vRing.y * 17.0);
          float R = mix(0.18, 0.82, sqrt(prog));
          float ring = smoothstep(0.2, 0.0, abs(r - R + (n - 0.5) * 0.18));
          float churn = (1.0 - smoothstep(0.0, R, r)) * (1.0 - prog) * (1.0 - prog);
          // The ring tears into patches as it spreads.
          float tear = smoothstep(prog * 0.75, prog * 0.75 + 0.25, n + 0.12);
          float a = (ring * tear + churn * 0.8) * (1.0 - prog) * 0.9;
          if (a < 0.01) discard;
          gl_FragColor = vec4(vec3(0.86, 0.91, 0.93) * uLight, a);
        }`,
      transparent: true,
      depthWrite: false,
    });
    const im = new InstancedMesh(g, mat, count);
    im.instanceMatrix.setUsage(DynamicDrawUsage);
    for (let k = 0; k < count; k++) im.setMatrixAt(k, ZERO);
    im.frustumCulled = false;
    im.renderOrder = 3;
    return im;
  }, [count]);
  useEffect(
    () => () => {
      boxes.dispose();
      rings.geometry.dispose();
      (rings.material as ShaderMaterial).dispose();
      rings.dispose();
      shipPose[shipKey].hook.active = false;
    },
    [boxes, rings, shipKey],
  );

  /**
   * Box `c` at playhead `t`: its world position and attitude, waves and ship motion included. Returns how far it has
   * gone under for good (1: sunk, not drawn), and writes when it hit the water into `wet` (simulated seconds after the
   * cut, Infinity before).
   */
  const poseAt = (c: PlanEntry, t: number, pos: Vector3, quat: Quaternion, mNow: Matrix4): number => {
    const sim = c.sim;
    const simT = (t - sim.startFrame) * SIM_PER_FRAME;
    sim.sample(c.i, simT, _pf, _qf);
    const wetAt = sim.wetAt[c.i];
    const wb = wetAt === Infinity ? 0 : smooth((simT - wetAt) / WET_BLEND_S);
    // Riding with the ship (on deck, in the air): the table was made with the ship at rest; move it with her now.
    _rel.multiplyMatrices(mNow, sim.nominalInv);
    pos.copy(_pf).applyMatrix4(_rel);
    _qs.setFromRotationMatrix(_rel);
    quat.copy(_qs).multiply(_qf);
    if (wb <= 0) return 0;
    // Afloat: the table's place (plus the drift and spread once the simulation has ended) on the live waves.
    const past = simT - sim.duration;
    if (past > 0) {
      const f0 = Math.min(derived.n - 1, Math.max(0, sim.startFrame + sim.duration / SIM_PER_FRAME));
      const dx = sampleDrift(drift, t, 0) - sampleDrift(drift, f0, 0);
      const dz = sampleDrift(drift, t, 1) - sampleDrift(drift, f0, 1);
      const spread = Math.min(SPREAD_MAX, 1 + SPREAD_PER_S * past);
      _pf.x = sim.centre.x + (_pf.x - sim.centre.x) * spread + dx;
      _pf.z = sim.centre.z + (_pf.z - sim.centre.z) * spread + dz;
    }
    waveAt(_pf.x, _pf.z, vis.wave, _w);
    const { h } = c.slot.dims;
    // A container with no restore ahead goes down after a while, by one end.
    const dFrames = (simT - wetAt) / SIM_PER_FRAME;
    const sunk = c.trip.back === null ? smooth((dFrames - FLOAT_FRAMES) / SETTLE_FRAMES) : 0;
    const bob = Math.sin(vis.elapsed * 1.6 + c.j * 1.7) * 0.04 * (1 - sunk);
    _pf.y += _w.h + bob - (2.4 * h + 1.2) * sunk * sunk;
    // Lie on the swell: tilt the table's attitude by the slope of the sea under it.
    _n.set(-_w.dhdx * 0.85, 1, -_w.dhdz * 0.85).normalize();
    _qw.setFromUnitVectors(UP, _n);
    _qf.premultiply(_qw);
    if (sunk > 0) _qf.premultiply(_qk.setFromAxisAngle(_e3.set(Math.cos(c.j), 0, Math.sin(c.j)), sunk * 0.6));
    pos.lerp(_pf, wb);
    quat.slerp(_qf, wb);
    return sunk;
  };

  const prevT = useRef(vis.t);
  useFrame(() => {
    const t = vis.t;
    const pose = shipPose[shipKey];
    const deckMatrix = pose.matrix;
    const pt = prevT.current;
    prevT.current = t;
    const forward = t > pt && t - pt < 3;
    const ringAttr = rings.geometry.getAttribute("aRing") as InstancedBufferAttribute;

    // Simulate what this frame needs, then a little ahead of the playhead within a small time budget.
    let ahead: CutSim | null = null;
    for (const c of plan) {
      const sim = c.sim;
      if (t >= sim.startFrame && !sim.complete) sim.advance((t - sim.startFrame) * SIM_PER_FRAME);
      if (!sim.complete && (ahead === null || sim.startFrame < ahead.startFrame)) ahead = sim;
    }
    if (ahead) ahead.advance(ahead.duration, BACKGROUND_BUDGET_MS);

    let hookOn = false;
    for (let k = 0; k < plan.length; k++) {
      const c = plan[k];
      const { trip, sim } = c;
      const { len, h, w } = c.slot.dims;
      const hoistAge = trip.back === null ? -1e9 : t - trip.back;
      let ringProg = 1;
      _s.set(len, h, w);
      if (t < trip.out || hoistAge >= HOIST_FRAMES) {
        boxes.setMatrixAt(k, ZERO);
      } else if (hoistAge < 0) {
        const sunk = poseAt(c, t, _p, _q, deckMatrix);
        boxes.setMatrixAt(k, sunk >= 0.999 ? ZERO : _m.compose(_p, _q, _s));
        const wetAt = sim.wetAt[c.i];
        if (wetAt !== Infinity) {
          const simT = (t - sim.startFrame) * SIM_PER_FRAME;
          ringProg = (simT - wetAt) / RING_S;
          // Spray when the replay plays forward through the moment it hits the water.
          const wetFrame = sim.startFrame + wetAt / SIM_PER_FRAME;
          if (forward && pt < wetFrame && t >= wetFrame) splash(_p.x, _p.y + 0.3 * h, _p.z, Math.min(1.6, c.slot.spec.size * 1.2));
        }
        // The derrick swings out over the first container before it lifts.
        if (hoistAge >= -CRANE_LEAD && !hookOn) {
          hookOn = true;
          _e3.set(0, h * 0.5, 0).applyQuaternion(_q);
          pose.hook.x = _p.x + _e3.x;
          pose.hook.y = _p.y + _e3.y;
          pose.hook.z = _p.z + _e3.z;
        }
      } else {
        // Lifted back aboard by the derrick: straight up out of the water, across, and down into its slot.
        const u = hoistAge / HOIST_FRAMES;
        poseAt(c, trip.back as number, _p0, _q0, deckMatrix);
        _qs.setFromRotationMatrix(deckMatrix);
        _e3.copy(c.slot.local).applyMatrix4(deckMatrix); // its slot, in the world
        const clear = Math.max(_p0.y, _e3.y) + 2.6;
        if (u < 0.3) {
          _p.set(_p0.x, _p0.y + (clear - _p0.y) * smooth(u / 0.3), _p0.z);
          _q.copy(_q0).slerp(_qs, smooth(u / 0.3) * 0.5);
        } else if (u < 0.75) {
          const e = smooth((u - 0.3) / 0.45);
          _p.set(_p0.x + (_e3.x - _p0.x) * e, clear, _p0.z + (_e3.z - _p0.z) * e);
          _q.copy(_q0).slerp(_qs, 0.5 + 0.5 * e);
        } else {
          _p.set(_e3.x, clear + (_e3.y - clear) * smooth((u - 0.75) / 0.25), _e3.z);
          _q.copy(_qs);
        }
        boxes.setMatrixAt(k, _m.compose(_p, _q, _s));
        hookOn = true;
        // The hook holds the top of the container (along its own up axis).
        _e3.set(0, h * 0.5, 0).applyQuaternion(_q);
        pose.hook.x = _p.x + _e3.x;
        pose.hook.y = _p.y + _e3.y;
        pose.hook.z = _p.z + _e3.z;
      }
      if (ringProg >= 0 && ringProg < 1 && t >= trip.out) {
        const size = (len + w) * (1.5 + 1.4 * ringProg);
        const wi = c.i * 3;
        rings.setMatrixAt(k, _m.makeScale(size, 1, size).setPosition(sim.wetPos[wi], 0, sim.wetPos[wi + 2]));
        ringAttr.setXY(k, ringProg, c.j * 0.137);
      } else {
        rings.setMatrixAt(k, ZERO);
      }
    }
    pose.hook.active = hookOn;
    boxes.instanceMatrix.needsUpdate = true;
    rings.instanceMatrix.needsUpdate = true;
    ringAttr.needsUpdate = true;
    (rings.material as ShaderMaterial).uniforms.uLight.value = foamLight(vis.dayFactor, vis.risk, vis.flash, vis.lantern);
  });

  if (plan.length === 0) return null;
  return (
    <>
      <primitive object={boxes} />
      <primitive object={rings} />
    </>
  );
}

/** The drift table at fractional frame t, component 0 (x) or 1 (z). */
function sampleDrift(d: Float32Array, t: number, comp: 0 | 1): number {
  const n = d.length / 2;
  const x = Math.min(n - 1, Math.max(0, t));
  const i = Math.floor(x);
  const j = Math.min(n - 1, i + 1);
  const u = x - i;
  return d[i * 2 + comp] + (d[j * 2 + comp] - d[i * 2 + comp]) * u;
}
