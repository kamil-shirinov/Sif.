import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import {
  CanvasTexture,
  Color,
  DoubleSide,
  DynamicDrawUsage,
  Group,
  InstancedMesh,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  PlaneGeometry,
  PointLight,
  Quaternion,
  ShaderMaterial,
  SRGBColorSpace,
  Vector3,
} from "three";
import type { CrateSpec, Derived, SceneShip, ShipDerived } from "../lib/derive";
import { HOIST_FRAMES, SINK_FRAMES, sampleAt, shipOf } from "../lib/derive";
import { WAVE_GLSL, waveAt, waveUniforms, type WaveSample } from "./waves";
import { vis } from "./vis";
import { placeLabel } from "./labels";
import { rnd, spawnParticle, splash, PK } from "./Particles";
import { foamLight } from "./foam";
import { Wreck } from "./Wreck";
import {
  bridgeTextures,
  containerColor,
  containerDims,
  containerGeometry,
  containerMaterial,
  DECK,
  HULL_L,
  makeDeckGeometry,
  makeDetailGeometry,
  makeHullGeometry,
  makeHullMaterial,
  makeRigGeometry,
  makeSailGeometry,
  MAST_TOP,
  MAST_X,
  shapeSail,
  windowTextures,
  YARD_Y,
} from "./shipModel";

// ---------- layout ----------
export const SHIP_LAYOUT: Record<SceneShip, { x: number; z: number; heading: number }> = {
  prepared: { x: -9, z: 4, heading: 0.22 },
  unprepared: { x: 10, z: -5, heading: -0.16 },
  // Survive mode: one ship, mid-frame.
  player: { x: 0, z: 0, heading: 0.14 },
};
/** Each ship's livery: topsides and funnel. Green followed the alarm, red ignored it, gold is the player's. */
const LIVERY: Record<SceneShip, { hull: string; funnel: string }> = {
  prepared: { hull: "#22706a", funnel: "#2fa57f" },
  unprepared: { hull: "#a04233", funnel: "#d04a32" },
  player: { hull: "#27405e", funnel: "#e0a81c" },
};

const FREEBOARD_MAX = 1.95; // deck height above water with a full margin buffer (riding high)
const FREEBOARD_MIN = 0.2; // no margin buffer left: deck nearly awash
// Lanterns: masthead (white), port (red, left) and starboard (green, right) lights. Lit as daylight fails
// (vis.lantern: dusk, night, and any stretch where the market is closed). HDR colours so the bloom picks them up.
const LAMP_OFF = new Color("#4a463c");
const LAMP_MAST_ON = new Color(9, 6.8, 3.2);
const LAMP_PORT_ON = new Color(8, 0.5, 0.4);
const LAMP_STARBOARD_ON = new Color(0.5, 7, 1.6);
const LANTERN_LIGHT = 60; // candela of the masthead point light at full lantern
const WINDOW_GLOW = 2.4; // emissive strength of the lit windows at night (under the bloom threshold)

// ---------- shared geometry and materials (built once, used by every ship) ----------
let shared: ReturnType<typeof buildShared> | null = null;
function buildShared() {
  const win = windowTextures();
  const br = bridgeTextures();
  const white = new MeshStandardMaterial({ color: "#e9e7e1", roughness: 0.55, metalness: 0.02 });
  const house = new MeshStandardMaterial({ map: win.map, emissiveMap: win.glow, emissive: new Color(1, 1, 1), emissiveIntensity: 0, roughness: 0.55, metalness: 0.02 });
  const wheel = new MeshStandardMaterial({ map: br.map, emissiveMap: br.glow, emissive: new Color(1, 1, 1), emissiveIntensity: 0, roughness: 0.45, metalness: 0.05 });
  // Sail cloth: canvas with sewn panels.
  const c = document.createElement("canvas");
  c.width = 128;
  c.height = 128;
  const g = c.getContext("2d")!;
  g.fillStyle = "#efe7d4";
  g.fillRect(0, 0, 128, 128);
  g.strokeStyle = "rgba(120,100,70,0.35)";
  g.lineWidth = 1;
  for (let k = 1; k < 7; k++) {
    g.beginPath();
    g.moveTo((k * 128) / 7, 0);
    g.lineTo((k * 128) / 7, 128);
    g.stroke();
  }
  g.fillStyle = "rgba(130,105,70,0.16)";
  g.fillRect(0, 0, 128, 6);
  g.fillRect(0, 120, 128, 8);
  const cloth = new CanvasTexture(c);
  cloth.colorSpace = SRGBColorSpace;
  return {
    hull: makeHullGeometry(),
    deck: makeDeckGeometry(),
    rig: makeRigGeometry(),
    detail: makeDetailGeometry(),
    white,
    // BoxGeometry faces: +x, -x, +y, -y, +z, -z. Windows on the four walls, plain plating on roof and floor.
    houseMats: [house, house, white, white, house, house],
    wheelMats: [wheel, wheel, white, white, wheel, wheel],
    glow: [house, wheel],
    // Double-sided, like the hull: no face of the ship is see-through from any angle (under the deck, inside the
    // crow's nest, along the open-ended stays).
    deckMat: new MeshStandardMaterial({ color: "#5d6f62", roughness: 0.85, metalness: 0.0, side: DoubleSide }),
    rigMat: new MeshStandardMaterial({ color: "#3b3f44", roughness: 0.6, metalness: 0.3, side: DoubleSide }),
    darkMat: new MeshStandardMaterial({ color: "#1b1f24", roughness: 0.6, metalness: 0.2 }),
    sailMat: new MeshStandardMaterial({ map: cloth, roughness: 0.95, metalness: 0, side: DoubleSide }),
  };
}

