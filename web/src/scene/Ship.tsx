import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import {
  BoxGeometry,
  Color,
  DoubleSide,
  ExtrudeGeometry,
  Group,
  Mesh,
  MeshStandardMaterial,
  PlaneGeometry,
  ShaderMaterial,
  Shape,
  Vector3,
} from "three";
import type { ShipKey } from "../types/bundle";
import type { CrateSpec, Derived, ShipDerived } from "../lib/derive";
import { sampleAt } from "../lib/derive";
import { WAVE_GLSL, waveAt, waveUniforms, type WaveSample } from "./waves";
import { vis } from "./vis";
import { placeLabel } from "./labels";

// ---------- layout ----------
export const SHIP_LAYOUT: Record<ShipKey, { x: number; z: number; heading: number }> = {
  prepared: { x: -9, z: 4, heading: 0.22 },
  unprepared: { x: 10, z: -5, heading: -0.16 },
};

const L = 14; // hull length
const B = 4.4; // beam
const H = 2.6; // hull depth (deck at y = 0, keel at y = -H)
const PAINT_LINE = -1.3; // design waterline paint (red below)
const FREEBOARD_MAX = 1.95; // deck height above water with a full margin buffer (riding high)
const FREEBOARD_MIN = 0.2; // no margin buffer left: deck nearly awash
const SINK_FRAMES = 30;
const DECK = { x0: -1.0, x1: 5.6, z0: -1.75, z1: 1.75 };
const CRATE_COLORS = ["#c47f36", "#3f7fc4", "#5aa168", "#c14b4b", "#8b6cc4", "#c4b13f"];

// ---------- geometry ----------
function makeHullGeometry(): ExtrudeGeometry {
  const s = new Shape();
  const hb = B / 2;
  s.moveTo(-L / 2, -hb + 0.5);
  s.quadraticCurveTo(-L / 2, -hb, -L / 2 + 0.6, -hb);
  s.lineTo(L / 2 - 4.5, -hb);
  s.quadraticCurveTo(L / 2 - 0.8, -hb + 0.2, L / 2, 0);
  s.quadraticCurveTo(L / 2 - 0.8, hb - 0.2, L / 2 - 4.5, hb);
  s.lineTo(-L / 2 + 0.6, hb);
  s.quadraticCurveTo(-L / 2, hb, -L / 2, hb - 0.5);
  s.closePath();
  const g = new ExtrudeGeometry(s, { depth: H, steps: 8, bevelEnabled: false, curveSegments: 10 });
  g.rotateX(Math.PI / 2); // shape y -> z (beam), extrusion -> -y (down)
  const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const y = p.getY(i);
    const f = Math.min(1, Math.max(0, -y / H));
    const x = p.getX(i);
    p.setZ(i, p.getZ(i) * (1 - 0.42 * f * f));
    // bow rake: keel shorter than deck at the bow
    if (x > 0) p.setX(i, x * (1 - 0.12 * f));
  }
  g.computeVertexNormals();
  return g;
}

function makeHullMaterial(): MeshStandardMaterial {
  const m = new MeshStandardMaterial({ roughness: 0.65, metalness: 0.15 });
  m.onBeforeCompile = (shader) => {
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\nvarying float vLocalY;\nvarying float vUp;")
      .replace("#include <begin_vertex>", "#include <begin_vertex>\nvLocalY = position.y;\nvUp = normal.y;");
    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", "#include <common>\nvarying float vLocalY;\nvarying float vUp;")
      .replace(
        "vec4 diffuseColor = vec4( diffuse, opacity );",
        `vec3 hullC = vLocalY > ${(PAINT_LINE + 0.18).toFixed(2)} ? vec3(0.06, 0.09, 0.14)
                    : vLocalY > ${PAINT_LINE.toFixed(2)} ? vec3(0.85, 0.85, 0.82) : vec3(0.48, 0.07, 0.06);
         if (vUp > 0.8 && vLocalY > -0.05) hullC = vec3(0.45, 0.36, 0.25);
         vec4 diffuseColor = vec4( hullC, opacity );`,
      );
  };
  return m;
}

