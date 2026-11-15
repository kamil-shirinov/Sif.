import { useEffect, useMemo } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { BufferAttribute, BufferGeometry, DynamicDrawUsage, Points, ShaderMaterial, Vector3 } from "three";
import { WAVE_GLSL, waveAt, waveUniforms, type WaveSample } from "./waves";
import { vis } from "./vis";

// One pool of GPU particles for everything the sea throws up: spray at the bows in heavy seas, the splash of a
// crate going over the side, the boil of a sinking ship. CPU work is only the spawn (a few attribute writes);
// the motion is computed in the vertex shader from the birth time. One draw call. (The foam on the water and the
// planks of a wreck are not particles: see Jettison.tsx and Wreck.tsx.)

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

/** A crate (or anything) hitting the water: a crown of droplets. The ring of foam is drawn on the sea by Jettison.tsx. `power` ~ 1 for a crate. */
export function splash(x: number, y: number, z: number, power = 1) {
  const n = Math.round(26 * power);
  for (let k = 0; k < n; k++) {
    const a = rnd() * Math.PI * 2;
    const r = 1.2 + rnd() * 2.2;
    spawnParticle(PK.Spray, x, y + 0.1, z, Math.cos(a) * r * power, (4 + rnd() * 4.5) * Math.sqrt(power), Math.sin(a) * r * power, 0.9 + rnd() * 0.6, 0.18 + rnd() * 0.22);
  }
}

/** Drop every particle (a new bundle, a seek). */
export function clearParticles() {
  for (let i = 0; i < POOL; i++) meta[i * 4 + 1] = 0;
  dirtyLo = 0;
  dirtyHi = POOL - 1;
}

const _crest: WaveSample = { h: 0, dhdx: 0, dhdz: 0 };

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
      uniforms: { ...waveUniforms, uTime: { value: 0 }, uScale: { value: 600 }, uLight: { value: 1 }, uWind: { value: new Vector3() } },
      vertexShader: /* glsl */ `
        ${WAVE_GLSL}
        attribute vec3 aVel; attribute vec4 aMeta;
        uniform float uTime; uniform float uScale; uniform vec3 uWind;
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
              // Ballistic, and carried downwind: the wind keeps pushing, so the drift grows with the square of its age.
              p += aVel * age * (1.0 - 0.25 * u) + vec3(0.0, -9.8 * 0.5 * age * age, 0.0) + uWind * age * age;
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

  useEffect(() => {
    clearParticles();
    return () => {
      points.geometry.dispose();
      (points.material as ShaderMaterial).dispose();
    };
  }, [points]);

  useFrame(({ camera, gl }) => {
    const m = points.material as ShaderMaterial;
    m.uniforms.uTime.value = vis.elapsed;
    // Wind on the spray: nothing in a calm, 7 units/s^2 downwind in a storm.
    (m.uniforms.uWind.value as Vector3).copy(vis.windDir).multiplyScalar(7 * Math.max(0, vis.wind - 0.2));
    // Spindrift: in a storm (wind over 0.6, i.e. state storm) the wind tears the tops off the waves around the
    // ships. A few random points are tried each frame; those near a crest throw a streak of spray downwind.
    const gale = Math.max(0, vis.wind - 0.6) / 0.4;
    if (gale > 0 && vis.wave.amp > 0.6) {
      const tries = Math.floor(gale * 10 + rnd());
      for (let k = 0; k < tries; k++) {
        const x = (rnd() - 0.5) * 150;
        const z = (rnd() - 0.5) * 110 - 10;
        waveAt(x, z, vis.wave, _crest);
        if (_crest.h < vis.wave.amp * 0.55) continue;
        for (let q = 0; q < 3; q++) {
          spawnParticle(PK.Spray, x + (rnd() - 0.5) * 2.5, _crest.h + 0.1, z + (rnd() - 0.5) * 2.5,
            vis.windDir.x * (4 + rnd() * 4), 1.2 + rnd() * 1.8, vis.windDir.z * (4 + rnd() * 4), 0.7 + rnd() * 0.5, 0.25 + rnd() * 0.3);
        }
      }
    }
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
  });

  return <primitive object={points} />;
}
