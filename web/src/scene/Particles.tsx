import { useEffect, useMemo } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import {
  BoxGeometry,
  BufferAttribute,
  BufferGeometry,
  DynamicDrawUsage,
  InstancedMesh,
  Matrix4,
  MeshStandardMaterial,
  Points,
  Quaternion,
  ShaderMaterial,
  Vector3,
  Euler,
} from "three";
import { WAVE_GLSL, waveAt, waveUniforms, type WaveSample } from "./waves";
import { vis } from "./vis";

// One pool of GPU particles for everything the sea throws up: spray at the bows in heavy seas, the splash of a
// crate going over the side, the boil of a sinking ship. CPU work is only the spawn (a few attribute writes);
// the motion is computed in the vertex shader from the birth time. One draw call. Debris planks are a separate
// instanced mesh that rides the waves on the CPU (at most a few dozen).

const POOL = 3072;
export const enum PK {
  Spray = 0, // ballistic droplet, gravity
  Boil = 1, // foam on the surface: grows and fades (splash ring, sinking boil)
}

const pos = new Float32Array(POOL * 3);
const vel = new Float32Array(POOL * 3);
const meta = new Float32Array(POOL * 4); // birth, life, size, kind
let head = 0;
let dirtyLo = Infinity;
let dirtyHi = -1;

/** Spawn one particle. Velocity in units per second, life in seconds of wall time, size in scene units. */
export function spawnParticle(kind: PK, x: number, y: number, z: number, vx: number, vy: number, vz: number, life: number, size: number) {
  const i = head;
  head = (head + 1) % POOL;
  pos[i * 3] = x;
  pos[i * 3 + 1] = y;
  pos[i * 3 + 2] = z;
  vel[i * 3] = vx;
  vel[i * 3 + 1] = vy;
  vel[i * 3 + 2] = vz;
  meta[i * 4] = vis.elapsed;
  meta[i * 4 + 1] = life;
  meta[i * 4 + 2] = size;
  meta[i * 4 + 3] = kind;
  if (i < dirtyLo) dirtyLo = i;
  if (i > dirtyHi) dirtyHi = i;
}

// Deterministic cheap random (no Math.random: spray looks the same on every run).
let seed = 1234567;
export function rnd(): number {
  seed = (seed * 16807) % 2147483647;
  return (seed - 1) / 2147483646;
}

/** A crate (or anything) hitting the water: a crown of droplets and a ring of foam. `power` ~ 1 for a crate. */
export function splash(x: number, y: number, z: number, power = 1) {
  const n = Math.round(26 * power);
  for (let k = 0; k < n; k++) {
    const a = rnd() * Math.PI * 2;
    const r = 1.2 + rnd() * 2.2;
    spawnParticle(PK.Spray, x, y + 0.1, z, Math.cos(a) * r * power, (4 + rnd() * 4.5) * Math.sqrt(power), Math.sin(a) * r * power, 0.9 + rnd() * 0.6, 0.18 + rnd() * 0.22);
  }
  for (let k = 0; k < 6; k++) {
    const a = rnd() * Math.PI * 2;
    spawnParticle(PK.Boil, x + Math.cos(a) * 0.6, y, z + Math.sin(a) * 0.6, Math.cos(a) * 1.4, 0, Math.sin(a) * 1.4, 1.8 + rnd(), 1.2 * power);
  }
}

// ---- debris (planks from a sinking ship) ----
const MAX_DEBRIS = 32;
interface Plank {
  x: number;
  z: number;
  vx: number;
  vz: number;
  spin: number;
  born: number;
  alive: boolean;
}
const planks: Plank[] = Array.from({ length: MAX_DEBRIS }, () => ({ x: 0, z: 0, vx: 0, vz: 0, spin: 0, born: 0, alive: false }));
let plankHead = 0;
export function spawnDebris(x: number, z: number, count: number) {
  for (let k = 0; k < count; k++) {
    const p = planks[plankHead];
    plankHead = (plankHead + 1) % MAX_DEBRIS;
    const a = rnd() * Math.PI * 2;
    const r = rnd() * 3;
    p.x = x + Math.cos(a) * r;
    p.z = z + Math.sin(a) * r;
    p.vx = Math.cos(a) * (0.3 + rnd() * 0.6);
    p.vz = Math.sin(a) * (0.3 + rnd() * 0.6);
    p.spin = (rnd() - 0.5) * 2;
    p.born = vis.elapsed;
    p.alive = true;
  }
}
/** Drop every particle and plank (a new bundle, a seek). */
export function clearParticles() {
  for (let i = 0; i < POOL; i++) meta[i * 4 + 1] = 0;
  dirtyLo = 0;
  dirtyHi = POOL - 1;
  for (const p of planks) p.alive = false;
}

const DEBRIS_LIFE = 90; // seconds a plank floats before it is gone
const _m = new Matrix4();
const _q = new Quaternion();
const _e = new Euler();
const _v = new Vector3();
const _s = new Vector3();
const _w: WaveSample = { h: 0, dhdx: 0, dhdz: 0 };
const ZERO = new Matrix4().makeScale(0, 0, 0);