function makeWake(): Mesh {
  const g = new PlaneGeometry(1, 1, 6, 30);
  g.rotateX(-Math.PI / 2);
  const mat = new ShaderMaterial({
    uniforms: { ...waveUniforms, uOpacity: { value: 0 }, uTime: { value: 0 }, uLight: { value: 1 } },
    vertexShader: /* glsl */ `
      ${WAVE_GLSL}
      varying vec2 vUv;
      void main() {
        vUv = uv;
        vec3 pos = position;
        float along = 1.0 - uv.y;                 // 0 at stern, 1 at far end
        pos.x = -along * 30.0;                    // trail behind the stern (local -x)
        pos.z *= 1.6 + along * 9.0;               // V-shaped spread
        vec4 wp = modelMatrix * vec4(pos, 1.0);
        wp.y = waveEval(wp.xz).x + 0.08;
        gl_Position = projectionMatrix * viewMatrix * wp;
      }`,
    fragmentShader: /* glsl */ `
      uniform float uOpacity; uniform float uTime; uniform float uLight;
      varying vec2 vUv;
      float hash(vec2 p) { return fract(sin(dot(p, vec2(41.3, 289.1))) * 15731.7); }
      void main() {
        float along = 1.0 - vUv.y;
        float across = abs(vUv.x - 0.5) * 2.0;
        float edge = smoothstep(1.0, 0.55, across) * (0.35 + 0.65 * smoothstep(0.2, 0.9, across));
        float n = hash(floor(vec2(vUv.x * 40.0, vUv.y * 120.0 + uTime * 6.0)));
        float a = uOpacity * edge * (1.0 - along) * (0.55 + 0.45 * n);
        gl_FragColor = vec4(vec3(0.92, 0.95, 0.97) * uLight, a);
      }`,
    transparent: true,
    depthWrite: false,
  });
  const m = new Mesh(g, mat);
  m.position.set(-HULL_L / 2 + 0.6, 0, 0);
  m.frustumCulled = false;
  return m;
}

// ---------- crate layout ----------
export interface CrateSlot {
  spec: CrateSpec;
  local: Vector3; // centre on deck, hull-local
  color: Color;
  /** Container length (along the hull), height and width in scene units. */
  dims: { len: number; h: number; w: number };
}

/** Containers stowed on the hatch: rows across the beam, bays along the hull, tiers on top of each other. */
export function crateSlots(crates: CrateSpec[]): CrateSlot[] {
  if (crates.length === 0) return [];
  const dims = containerDims(crates[0].size);
  const gapL = dims.len * 1.035;
  const gapW = dims.w * 1.05;
  const bays = Math.max(1, Math.floor((DECK.x1 - DECK.x0) / gapL));
  const rows = Math.max(1, Math.floor((DECK.z1 - DECK.z0) / gapW));
  const per = bays * rows;
  const cx = (DECK.x0 + DECK.x1) / 2;
  return crates.map((spec, k) => {
    const tier = Math.floor(k / per);
    const r = k % per;
    const bay = Math.floor(r / rows);
    const row = r % rows;
    const local = new Vector3(cx + (bay - (bays - 1) / 2) * gapL, 0.16 + dims.h / 2 + tier * dims.h * 1.01, (row - (rows - 1) / 2) * gapW);
    return { spec, local, color: containerColor(spec.positionIndex, k), dims };
  });
}

