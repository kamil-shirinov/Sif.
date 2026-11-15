import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import {
  CylinderGeometry,
  DynamicDrawUsage,
  Euler,
  InstancedBufferAttribute,
  InstancedMesh,
  Matrix4,
  MeshBasicMaterial,
  PlaneGeometry,
  Quaternion,
  ShaderMaterial,
  Vector3,
} from "three";
import { HOIST_FRAMES, shipOf, THROW_FRAMES, type Derived, type SceneShip } from "../lib/derive";
import { WAVE_GLSL, waveAt, waveUniforms, type WaveSample } from "./waves";
import { vis } from "./vis";
import { crateSlots, SHIP_LAYOUT, shipPose, type CrateSlot } from "./Ship";
import { splash } from "./Particles";
import { containerGeometry, containerMaterial, MAST_TOP, MAST_X } from "./shipModel";
import { FOAM_NOISE_GLSL, foamLight } from "./foam";

const SWING = 2.2; // how high a hoisted crate swings above its straight path
const ARC = 3.4; // how high a thrown crate rises above the straight line from deck to water
/** Frames a container floats high before it settles: one with a restore ahead rides awash, one without sinks. */
export const FLOAT_FRAMES = 24;
/** Frames the settling (or sinking) takes. */
export const SETTLE_FRAMES = 44;
/** Frames the foam ring of a splash lasts. */
const RING_FRAMES = 9;

const _w: WaveSample = { h: 0, dhdx: 0, dhdz: 0 };
const _p = new Vector3();
const _p0 = new Vector3();
const _a = new Vector3();
const _b = new Vector3();
const _s = new Vector3();
const _q = new Quaternion();
const _e = new Euler();
const _e0 = new Euler();
const _m = new Matrix4();
const ZERO = new Matrix4().makeScale(0, 0, 0);
const UP = new Vector3(0, 1, 0);
const smooth = (u: number) => {
  const t = Math.min(1, Math.max(0, u));
  return t * t * (3 - 2 * t);
};

interface Floater {
  land: Vector3;
  drift: Vector3;
  slot: CrateSlot;
  /** Small fixed list and trim, and the heading it settles on. */
  roll: number;
  trim: number;
  yaw: number;
  j: number;
  /** A restore event brings this crate back: it stays afloat (awash) until then instead of sinking. */
  returns: boolean;
}

/**
 * Where a container floats `d` frames after it landed, and how it lies on the swell. It plunges, bobs up, rides
 * high for a while, then settles: awash if a restore will hoist it back, otherwise down by one end until it is gone.
 * Returns how much of it has gone under for good (1 = sunk, not drawn).
 */
function floatAt(c: Floater, d: number, out: Vector3, rot: Euler): number {
  const { h } = c.slot.dims;
  // Thrown clear, then carried slowly by the sea.
  const run = 5 * (1 - Math.exp(-d / 7)) + d * 0.1;
  out.copy(c.land).addScaledVector(c.drift, run);
  waveAt(out.x, out.z, vis.wave, _w);
  const settle = smooth((d - FLOAT_FRAMES) / SETTLE_FRAMES);
  const sunk = c.returns ? 0 : settle;
  // Centre of the box relative to the surface: 38% of it above water at first, a tenth once awash.
  const ride = -0.12 * h - (c.returns ? 0.28 * h * settle : (2.4 * h + 1.2) * settle * settle);
  const plunge = -0.75 * h * Math.exp(-d / 1.4) * Math.cos(d * 2.1);
  const bob = Math.sin(vis.elapsed * 1.6 + c.j) * 0.05 * (1 - sunk);
  out.y = _w.h + ride + plunge + bob;
  const follow = 0.85 * (1 - 0.6 * sunk);
  rot.set(-Math.atan(_w.dhdz) * follow + c.roll * (1 + sunk), c.yaw + d * 0.004 * (c.roll > 0 ? 1 : -1), Math.atan(_w.dhdx) * follow + c.trim + sunk * 0.75 * Math.sign(c.trim || 1));
  return sunk;
}