export function Particles() {
  const size = useThree((s) => s.size);
  const points = useMemo(() => {
    const g = new BufferGeometry();
    const aPos = new BufferAttribute(pos, 3).setUsage(DynamicDrawUsage);
    const aVel = new BufferAttribute(vel, 3).setUsage(DynamicDrawUsage);
    const aMeta = new BufferAttribute(meta, 4).setUsage(DynamicDrawUsage);
    g.setAttribute("position", aPos);
    g.setAttribute("aVel", aVel);
    g.setAttribute("aMeta", aMeta);
    const m = new ShaderMaterial({
      uniforms: { ...waveUniforms, uTime: { value: 0 }, uScale: { value: 600 }, uLight: { value: 1 } },
      vertexShader: /* glsl */ `
        ${WAVE_GLSL}
        attribute vec3 aVel; attribute vec4 aMeta;
        uniform float uTime; uniform float uScale;
        varying float vA; varying float vKind;
        void main() {
          float age = uTime - aMeta.x;
          float life = aMeta.y;
          vKind = aMeta.w;
          vA = 0.0;
          vec3 p = position;
          float sz = aMeta.z;
          if (life > 0.0 && age >= 0.0 && age < life) {
            float u = age / life;
            if (vKind < 0.5) {
              // Spray: ballistic, with a little drag; gone when it falls back into the sea.
              p += aVel * age * (1.0 - 0.25 * u) + vec3(0.0, -9.8 * 0.5 * age * age, 0.0);
              float sea = waveEval(p.xz).x;
              vA = (1.0 - u) * step(sea - 0.2, p.y);
              sz *= 1.0 + u * 0.8;
            } else {
              // Foam boil: spreads on the surface and fades.
              p.xz += aVel.xz * age * (1.0 - 0.5 * u);
              p.y = waveEval(p.xz).x + 0.06;
              vA = (1.0 - u) * smoothstep(0.0, 0.08, u) * 0.8;
              sz *= 1.0 + u * 2.5;
            }
          }
          vec4 mv = viewMatrix * vec4(p, 1.0);
          gl_Position = projectionMatrix * mv;
          gl_PointSize = vA > 0.0 ? clamp(sz * uScale / max(-mv.z, 0.05), 1.0, 96.0) : 0.0;
        }`,
      fragmentShader: /* glsl */ `
        uniform float uLight;
        varying float vA; varying float vKind;
        void main() {
          if (vA <= 0.0) discard;
          vec2 c = gl_PointCoord - 0.5;
          float r = length(c) * 2.0;
          float a = vKind < 0.5 ? smoothstep(1.0, 0.35, r) : smoothstep(1.0, 0.6, r) * (0.55 + 0.45 * smoothstep(0.2, 0.8, r));
          a *= vA;
          if (a < 0.01) discard;
          gl_FragColor = vec4(vec3(0.88, 0.93, 0.96) * uLight, a * 0.85);
        }`,
      transparent: true,
      depthWrite: false,
    });
    const pts = new Points(g, m);
    pts.frustumCulled = false;
    pts.renderOrder = 4;
    return pts;
  }, []);

  const debris = useMemo(() => {
    const geo = new BoxGeometry(1.6, 0.14, 0.38);
    const mat = new MeshStandardMaterial({ color: "#5d4630", roughness: 0.9 });
    const im = new InstancedMesh(geo, mat, MAX_DEBRIS);
    im.instanceMatrix.setUsage(DynamicDrawUsage);
    for (let i = 0; i < MAX_DEBRIS; i++) im.setMatrixAt(i, ZERO);
    im.frustumCulled = false;
    return im;
  }, []);

  useEffect(() => {
    clearParticles();
    return () => {
      points.geometry.dispose();
      (points.material as ShaderMaterial).dispose();
      debris.geometry.dispose();
      (debris.material as MeshStandardMaterial).dispose();
    };
  }, [points, debris]);

  useFrame(({ camera, gl }) => {
    const m = points.material as ShaderMaterial;
    m.uniforms.uTime.value = vis.elapsed;
    const fov = "fov" in camera ? (camera as { fov: number }).fov : 50;
    m.uniforms.uScale.value = (size.height * gl.getPixelRatio() * 0.5) / Math.tan((fov * Math.PI) / 360);
    m.uniforms.uLight.value = Math.min(1.5, 0.15 + 0.85 * vis.dayFactor * (1 - 0.5 * vis.risk) + vis.flash * 1.2 + 0.1 * vis.lantern);
    if (dirtyHi >= dirtyLo) {
      const g = points.geometry;
      for (const [name, w] of [["position", 3], ["aVel", 3], ["aMeta", 4]] as const) {
        const a = g.getAttribute(name) as BufferAttribute;
        a.clearUpdateRanges();
        a.addUpdateRange(dirtyLo * w, (dirtyHi - dirtyLo + 1) * w);
        a.needsUpdate = true;
      }
      dirtyLo = Infinity;
      dirtyHi = -1;
    }

    let any = false;
    for (let i = 0; i < MAX_DEBRIS; i++) {
      const p = planks[i];
      if (!p.alive) continue;
      const age = vis.elapsed - p.born;
      if (age > DEBRIS_LIFE) {
        p.alive = false;
        debris.setMatrixAt(i, ZERO);
        any = true;
        continue;
      }
      const drag = Math.min(age, 6);
      const x = p.x + p.vx * drag + p.vx * 0.08 * age;
      const z = p.z + p.vz * drag + p.vz * 0.08 * age;
      waveAt(x, z, vis.wave, _w);
      _e.set(-Math.atan(_w.dhdz), p.spin + age * 0.03 * p.spin, Math.atan(_w.dhdx));
      _q.setFromEuler(_e);
      const rise = Math.min(1, age / 1.5); // planks surface from below
      _v.set(x, _w.h - 0.05 - (1 - rise) * 1.2, z);
      _s.setScalar(1);
      _m.compose(_v, _q, _s);
      debris.setMatrixAt(i, _m);
      any = true;
    }
    if (any) debris.instanceMatrix.needsUpdate = true;
  });

  return (
    <>
      <primitive object={points} />
      <primitive object={debris} />
    </>
  );
}