/**
 * Is crate `crate` on deck at playhead t? It leaves at each trip's `out` frame and is back on deck
 * once its hoist (which starts at `back`) has finished. Trips come from the cut and restore events.
 */
export function crateAboard(ship: ShipDerived, crate: number, t: number): boolean {
  const trips = ship.tripsByCrate[crate];
  if (!trips) return true;
  for (const tr of trips) {
    if (t >= tr.out && (tr.back === null || t < tr.back + HOIST_FRAMES)) return false;
  }
  return true;
}

/**
 * Live pose of each ship, shared with the containers in the water (Jettison.tsx): the deck's world height, the hull's
 * world matrix and its inverse, and the point the derrick's hook should be at (the top of the container being lifted).
 */
export interface ShipPose {
  y: number;
  matrix: Matrix4;
  inv: Matrix4;
  hook: { active: boolean; x: number; y: number; z: number };
}
const newPose = (): ShipPose => ({ y: 1, matrix: new Matrix4(), inv: new Matrix4(), hook: { active: false, x: 0, y: 0, z: 0 } });
export const shipPose: Record<SceneShip, ShipPose> = { prepared: newPose(), unprepared: newPose(), player: newPose() };

// The derrick: a boom stepped on the mast, with a topping lift to the mast head and a cargo runner down to the hook.
const BOOM_PIVOT = new Vector3(MAST_X + 0.3, 2.55, 0);
export const BOOM_LEN = 9.5;
const BOOM_STOW_LUFF = 0.24; // radians: stowed pointing forward over the cargo
const BOOM_MIN_LUFF = 0.14;
const HOOK_IDLE_DROP = 0.9;

// ---------- motion shared by ship + jettisoned crates ----------
export function shipBuffer(ship: ShipDerived, t: number): number {
  const mc = ship.marginCallI;
  if (mc !== null && t >= mc - 1) return ship.buffer[Math.max(0, mc - 1)];
  return sampleAt(ship.buffer, t);
}
export function sinkProgress(ship: ShipDerived, t: number): number {
  if (ship.marginCallI === null || t < ship.marginCallI) return 0;
  const s = Math.min(1, (t - ship.marginCallI) / SINK_FRAMES);
  return s * s * (3 - 2 * s);
}


const _w: WaveSample = { h: 0, dhdx: 0, dhdz: 0 };
const _m = new Matrix4();
const ZERO = new Matrix4().makeScale(0, 0, 0);
const _tip = new Vector3();
const _hook = new Vector3();
const _head = new Vector3(MAST_X, MAST_TOP - 0.25, 0);
const _dir = new Vector3();
const _mid = new Vector3();
const _q = new Quaternion();
const UP = new Vector3(0, 1, 0);
/** Lay a unit-height rod (a cylinder along +y, centred) from a to b. */
function layRod(mesh: Mesh, a: Vector3, b: Vector3) {
  const len = _dir.copy(b).sub(a).length();
  mesh.position.copy(_mid.copy(a).add(b).multiplyScalar(0.5));
  mesh.scale.set(1, Math.max(len, 1e-3), 1);
  if (len > 1e-4) mesh.quaternion.copy(_q.setFromUnitVectors(UP, _dir.multiplyScalar(1 / len)));
}