/**
 * Containers in the water. At each cut event a container is thrown over the side on an arc, hits the water with a
 * splash and a ring of foam, floats and bobs, then slowly settles (sinks, if no restore brings it back). At each
 * restore event it is hoisted back aboard on a line from the mast head and lands on its place on deck.
 * One instance per crate trip (derived.ships[ship].trips), so several cuts and restores per bundle just work.
 */
export function Jettison({ shipKey, derived }: { shipKey: SceneShip; derived: Derived }) {
  const ship = shipOf(derived, shipKey);
  const lay = SHIP_LAYOUT[shipKey];
  const slots = useMemo(() => crateSlots(derived.crates), [derived.crates]);

  // Precompute per-trip world-space start and landing points and each crate's own small differences.
  const plan = useMemo(() => {
    const cos = Math.cos(lay.heading);
    const sin = Math.sin(lay.heading);
    const toWorld = (lx: number, lz: number) => new Vector3(lay.x + lx * cos + lz * sin, 0, lay.z - lx * sin + lz * cos);
    const side = new Vector3(sin, 0, cos); // ship's local +z: the side facing the camera
    const mast = toWorld(MAST_X, 0);
    return ship.trips
      .map((trip, j) => {
        const slot = slots[trip.crate];
        if (!slot) return null;
        const r1 = ((j * 7919) % 97) / 97;
        const r2 = ((j * 104729) % 89) / 89;
        const deck = toWorld(slot.local.x, slot.local.z); // y is the live deck height, set per frame
        const land = toWorld(slot.local.x + (r1 - 0.5) * 3.5, 3.9 + r2 * 3.6);
        const drift = side.clone().multiplyScalar(0.45 + 0.4 * r1).add(new Vector3(-0.25 + 0.5 * r2, 0, 0.1));
        const floater: Floater = { land, drift, slot, roll: (r1 - 0.5) * 0.3, trim: (r2 - 0.5) * 0.24, yaw: lay.heading + (r1 - 0.5) * 1.4, j, returns: trip.back !== null };
        return { trip, slot, deck, mast, floater, spinX: (r1 - 0.5) * 3.2, spinZ: 0.8 + r2 * 1.4, j };
      })
      .filter((c): c is NonNullable<typeof c> => c !== null);
  }, [lay, slots, ship]);

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
  const ropes = useMemo(() => {
    const im = new InstancedMesh(new CylinderGeometry(0.045, 0.045, 1, 5), new MeshBasicMaterial({ color: "#2b2622" }), count);
    im.instanceMatrix.setUsage(DynamicDrawUsage);
    for (let k = 0; k < count; k++) im.setMatrixAt(k, ZERO);
    im.frustumCulled = false;
    return im;
  }, [count]);
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
          float prog = vRing.x;
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
      ropes.geometry.dispose();
      (ropes.material as MeshBasicMaterial).dispose();
      ropes.dispose();
      rings.geometry.dispose();
      (rings.material as ShaderMaterial).dispose();
      rings.dispose();
    },
    [boxes, ropes, rings],
  );

  const prevT = useRef(vis.t);
  useFrame(() => {
    const t = vis.t;
    const deckY = shipPose[shipKey].y;
    // Spray only while the replay plays forward through a landing (not on a seek): a crate hits the water, or
    // leaves it on a hoist line. The foam ring is a function of the playhead, so it also shows paused.
    const pt = prevT.current;
    prevT.current = t;
    const playing = t > pt && t - pt < 3;
    const ringAttr = rings.geometry.getAttribute("aRing") as InstancedBufferAttribute;
    let anyRope = false;
    for (let k = 0; k < plan.length; k++) {
      const c = plan[k];
      const { trip } = c;
      const { len, h, w } = c.slot.dims;
      const age = t - trip.out;
      const hoistAge = trip.back === null ? -1 : t - trip.back;
      let ropeOn = false;
      let ringProg = 1;
      if (age < 0 || hoistAge >= HOIST_FRAMES) {
        boxes.setMatrixAt(k, ZERO);
      } else {
        const startY = deckY + c.slot.local.y;
        _s.set(len, h, w);
        if (playing) {
          const land = trip.out + THROW_FRAMES;
          if (pt < land && t >= land) {
            floatAt(c.floater, 0, _p0, _e0);
            splash(_p0.x, _p0.y + 0.4 * h, _p0.z, Math.min(1.6, c.slot.spec.size * 1.2));
          } else if (trip.back !== null && pt < trip.back && t >= trip.back) {
            floatAt(c.floater, Math.max(0, trip.back - trip.out - THROW_FRAMES), _p0, _e0);
            splash(_p0.x, _p0.y, _p0.z, 0.4);
          }
        }

        if (age < THROW_FRAMES) {
          // Over the side: a tumbling arc from the deck to the water.
          const u = age / THROW_FRAMES;
          floatAt(c.floater, 0, _p0, _e0);
          const e = u * u * 0.35 + u * 0.65; // leaves the deck with a push, falls faster
          _p.set(c.deck.x + (c.floater.land.x - c.deck.x) * e, 0, c.deck.z + (c.floater.land.z - c.deck.z) * e);
          _p.y = startY + (_p0.y + 0.75 * h - startY) * u * u + Math.sin(Math.PI * Math.min(1, u * 1.15)) * ARC * (1 - u * 0.4);
          const tumble = Math.sin(Math.PI * u);
          _e.set(tumble * c.spinX + _e0.x * u, lay.heading + (_e0.y - lay.heading) * u, tumble * c.spinZ + _e0.z * u);
          boxes.setMatrixAt(k, _m.compose(_p, _q.setFromEuler(_e), _s));
        } else if (hoistAge < 0) {
          // In the water: floating, settling, sinking.
          const d = age - THROW_FRAMES;
          const sunk = floatAt(c.floater, d, _p, _e);
          if (sunk >= 0.999) boxes.setMatrixAt(k, ZERO);
          else boxes.setMatrixAt(k, _m.compose(_p, _q.setFromEuler(_e), _s));
          ringProg = d / RING_FRAMES;
        } else {
          // Hoisted back aboard: up from the water, swung over the rail, lowered to its place on deck.
          const u = hoistAge / HOIST_FRAMES;
          const e = smooth(u);
          floatAt(c.floater, Math.max(0, (trip.back as number) - trip.out - THROW_FRAMES), _p0, _e0);
          _p.set(_p0.x + (c.deck.x - _p0.x) * e, 0, _p0.z + (c.deck.z - _p0.z) * e);
          _p.y = _p0.y + (startY - _p0.y) * e + Math.sin(Math.PI * u) * SWING;
          _e.set(_e0.x * (1 - e), _e0.y * (1 - e) + lay.heading * e, _e0.z * (1 - e));
          boxes.setMatrixAt(k, _m.compose(_p, _q.setFromEuler(_e), _s));
          // The line from the mast head to the top of the crate.
          _a.set(c.mast.x, deckY + MAST_TOP, c.mast.z);
          _b.set(_p.x, _p.y + h * 0.5, _p.z);
          const lenR = _a.distanceTo(_b);
          if (lenR > 0.01) {
            ropeOn = true;
            _q.setFromUnitVectors(UP, _p0.copy(_b).sub(_a).normalize());
            _p0.copy(_a).add(_b).multiplyScalar(0.5);
            ropes.setMatrixAt(k, _m.compose(_p0, _q, _s.set(1, lenR, 1)));
          }
        }
      }
      if (!ropeOn) ropes.setMatrixAt(k, ZERO);
      anyRope ||= ropeOn;
      if (ringProg >= 0 && ringProg < 1) {
        const size = (len + w) * (1.5 + 1.4 * ringProg);
        _p.copy(c.floater.land);
        rings.setMatrixAt(k, _m.makeScale(size, 1, size).setPosition(_p.x, 0, _p.z));
        ringAttr.setXY(k, ringProg, c.j * 0.137);
      } else {
        rings.setMatrixAt(k, ZERO);
      }
    }
    boxes.instanceMatrix.needsUpdate = true;
    ropes.instanceMatrix.needsUpdate = true;
    ropes.visible = anyRope;
    rings.instanceMatrix.needsUpdate = true;
    ringAttr.needsUpdate = true;
    (rings.material as ShaderMaterial).uniforms.uLight.value = foamLight(vis.dayFactor, vis.risk, vis.flash, vis.lantern);
  });

  if (plan.length === 0) return null;
  return (
    <>
      <primitive object={boxes} />
      <primitive object={ropes} />
      <primitive object={rings} />
    </>
  );
}