function makeSailGeometry(): PlaneGeometry {
  const g = new PlaneGeometry(4.2, 4.6, 10, 10);
  const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const u = p.getX(i) / 2.1;
    const v = p.getY(i) / 2.3;
    p.setZ(i, (1 - u * u) * (1 - v * v) * 1.3);
  }
  g.rotateY(Math.PI / 2); // plane across the beam, bulge forward (+x)
  g.computeVertexNormals();
  return g;
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
  m.position.set(-L / 2 + 0.3, 0, 0);
  m.frustumCulled = false;
  return m;
}

// ---------- crate layout ----------
export interface CrateSlot {
  spec: CrateSpec;
  local: Vector3; // centre on deck, hull-local
  color: Color;
}

export function crateSlots(crates: CrateSpec[]): CrateSlot[] {
  if (crates.length === 0) return [];
  const size = crates[0].size;
  const w = DECK.x1 - DECK.x0;
  const d = DECK.z1 - DECK.z0;
  const cols = Math.max(1, Math.floor(w / size));
  const rows = Math.max(1, Math.floor(d / size));
  const per = cols * rows;
  return crates.map((spec, k) => {
    const layer = Math.floor(k / per);
    const r = k % per;
    const col = r % cols;
    const row = Math.floor(r / cols);
    const local = new Vector3(DECK.x0 + (col + 0.5) * (w / cols), size / 2 + layer * size * 1.01, DECK.z0 + (row + 0.5) * (d / rows));
    const c = new Color(CRATE_COLORS[spec.positionIndex % CRATE_COLORS.length]);
    c.offsetHSL(0, 0, ((k * 37) % 7) / 70 - 0.04);
    return { spec, local, color: c };
  });
}

/** Number of crates the ship throws overboard at cut_i (cut_fraction of its cargo). */
export function thrownCount(ship: ShipDerived, total: number): number {
  return ship.cutI === null ? 0 : Math.round(ship.cutFraction * total);
}
/** Frame at which the j-th thrown crate goes over the side. */
export const throwFrame = (ship: ShipDerived, j: number) => (ship.cutI ?? 0) + j * 0.4;

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

