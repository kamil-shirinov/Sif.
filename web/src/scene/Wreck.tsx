import { useEffect, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { BoxGeometry, Color, DynamicDrawUsage, Euler, InstancedMesh, Matrix4, Mesh, MeshStandardMaterial, PlaneGeometry, Quaternion, ShaderMaterial, Vector3 } from "three";
import { shipOf, SINK_FRAMES, type Derived, type SceneShip } from "../lib/derive";
import { WAVE_GLSL, waveAt, waveUniforms, type WaveSample } from "./waves";
import { vis } from "./vis";
import { FOAM_NOISE_GLSL, foamLight } from "./foam";
import { SHIP_LAYOUT } from "./Ship";

/** Frames after the margin call over which the foam breaks up and is gone. */
export const WRECK_FOAM_FRAMES = SINK_FRAMES + 80;
const PLANKS = 9;
const PLANK_FROM = SINK_FRAMES * 0.45; // frames after the margin call when the first plank surfaces

const _w: WaveSample = { h: 0, dhdx: 0, dhdz: 0 };
const _m = new Matrix4();
const _q = new Quaternion();
const _e = new Euler();
const _v = new Vector3();
const _s = new Vector3();
const ZERO = new Matrix4().makeScale(0, 0, 0);
const smooth = (u: number) => {
  const t = Math.min(1, Math.max(0, u));
  return t * t * (3 - 2 * t);
};

/**
 * What a sinking ship leaves on the water, from ships.*.margin_call_i: churning foam where the hull goes down,
 * which breaks into patches and fades, and a few planks that surface and drift. Everything is a function of the
 * playhead, so it is the same paused, scrubbed or played.
 */
export function Wreck({ shipKey, derived }: { shipKey: SceneShip; derived: Derived }) {
  const ship = shipOf(derived, shipKey);
  const lay = SHIP_LAYOUT[shipKey];
  const mc = ship.marginCallI;

  const foam = useMemo(() => {
    const g = new PlaneGeometry(1, 1, 30, 22);
    g.rotateX(-Math.PI / 2);
    const mat = new ShaderMaterial({
      uniforms: { ...waveUniforms, uGrow: { value: 0 }, uBreak: { value: 0 }, uChurn: { value: 0 }, uTime: { value: 0 }, uLight: { value: 1 }, uSeed: { value: lay.x * 0.37 } },
      vertexShader: /* glsl */ `
        ${WAVE_GLSL}
        varying vec2 vUv; varying vec2 vW;
        void main() {
          vUv = uv;
          vec4 wp = modelMatrix * vec4(position, 1.0);
          wp.y = waveEval(wp.xz).x + 0.07;
          vW = wp.xz;
          gl_Position = projectionMatrix * viewMatrix * wp;
        }`,
      fragmentShader: /* glsl */ `
        uniform float uGrow; uniform float uBreak; uniform float uChurn; uniform float uTime; uniform float uLight; uniform float uSeed;
        varying vec2 vUv; varying vec2 vW;
        ${FOAM_NOISE_GLSL}
        void main() {
          vec2 c = (vUv - 0.5) * 2.0;
          float r = length(c);
          // The patch spreads as she goes down; its edge is ragged, never an ellipse.
          float reach = mix(0.2, 0.9, uGrow);
          float ragged = fmFbm(vW * 0.16 + uSeed) - 0.5;
          float body = 1.0 - smoothstep(reach * 0.35, reach, r + ragged * 0.7);
          // Lace: thin white veins around dark holes of open water (the ridges of a slowly drifting noise). The
          // holes widen as the foam breaks up, until only scraps are left.
          vec2 q = vW * 0.55 + vec2(uTime * 0.04, -uTime * 0.025) + uSeed;
          float cells = abs(fmFbm(q) - 0.5) * 2.0;
          float veins = 1.0 - smoothstep(0.0, mix(0.34, 0.07, uBreak), cells);
          float scraps = smoothstep(mix(0.3, 0.7, uBreak), 0.85, fmFbm(q * 0.6 + 9.0));
          float fine = fmNoise(vW * 3.1 - vec2(uTime * 0.25, uTime * 0.17));
          float lace = clamp(veins * (0.55 + 0.45 * scraps) + scraps * 0.35, 0.0, 1.0) * (0.7 + 0.3 * fine);
          // Boiling water over the hull while she is still going down: bursts of bubbles, not a filled disc.
          float bub = smoothstep(0.52, 0.8, fmNoise(vW * 1.9 + vec2(0.0, uTime * 1.6)) * 0.6 + fmNoise(vW * 4.3 - uTime * 2.2) * 0.4 + 0.12);
          float boil = uChurn * (1.0 - smoothstep(0.1, 0.62, r + ragged * 0.3)) * bub;
          float a = clamp(body * lace * 1.25 * (1.0 - uBreak * uBreak) + boil, 0.0, 1.0) * 0.95;
          if (a < 0.012) discard;
          gl_FragColor = vec4(vec3(0.95, 0.98, 1.0) * uLight * (0.8 + 0.2 * fine), a);
        }`,
      transparent: true,
      depthWrite: false,
    });
    const m = new Mesh(g, mat);
    m.position.set(lay.x, 0, lay.z);
    m.rotation.y = lay.heading;
    m.scale.set(34, 1, 24);
    m.frustumCulled = false;
    m.renderOrder = 3;
    m.visible = false;
    return m;
  }, [lay]);

  const planks = useMemo(() => {
    const im = new InstancedMesh(new BoxGeometry(1, 1, 1), new MeshStandardMaterial({ roughness: 0.9, metalness: 0 }), PLANKS);
    im.instanceMatrix.setUsage(DynamicDrawUsage);
    const c = new Color();
    for (let i = 0; i < PLANKS; i++) {
      im.setMatrixAt(i, ZERO);
      im.setColorAt(i, c.set("#7a5a3a").offsetHSL(0, 0, ((i * 37) % 11) / 11 * 0.14 - 0.07));
    }
    im.frustumCulled = false;
    im.visible = false;
    return im;
  }, []);
  // Each plank: where it surfaces, which way it drifts, its size. Fixed per ship, no randomness at run time.
  const plan = useMemo(
    () =>
      Array.from({ length: PLANKS }, (_, i) => {
        const r1 = ((i * 7919 + 13) % 97) / 97;
        const r2 = ((i * 104729 + 7) % 89) / 89;
        const a = (i / PLANKS) * Math.PI * 2 + r1 * 0.9;
        return { a, r0: 1.2 + r2 * 3.2, speed: 0.05 + 0.07 * r1, yaw: r2 * Math.PI * 2, len: 1.5 + r1 * 1.5, wid: 0.3 + r2 * 0.22, from: PLANK_FROM + i * 2.2, phase: r1 * 6 };
      }),
    [],
  );

  useEffect(
    () => () => {
      foam.geometry.dispose();
      (foam.material as ShaderMaterial).dispose();
      planks.geometry.dispose();
      (planks.material as MeshStandardMaterial).dispose();
    },
    [foam, planks],
  );

  useFrame(() => {
    const age = mc === null ? -1 : vis.t - mc;
    foam.visible = age >= 0 && age < WRECK_FOAM_FRAMES;
    if (foam.visible) {
      const u = (foam.material as ShaderMaterial).uniforms;
      u.uGrow.value = smooth(age / (SINK_FRAMES * 0.6));
      u.uBreak.value = smooth((age - SINK_FRAMES * 0.7) / (WRECK_FOAM_FRAMES - SINK_FRAMES * 0.7));
      u.uChurn.value = smooth(age / 4) * (1 - smooth((age - SINK_FRAMES * 0.6) / (SINK_FRAMES * 0.6)));
      u.uTime.value = vis.elapsed;
      u.uLight.value = foamLight(vis.dayFactor, vis.risk, vis.flash, vis.lantern);
    }
    planks.visible = age >= PLANK_FROM;
    if (!planks.visible) return;
    for (let i = 0; i < PLANKS; i++) {
      const p = plan[i];
      const d = age - p.from;
      if (d < 0) {
        planks.setMatrixAt(i, ZERO);
        continue;
      }
      // Drift: quick at first, then carried slowly by the sea.
      const out = p.r0 + p.speed * (18 * (1 - Math.exp(-d / 18)) + d * 0.2);
      const x = lay.x + Math.cos(p.a) * out * 1.25;
      const z = lay.z + Math.sin(p.a) * out;
      waveAt(x, z, vis.wave, _w);
      const rise = smooth(d / 5); // surfaces from below
      _v.set(x, _w.h + 0.02 - (1 - rise) * 1.4 + Math.sin(vis.elapsed * 1.7 + p.phase) * 0.03, z);
      _e.set(-Math.atan(_w.dhdz) * 0.9 + (1 - rise) * 0.8, p.yaw + d * 0.006, Math.atan(_w.dhdx) * 0.9);
      _q.setFromEuler(_e);
      _s.set(p.len, 0.12, p.wid);
      planks.setMatrixAt(i, _m.compose(_v, _q, _s));
    }
    planks.instanceMatrix.needsUpdate = true;
  });

  if (mc === null) return null;
  return (
    <>
      <primitive object={foam} />
      <primitive object={planks} />
    </>
  );
}
