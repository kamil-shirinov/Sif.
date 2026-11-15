import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { DynamicDrawUsage, Euler, InstancedBufferAttribute, InstancedMesh, Matrix4, PlaneGeometry, Quaternion, ShaderMaterial, Vector3 } from "three";
import { Body, Box, Vec3, World } from "cannon-es";
import { CRANE_LEAD, HOIST_FRAMES, shipOf, THROW_FRAMES, type Derived, type SceneShip } from "../lib/derive";
import { WAVE_GLSL, waveAt, waveUniforms, type WaveSample } from "./waves";
import { vis } from "./vis";
import { crateAboard, crateSlots, SHIP_LAYOUT, shipPose, type CrateSlot } from "./Ship";
import { splash } from "./Particles";
import { BULWARK, containerGeometry, containerMaterial, DECK, HULL_B, HULL_L } from "./shipModel";
import { FOAM_NOISE_GLSL, foamLight } from "./foam";

const ARC = 3.4; // analytic fallback only: how high a thrown crate rises above the straight line from deck to water
/** Frames a container floats high before it settles: one with a restore ahead rides awash, one without sinks. */
export const FLOAT_FRAMES = 24;
/** Frames the settling (or sinking) takes. */
export const SETTLE_FRAMES = 44;
/** Frames (analytic) or seconds (after a simulated splash) the foam ring of a splash lasts. */
const RING_FRAMES = 9;
const RING_SECONDS = 2.2;
// ---- rigid bodies (cannon-es) ----
const GRAVITY = 9.82;
const PUSH_ACCEL = 9; // the shove over the side, units / s^2, while the container is still inboard
const PUSH_SECONDS = 2.2;
const WET_SECONDS = 1.5; // seconds afloat before the simulation hands the container to the drifting float
const PHYS_MAX_SECONDS = 7; // a container that has not reached the water by then is handed over anyway
const BLEND_SECONDS = 1.6; // easing from the simulated attitude to the floating one

const _w: WaveSample = { h: 0, dhdx: 0, dhdz: 0 };
const _p = new Vector3();
const _p0 = new Vector3();
const _e3 = new Vector3();
const _s = new Vector3();
const _q = new Quaternion();
const _q0 = new Quaternion();
const _qs = new Quaternion();
const _e = new Euler();
const _e0 = new Euler();
const _m = new Matrix4();
const _f = new Vec3();
const ZERO = new Matrix4().makeScale(0, 0, 0);
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
  /** It reached the water in the simulation: no analytic plunge, it is already afloat. */
  landed: boolean;
}

/** How far a floating container has drifted `d` frames after it landed (it stays within the derrick's reach). */
const driftRun = (d: number) => 2.2 * (1 - Math.exp(-Math.max(0, d) / 10)) + 0.012 * Math.max(0, d);

/**
 * Where a container floats `d` frames after it landed, and how it lies on the swell. It rides high for a while, then
 * settles: awash if a restore will hoist it back, otherwise down by one end until it is gone.
 * Returns how much of it has gone under for good (1 = sunk, not drawn).
 */
function floatAt(c: Floater, d: number, out: Vector3, rot: Euler): number {
  const { h } = c.slot.dims;
  out.copy(c.land).addScaledVector(c.drift, driftRun(d));
  waveAt(out.x, out.z, vis.wave, _w);
  const settle = smooth((d - FLOAT_FRAMES) / SETTLE_FRAMES);
  const sunk = c.returns ? 0 : settle;
  // Centre of the box relative to the surface: 38% of it above water at first, a tenth once awash.
  const ride = -0.12 * h - (c.returns ? 0.28 * h * settle : (2.4 * h + 1.2) * settle * settle);
  const plunge = c.landed ? 0 : -0.75 * h * Math.exp(-d / 1.4) * Math.cos(d * 2.1);
  const bob = Math.sin(vis.elapsed * 1.6 + c.j) * 0.05 * (1 - sunk);
  out.y = _w.h + ride + plunge + bob;
  const follow = 0.85 * (1 - 0.6 * sunk);
  rot.set(-Math.atan(_w.dhdz) * follow + c.roll * (1 + sunk), c.yaw + d * 0.004 * (c.roll > 0 ? 1 : -1), Math.atan(_w.dhdx) * follow + c.trim + sunk * 0.75 * Math.sign(c.trim || 1));
  return sunk;
}

/** Per-trip simulation state. */
interface Sim {
  body: Body;
  active: boolean;
  since: number; // seconds simulated
  wet: number; // seconds since it first touched the water (-1: still dry)
  /** After the hand-over: the attitude it had, and when (wall clock), to ease into the floating attitude. */
  q0: Quaternion;
  blendFrom: number;
  /** Where and when (wall clock) it hit the water, for the foam ring. */
  splashX: number;
  splashZ: number;
  splashAt: number;
}