// ---------- component ----------
export function Ship({ shipKey, derived }: { shipKey: SceneShip; derived: Derived }) {
  const ship = shipOf(derived, shipKey);
  const lay = SHIP_LAYOUT[shipKey];
  const S = (shared ??= buildShared());
  const hullMat = useMemo(() => makeHullMaterial(LIVERY[shipKey].hull), [shipKey]);
  const sailGeo = useMemo(makeSailGeometry, []);
  const wake = useMemo(makeWake, []);
  const slots = useMemo(() => crateSlots(derived.crates), [derived.crates]);
  // Cargo: one instanced draw for all containers on deck.
  const cargo = useMemo(() => {
    const im = new InstancedMesh(containerGeometry(), containerMaterial(), Math.max(1, slots.length));
    im.instanceMatrix.setUsage(DynamicDrawUsage);
    im.count = slots.length;
    slots.forEach((s, i) => {
      im.setMatrixAt(i, _m.makeScale(s.dims.len, s.dims.h, s.dims.w).setPosition(s.local));
      im.setColorAt(i, s.color);
    });
    if (im.instanceColor) im.instanceColor.needsUpdate = true;
    im.frustumCulled = false;
    return im;
  }, [slots]);
  useEffect(
    () => () => {
      hullMat.dispose();
      sailGeo.dispose();
      cargo.dispose();
    },
    [hullMat, sailGeo, cargo],
  );

  const outer = useRef<Group>(null);
  const pitchG = useRef<Group>(null);
  const rollG = useRef<Group>(null);
  const lanternLight = useRef<PointLight>(null);
  const lamps = useMemo(
    () => ({
      mast: new MeshBasicMaterial({ color: LAMP_OFF.clone(), toneMapped: false }),
      port: new MeshBasicMaterial({ color: LAMP_OFF.clone(), toneMapped: false }),
      starboard: new MeshBasicMaterial({ color: LAMP_OFF.clone(), toneMapped: false }),
    }),
    [],
  );
  const smooth = useRef({ rising: 0, heel: 0, freeboard: 1, aboard: -1, slew: 0, luff: BOOM_STOW_LUFF });
  const boomG = useRef<Group>(null);
  const boomTilt = useRef<Group>(null);
  const runner = useRef<Mesh>(null);
  const lift = useRef<Mesh>(null);
  const hookBlock = useRef<Mesh>(null);

  const anchor = useMemo(() => new Vector3(), []);
  const prevT = useRef(vis.t);
  useFrame(({ camera, size }) => {
    const t = vis.t;
    const sm = smooth.current;
    const k = 1 - Math.exp(-vis.dt * 3);
    const sink = sinkProgress(ship, t);
    const buffer = shipBuffer(ship, t);
    sm.freeboard += (FREEBOARD_MIN + (FREEBOARD_MAX - FREEBOARD_MIN) * buffer - sm.freeboard) * k;
    sm.heel += (sampleAt(ship.heelDeg, t) - sm.heel) * k;
    // Sails fill when equity is rising, and when a fair_wind event has the sun breaking through.
    const fill = Math.max(sampleAt(ship.rising, t), vis.fairWind * 0.9);
    sm.rising += (fill * (1 - sink) - sm.rising) * (1 - Math.exp(-vis.dt * 1.5));

    waveAt(lay.x, lay.z, vis.wave, _w);
    const fx = Math.cos(lay.heading);
    const fz = -Math.sin(lay.heading);
    const slopeF = _w.dhdx * fx + _w.dhdz * fz;
    const slopeS = _w.dhdx * -fz + _w.dhdz * fx; // local +z in world = (sin h, cos h) = (-fz, fx)
    if (outer.current) {
      outer.current.position.set(lay.x, _w.h + sm.freeboard - sink * 13, lay.z);
      shipPose[shipKey].y = outer.current.position.y;
      // Hide the hull group, never the group that holds the lantern: a light that disappears changes the scene's light
      // count, and three recompiles every lit material when that changes (a 130 to 150 ms frame as she went under).
      if (pitchG.current) pitchG.current.visible = sink < 0.999;
      anchor.set(lay.x, Math.max(outer.current.position.y, 0) + MAST_TOP + 0.9, lay.z);
      placeLabel(`ship-${shipKey}`, anchor, camera, size.width, size.height);
    }
    // Going down by the stern: the bow lifts as she sinks.
    if (pitchG.current) pitchG.current.rotation.z = Math.atan(slopeF) * 0.75 + sink * 0.75;
    if (rollG.current) {
      const flutter = Math.sin(vis.elapsed * 1.7 + lay.x) * 0.015 * (0.3 + vis.wind);
      rollG.current.rotation.x = (sm.heel * Math.PI) / 180 - Math.atan(slopeS) * 0.75 + flutter + sink * 0.35;
    }
    shapeSail(sailGeo, sm.rising, vis.wind, vis.elapsed + lay.x);
    const wm = wake.material as ShaderMaterial;
    wm.uniforms.uOpacity.value = sm.rising * 0.85;
    wm.uniforms.uTime.value = vis.elapsed;
    wm.uniforms.uLight.value = foamLight(vis.dayFactor, vis.risk, vis.flash, vis.lantern);
    wake.visible = sm.rising > 0.01;

    // Containers on deck: only rewrite the instance matrices when one leaves or comes back.
    let sig = 0; // one bit per container (at most MAX_CRATES = 24)
    for (let i = 0; i < slots.length; i++) if (crateAboard(ship, i, t)) sig |= 1 << i;
    if (sig !== sm.aboard) {
      sm.aboard = sig;
      for (let i = 0; i < slots.length; i++) {
        const s = slots[i];
        cargo.setMatrixAt(i, sig & (1 << i) ? _m.makeScale(s.dims.len, s.dims.h, s.dims.w).setPosition(s.local) : ZERO);
      }
      cargo.instanceMatrix.needsUpdate = true;
    }

    // The hull's world pose, for the containers in the water and the derrick.
    const pose = shipPose[shipKey];
    if (rollG.current) {
      rollG.current.updateWorldMatrix(true, false);
      pose.matrix.copy(rollG.current.matrixWorld);
      pose.inv.copy(pose.matrix).invert();
    }
    // Derrick: slew and luff so the boom's tip stands over the hook point; stowed forward when there is nothing to lift.
    let slewT = 0;
    let luffT = BOOM_STOW_LUFF;
    const lifting = pose.hook.active && sink < 0.05;
    if (lifting) {
      _hook.set(pose.hook.x, pose.hook.y, pose.hook.z).applyMatrix4(pose.inv);
      const dx = _hook.x - BOOM_PIVOT.x;
      const dz = _hook.z - BOOM_PIVOT.z;
      slewT = Math.atan2(-dz, dx);
      const reach = Math.min(BOOM_LEN * Math.cos(BOOM_MIN_LUFF), Math.max(1.2, Math.hypot(dx, dz)));
      luffT = Math.acos(reach / BOOM_LEN);
    }
    const kb = 1 - Math.exp(-vis.dt * 10);
    sm.slew += Math.atan2(Math.sin(slewT - sm.slew), Math.cos(slewT - sm.slew)) * kb;
    sm.luff += (luffT - sm.luff) * kb;
    if (boomG.current) boomG.current.rotation.y = sm.slew;
    if (boomTilt.current) boomTilt.current.rotation.z = sm.luff;
    _tip.set(BOOM_PIVOT.x + Math.cos(sm.slew) * Math.cos(sm.luff) * BOOM_LEN, BOOM_PIVOT.y + Math.sin(sm.luff) * BOOM_LEN, BOOM_PIVOT.z - Math.sin(sm.slew) * Math.cos(sm.luff) * BOOM_LEN);
    if (!lifting) _hook.set(_tip.x, _tip.y - HOOK_IDLE_DROP, _tip.z);
    if (runner.current) layRod(runner.current, _tip, _hook);
    if (lift.current) layRod(lift.current, _head, _tip);
    if (hookBlock.current) hookBlock.current.position.copy(_hook);

    // Lanterns and cabin windows follow the light: on at dusk, at night and while the market is closed.
    const lit = vis.lantern * (1 - sink);
    lamps.mast.color.copy(LAMP_OFF).lerp(LAMP_MAST_ON, lit);
    lamps.port.color.copy(LAMP_OFF).lerp(LAMP_PORT_ON, lit);
    lamps.starboard.color.copy(LAMP_OFF).lerp(LAMP_STARBOARD_ON, lit);
    if (lanternLight.current) lanternLight.current.intensity = lit * LANTERN_LIGHT;
    for (const m of S.glow) m.emissiveIntensity = vis.lantern * WINDOW_GLOW;

    // Going under (from margin_call_i): a burst of spray as she founders. The foam and planks are <Wreck/>.
    const pt = prevT.current;
    prevT.current = t;
    const mc = ship.marginCallI;
    if (mc !== null && t > pt && t - pt < 3 && pt < mc && t >= mc) splash(lay.x, 0, lay.z, 1.4);
    // Spray at the bow in heavy seas: rate from chop (vol_ratio); none in a calm sea or once she is sinking.
    const sprayRate = Math.max(0, vis.wave.chop - 0.45) * 55 * (1 - sink);
    let nSpray = Math.floor(sprayRate * vis.dt + rnd());
    while (nSpray-- > 0) {
      const bx = lay.x + fx * (HULL_L / 2 - 0.8);
      const bz = lay.z + fz * (HULL_L / 2 - 0.8);
      const sideways = (rnd() - 0.5) * 2;
      spawnParticle(PK.Spray, bx - fz * sideways * 1.2, _w.h + 0.3, bz + fx * sideways * 1.2,
        fx * (1.5 + rnd() * 2) - fz * sideways * 2.5, 2.5 + rnd() * 3 + vis.wave.chop * 1.5, fz * (1.5 + rnd() * 2) + fx * sideways * 2.5,
        0.8 + rnd() * 0.5, 0.2 + rnd() * 0.25);
    }
  });

  const funnel = LIVERY[shipKey].funnel;
  return (
    <>
      <group ref={outer} rotation={[0, lay.heading, 0]}>
        <group ref={pitchG}>
          <group ref={rollG}>
            <mesh geometry={S.hull} material={hullMat} />
            <mesh geometry={S.deck} material={S.deckMat} />
            <mesh geometry={S.detail} material={S.darkMat} />
            {/* accommodation block and wheelhouse at the stern */}
            <mesh position={[-5.45, 1.15, 0]} material={S.houseMats}>
              <boxGeometry args={[2.9, 2.3, 3.5]} />
            </mesh>
            <mesh position={[-5.05, 2.86, 0]} material={S.wheelMats}>
              <boxGeometry args={[1.9, 1.1, 4.3]} />
            </mesh>
            <mesh position={[-5.1, 3.46, 0]} material={S.white}>
              <boxGeometry args={[2.3, 0.1, 4.5]} />
            </mesh>
            {/* funnel in the ship's colour, black top */}
            <group position={[-6.35, 2.3, 0]} rotation={[0, 0, 0.1]}>
              <mesh position={[0, 0.95, 0]}>
                <cylinderGeometry args={[0.48, 0.58, 1.9, 16]} />
                <meshStandardMaterial color={funnel} roughness={0.5} metalness={0.1} />
              </mesh>
              <mesh position={[0, 1.78, 0]} material={S.darkMat}>
                <cylinderGeometry args={[0.5, 0.49, 0.42, 16]} />
              </mesh>
              <mesh position={[0, 1.2, 0]} material={S.white}>
                <cylinderGeometry args={[0.515, 0.535, 0.22, 16]} />
              </mesh>
            </group>
            {/* radar mast on the wheelhouse */}
            <mesh position={[-4.9, 4.2, 0]} material={S.rigMat}>
              <cylinderGeometry args={[0.05, 0.07, 1.4, 6]} />
            </mesh>
            <mesh position={[-4.9, 4.75, 0]} material={S.rigMat}>
              <boxGeometry args={[0.12, 0.1, 1.3]} />
            </mesh>
            {/* mast, yard and standing rigging; the sail hangs from the yard */}
            <mesh geometry={S.rig} material={S.rigMat} />
            <mesh geometry={sailGeo} material={S.sailMat} position={[MAST_X + 0.2, YARD_Y, 0]} />
            {/* derrick: boom stepped on the mast, topping lift, cargo runner and hook block */}
            <group ref={boomG} position={BOOM_PIVOT}>
              <group ref={boomTilt}>
                <mesh position={[BOOM_LEN / 2, 0, 0]} rotation={[0, 0, -Math.PI / 2]} material={S.rigMat}>
                  <cylinderGeometry args={[0.1, 0.17, BOOM_LEN, 8]} />
                </mesh>
              </group>
            </group>
            <mesh ref={runner} material={S.darkMat}>
              <cylinderGeometry args={[0.022, 0.022, 1, 5]} />
            </mesh>
            <mesh ref={lift} material={S.rigMat}>
              <cylinderGeometry args={[0.02, 0.02, 1, 5]} />
            </mesh>
            <mesh ref={hookBlock} material={S.darkMat}>
              <boxGeometry args={[0.22, 0.26, 0.22]} />
            </mesh>
            {/* lanterns: masthead, port (red) and starboard (green) */}
            <mesh position={[MAST_X, MAST_TOP + 0.2, 0]} material={lamps.mast}>
              <sphereGeometry args={[0.2, 10, 8]} />
            </mesh>
            <mesh position={[-4.6, 2.95, -2.22]} material={lamps.port}>
              <sphereGeometry args={[0.15, 8, 6]} />
            </mesh>
            <mesh position={[-4.6, 2.95, 2.22]} material={lamps.starboard}>
              <sphereGeometry args={[0.15, 8, 6]} />
            </mesh>
            {/* cargo: one container per USD_PER_CRATE of notional from exposure.positions */}
            <primitive object={cargo} />
          </group>
        </group>
        <primitive object={wake} />
        {/* Outside the hull group, which is hidden once she has sunk: the light count must not change. */}
        <pointLight ref={lanternLight} position={[MAST_X + 0.6, MAST_TOP - 0.6, 0]} intensity={0} distance={38} decay={1.5} color="#ffd9a0" />
      </group>
      <Wreck shipKey={shipKey} derived={derived} />
    </>
  );
}