// ---------- component ----------
export function Ship({ shipKey, derived }: { shipKey: ShipKey; derived: Derived }) {
  const ship = derived.ships[shipKey];
  const lay = SHIP_LAYOUT[shipKey];
  const hullGeo = useMemo(makeHullGeometry, []);
  const hullMat = useMemo(makeHullMaterial, []);
  const sailGeo = useMemo(makeSailGeometry, []);
  const wake = useMemo(makeWake, []);
  const slots = useMemo(() => crateSlots(derived.crates), [derived.crates]);
  const nThrown = thrownCount(ship, slots.length);
  const crateGeo = useMemo(() => new BoxGeometry(1, 1, 1), []);
  const crateMats = useMemo(() => slots.map((s) => new MeshStandardMaterial({ color: s.color, roughness: 0.8 })), [slots]);

  const outer = useRef<Group>(null);
  const pitchG = useRef<Group>(null);
  const rollG = useRef<Group>(null);
  const sail = useRef<Mesh>(null);
  const crateRefs = useRef<(Mesh | null)[]>([]);
  const smooth = useRef({ rising: 0, heel: 0, freeboard: 1 });

  const anchor = useMemo(() => new Vector3(), []);
  useFrame(({ camera, size }) => {
    const t = vis.t;
    const sm = smooth.current;
    const k = 1 - Math.exp(-vis.dt * 3);
    const sink = sinkProgress(ship, t);
    const buffer = shipBuffer(ship, t);
    sm.freeboard += (FREEBOARD_MIN + (FREEBOARD_MAX - FREEBOARD_MIN) * buffer - sm.freeboard) * k;
    sm.heel += (sampleAt(ship.heelDeg, t) - sm.heel) * k;
    sm.rising += (sampleAt(ship.rising, t) * (1 - sink) - sm.rising) * (1 - Math.exp(-vis.dt * 1.5));

    waveAt(lay.x, lay.z, vis.wave, _w);
    const fx = Math.cos(lay.heading);
    const fz = -Math.sin(lay.heading);
    const slopeF = _w.dhdx * fx + _w.dhdz * fz;
    const slopeS = _w.dhdx * -fz + _w.dhdz * fx; // local +z in world = (sin h, cos h) = (-fz, fx)
    if (outer.current) {
      outer.current.position.set(lay.x, _w.h + sm.freeboard - sink * 11, lay.z);
      outer.current.visible = sink < 0.999;
      anchor.set(lay.x, Math.max(outer.current.position.y, 0) + 9, lay.z);
      placeLabel(`ship-${shipKey}`, anchor, camera, size.width, size.height);
    }
    if (pitchG.current) pitchG.current.rotation.z = Math.atan(slopeF) * 0.75 + sink * 0.6;
    if (rollG.current) {
      const flutter = Math.sin(vis.elapsed * 1.7 + lay.x) * 0.015 * (0.3 + vis.wind);
      rollG.current.rotation.x = (sm.heel * Math.PI) / 180 - Math.atan(slopeS) * 0.75 + flutter + sink * 0.35;
    }
    if (sail.current) {
      const luff = (1 - sm.rising) * Math.sin(vis.elapsed * (4 + 6 * vis.wind)) * 0.06 * (0.3 + vis.wind);
      sail.current.scale.x = 0.08 + 0.92 * sm.rising + luff;
    }
    const wm = wake.material as ShaderMaterial;
    wm.uniforms.uOpacity.value = sm.rising * 0.85;
    wm.uniforms.uTime.value = vis.elapsed;
    wm.uniforms.uLight.value = 0.3 + 0.7 * vis.dayFactor * (1 - 0.6 * vis.risk) + vis.flash;
    wake.visible = sm.rising > 0.01;

    for (let i = 0; i < slots.length; i++) {
      const m = crateRefs.current[i];
      if (!m) continue;
      const j = slots.length - 1 - i; // throw order: top/last-stowed crate first
      m.visible = !(j < nThrown && t >= throwFrame(ship, j));
    }
  });

  return (
    <>
      <group ref={outer} rotation={[0, lay.heading, 0]}>
        <group ref={pitchG}>
          <group ref={rollG}>
            <mesh geometry={hullGeo} material={hullMat} />
            {/* bridge + funnel at the stern */}
            <mesh position={[-5.1, 1.3, 0]}>
              <boxGeometry args={[2.6, 2.6, 3.4]} />
              <meshStandardMaterial color="#e9e6df" roughness={0.6} />
            </mesh>
            <mesh position={[-4.15, 2.1, 0]}>
              <boxGeometry args={[0.7, 0.5, 3.45]} />
              <meshStandardMaterial color="#1a2633" roughness={0.2} metalness={0.5} />
            </mesh>
            <mesh position={[-5.6, 3.4, 0]}>
              <cylinderGeometry args={[0.45, 0.55, 1.8, 12]} />
              <meshStandardMaterial color={shipKey === "prepared" ? "#2c8a6a" : "#b3402c"} roughness={0.5} />
            </mesh>
            {/* mast, yard and sail */}
            <mesh position={[-2.4, 4.2, 0]}>
              <cylinderGeometry args={[0.12, 0.16, 8.4, 8]} />
              <meshStandardMaterial color="#5a4632" />
            </mesh>
            <mesh position={[-2.4, 6.9, 0]} rotation={[Math.PI / 2, 0, 0]}>
              <cylinderGeometry args={[0.08, 0.08, 4.6, 6]} />
              <meshStandardMaterial color="#5a4632" />
            </mesh>
            <mesh ref={sail} geometry={sailGeo} position={[-2.25, 4.55, 0]}>
              <meshStandardMaterial color="#ece4d2" roughness={0.9} side={DoubleSide} />
            </mesh>
            {/* cargo: one crate per USD_PER_CRATE of notional from exposure.positions */}
            {slots.map((s, i) => (
              <mesh
                key={i}
                ref={(m) => {
                  crateRefs.current[i] = m;
                }}
                geometry={crateGeo}
                material={crateMats[i]}
                position={s.local}
                scale={s.spec.size * 0.94}
              />
            ))}
          </group>
        </group>
        <primitive object={wake} />
      </group>
    </>
  );
}