/**
 * Containers off the deck. At each cut event the right number of containers are shoved over the side as rigid
 * bodies (cannon-es): they slide, catch the rail and tip, knock each other, fall, hit the water with a splash and a
 * ring of foam, and bob. Then they float and drift on the waves and slowly settle (sink, if no restore brings them
 * back). At each restore event the ship's derrick lifts them out one at a time and sets them back in their slots.
 * One instance per crate trip (derived.ships[ship].trips), so several cuts and restores per bundle just work.
 *
 * The simulation runs only while the replay moves forward through a cut. After a seek, or on a paused frame, the
 * containers take their analytic places (an arc, then the same float), so every frame can still be shown on its own.
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
    const side = new Vector3(sin, 0, cos); // ship's local +z (starboard): the side facing the camera
    return ship.trips
      .map((trip, j) => {
        const slot = slots[trip.crate];
        if (!slot) return null;
        const r1 = ((j * 7919) % 97) / 97;
        const r2 = ((j * 104729) % 89) / 89;
        const deck = toWorld(slot.local.x, slot.local.z); // y is the live deck height, set per frame
        const land = toWorld(slot.local.x + (r1 - 0.5) * 2, 3.6 + r2 * 2.6);
        const drift = side.clone().multiplyScalar(0.5 + 0.4 * r1).add(new Vector3(-0.3 + 0.6 * r2, 0, 0.1));
        const floater: Floater = { land, drift, slot, roll: (r1 - 0.5) * 0.3, trim: (r2 - 0.5) * 0.24, yaw: lay.heading + (r1 - 0.5) * 1.4, j, returns: trip.back !== null, landed: false };
        const { len, h, w } = slot.dims;
        const body = new Body({ mass: 1, shape: new Box(new Vec3(len / 2, h / 2, w / 2)), linearDamping: 0.02, angularDamping: 0.05 });
        const sim: Sim = { body, active: false, since: 0, wet: -1, q0: new Quaternion(), blendFrom: -1e9, splashX: 0, splashZ: 0, splashAt: -1e9 };
        return { trip, slot, deck, floater, sim, spinX: (r1 - 0.5) * 3.2, spinZ: 0.8 + r2 * 1.4, j };
      })
      .filter((c): c is NonNullable<typeof c> => c !== null);
  }, [lay, slots, ship]);

  // The rigid-body world: the deck and its two rails and the containers still stowed are kinematic (they follow the
  // ship); a container becomes a dynamic body the moment it is cut loose.
  const phys = useMemo(() => {
    const world = new World({ gravity: new Vec3(0, -GRAVITY, 0) });
    world.allowSleep = false;
    world.defaultContactMaterial.friction = 0.25;
    world.defaultContactMaterial.restitution = 0.05;
    const kin = (half: Vec3) => {
      const b = new Body({ mass: 0, type: Body.KINEMATIC, shape: new Box(half) });
      world.addBody(b);
      return b;
    };
    // Hull-local centres: the hatch top (y = 0.16 is where the containers stand) and the bulwark each side.
    const fixed = [
      { body: kin(new Vec3(HULL_L / 2, 0.5, HULL_B / 2 - 0.12)), local: new Vector3(0, 0.16 - 0.5, 0) },
      // Each rail from below the hatch top up to the top of the bulwark: 0.26 above the containers' feet.
      { body: kin(new Vec3(HULL_L / 2, (BULWARK + 0.1) / 2, 0.06)), local: new Vector3(0, (BULWARK - 0.1) / 2, HULL_B / 2 - 0.06) },
      { body: kin(new Vec3(HULL_L / 2, (BULWARK + 0.1) / 2, 0.06)), local: new Vector3(0, (BULWARK - 0.1) / 2, -(HULL_B / 2 - 0.06)) },
      // The bridge front and the forecastle break: containers do not slide along the deck into them.
      { body: kin(new Vec3(0.3, 1.2, HULL_B / 2)), local: new Vector3(DECK.x0 - 0.75, 1.2, 0) },
      { body: kin(new Vec3(0.3, 0.6, HULL_B / 2)), local: new Vector3(DECK.x1 + 0.6, 0.6, 0) },
    ];
    const stowed = slots.map((s) => ({ body: new Body({ mass: 0, type: Body.KINEMATIC, shape: new Box(new Vec3(s.dims.len / 2, s.dims.h / 2, s.dims.w / 2)) }), local: s.local, inWorld: false }));
    return { world, fixed, stowed, live: 0 };
  }, [slots]);

  // A new plan (another bundle, a move in Survive) drops whatever the old one was simulating.
  useEffect(
    () => () => {
      for (const c of plan) {
        if (!c.sim.active) continue;
        phys.world.removeBody(c.sim.body);
        c.sim.active = false;
        phys.live--;
      }
    },
    [plan, phys],
  );

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

  const prevT = useRef(vis.t);
  useFrame(() => {
    const t = vis.t;
    const pose = shipPose[shipKey];
    const deckY = pose.y;
    const pt = prevT.current;
    prevT.current = t;
    // The simulation lives only while the replay runs forward (or stands still); a seek drops it.
    const seeked = t < pt || t - pt > 3;
    const forward = t > pt && !seeked;
    const ringAttr = rings.geometry.getAttribute("aRing") as InstancedBufferAttribute;
    _qs.setFromRotationMatrix(pose.matrix); // the ship's attitude
    const dt = Math.min(vis.dt, 1 / 20);

    // ---- start and stop simulated bodies ----
    for (let k = 0; k < plan.length; k++) {
      const c = plan[k];
      const sim = c.sim;
      if (seeked && sim.active) {
        phys.world.removeBody(sim.body);
        sim.active = false;
        phys.live--;
      }
      if (seeked) {
        c.floater.landed = false;
        sim.blendFrom = -1e9;
        sim.splashAt = -1e9;
      }
      if (forward && !sim.active && pt < c.trip.out && t >= c.trip.out) {
        // Cut loose: a dynamic body where the container stands, moving with the ship.
        const b = sim.body;
        _p.copy(c.slot.local).applyMatrix4(pose.matrix);
        b.position.set(_p.x, _p.y, _p.z);
        b.quaternion.set(_qs.x, _qs.y, _qs.z, _qs.w);
        b.velocity.set(0, 0, 0);
        b.angularVelocity.set(0, 0, 0);
        phys.world.addBody(b);
        sim.active = true;
        sim.since = 0;
        sim.wet = -1;
        c.floater.landed = false;
        phys.live++;
      }
    }

    if (phys.live > 0) {
      // Kinematic parts follow the ship; stowed containers are obstacles only while they are aboard.
      for (const f of phys.fixed) {
        _p.copy(f.local).applyMatrix4(pose.matrix);
        f.body.position.set(_p.x, _p.y, _p.z);
        f.body.quaternion.set(_qs.x, _qs.y, _qs.z, _qs.w);
      }
      for (let i = 0; i < phys.stowed.length; i++) {
        const s = phys.stowed[i];
        const aboard = crateAboard(ship, i, t);
        if (aboard !== s.inWorld) {
          if (aboard) phys.world.addBody(s.body);
          else phys.world.removeBody(s.body);
          s.inWorld = aboard;
        }
        if (!aboard) continue;
        _p.copy(s.local).applyMatrix4(pose.matrix);
        s.body.position.set(_p.x, _p.y, _p.z);
        s.body.quaternion.set(_qs.x, _qs.y, _qs.z, _qs.w);
      }
      // Forces: the shove over the starboard side while inboard, then buoyancy and drag in the water.
      _e3.setFromMatrixColumn(pose.matrix, 2).normalize(); // starboard
      for (let k = 0; k < plan.length; k++) {
        const c = plan[k];
        const sim = c.sim;
        if (!sim.active) continue;
        const b = sim.body;
        const { h } = c.slot.dims;
        sim.since += dt;
        _p.set(b.position.x, b.position.y, b.position.z).applyMatrix4(pose.inv);
        if (sim.since < PUSH_SECONDS && _p.z < HULL_B / 2 + 0.5 && sim.wet < 0) {
          // Harder if it has hung up on the rail or a neighbour.
          const a = PUSH_ACCEL * (1 + Math.max(0, sim.since - 0.8));
          _f.set(_e3.x * a, 2.2 + Math.max(0, sim.since - 0.8) * 5, _e3.z * a);
          b.applyForce(_f);
        }
        waveAt(b.position.x, b.position.z, vis.wave, _w);
        const depth = _w.h - (b.position.y - h / 2);
        if (depth > 0) {
          const sub = Math.min(1, depth / h);
          if (sim.wet < 0) {
            sim.wet = 0;
            sim.splashX = b.position.x;
            sim.splashZ = b.position.z;
            sim.splashAt = vis.elapsed;
            splash(b.position.x, _w.h + 0.2, b.position.z, Math.min(1.6, c.slot.spec.size * 1.2));
          }
          // Floats with about 60% of its height under water; the water takes the speed and the spin out of it.
          _f.set(0, GRAVITY * sub * 1.65, 0);
          b.applyForce(_f);
          const drag = Math.exp(-dt * 3.2 * sub);
          b.velocity.scale(drag, b.velocity);
          b.angularVelocity.scale(Math.exp(-dt * 4.5 * sub), b.angularVelocity);
        }
        if (sim.wet >= 0) sim.wet += dt;
      }
      phys.world.step(1 / 90, dt, 4);
      // Hand over to the drifting float once it has been afloat a while (or has taken too long).
      for (let k = 0; k < plan.length; k++) {
        const c = plan[k];
        const sim = c.sim;
        if (!sim.active) continue;
        const b = sim.body;
        if (sim.wet < WET_SECONDS && sim.since < PHYS_MAX_SECONDS && b.position.y > -20) continue;
        const d = t - c.trip.out - THROW_FRAMES;
        // The float continues from exactly where the simulation left it.
        c.floater.land.set(b.position.x, 0, b.position.z).addScaledVector(c.floater.drift, -driftRun(d));
        _q.set(b.quaternion.x, b.quaternion.y, b.quaternion.z, b.quaternion.w);
        sim.q0.copy(_q);
        sim.blendFrom = vis.elapsed;
        c.floater.landed = true;
        phys.world.removeBody(b);
        sim.active = false;
        phys.live--;
      }
    }

    // ---- draw ----
    let hookOn = false;
    for (let k = 0; k < plan.length; k++) {
      const c = plan[k];
      const { trip, sim } = c;
      const { len, h, w } = c.slot.dims;
      const age = t - trip.out;
      const hoistAge = trip.back === null ? -1e9 : t - trip.back;
      let ringProg = 1;
      let ringX = c.floater.land.x;
      let ringZ = c.floater.land.z;
      _s.set(len, h, w);
      if (age < 0 || hoistAge >= HOIST_FRAMES) {
        boxes.setMatrixAt(k, ZERO);
      } else if (sim.active) {
        // Simulated: falling, tumbling, bobbing.
        const b = sim.body;
        _p.set(b.position.x, b.position.y, b.position.z);
        _q.set(b.quaternion.x, b.quaternion.y, b.quaternion.z, b.quaternion.w);
        boxes.setMatrixAt(k, _m.compose(_p, _q, _s));
      } else if (hoistAge < 0) {
        const d = age - THROW_FRAMES;
        if (d < 0 && !c.floater.landed) {
          // Analytic fallback (a paused or scrubbed frame inside a throw): a tumbling arc from the deck to the water.
          const u = age / THROW_FRAMES;
          const startY = deckY + c.slot.local.y;
          floatAt(c.floater, 0, _p0, _e0);
          const e = u * u * 0.35 + u * 0.65;
          _p.set(c.deck.x + (c.floater.land.x - c.deck.x) * e, 0, c.deck.z + (c.floater.land.z - c.deck.z) * e);
          _p.y = startY + (_p0.y + 0.75 * h - startY) * u * u + Math.sin(Math.PI * Math.min(1, u * 1.15)) * ARC * (1 - u * 0.4);
          const tumble = Math.sin(Math.PI * u);
          _e.set(tumble * c.spinX + _e0.x * u, lay.heading + (_e0.y - lay.heading) * u, tumble * c.spinZ + _e0.z * u);
          boxes.setMatrixAt(k, _m.compose(_p, _q.setFromEuler(_e), _s));
        } else {
          // In the water: floating, drifting, settling, sinking.
          const sunk = floatAt(c.floater, d, _p, _e);
          _q.setFromEuler(_e);
          const blend = smooth((vis.elapsed - sim.blendFrom) / BLEND_SECONDS);
          if (blend < 1) _q.slerpQuaternions(sim.q0, _q, blend);
          if (sunk >= 0.999) boxes.setMatrixAt(k, ZERO);
          else boxes.setMatrixAt(k, _m.compose(_p, _q, _s));
          if (!c.floater.landed) ringProg = d / RING_FRAMES;
          // The derrick swings out over the first container before it lifts.
          if (hoistAge >= -CRANE_LEAD && !hookOn) {
            hookOn = true;
            pose.hook.x = _p.x;
            pose.hook.y = _p.y + h * 0.5;
            pose.hook.z = _p.z;
          }
        }
      } else {
        // Lifted back aboard by the derrick: straight up out of the water, across, and down into its slot.
        const u = hoistAge / HOIST_FRAMES;
        floatAt(c.floater, Math.max(0, (trip.back as number) - trip.out - THROW_FRAMES), _p0, _e0);
        _q0.setFromEuler(_e0);
        _e3.copy(c.slot.local).applyMatrix4(pose.matrix); // its slot, in the world
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
      // Foam ring: where it hit the water in the simulation, else where the analytic arc lands.
      const wall = (vis.elapsed - sim.splashAt) / RING_SECONDS;
      if (wall >= 0 && wall < 1) {
        ringProg = wall;
        ringX = sim.splashX;
        ringZ = sim.splashZ;
      }
      if (ringProg >= 0 && ringProg < 1 && age >= 0) {
        const size = (len + w) * (1.5 + 1.4 * ringProg);
        rings.setMatrixAt(k, _m.makeScale(size, 1, size).setPosition(ringX, 0, ringZ));
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
