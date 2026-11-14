import { useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { CylinderGeometry, DoubleSide, Group, Mesh, ShaderMaterial } from "three";
import type { WatchEvent } from "../types/bundle";
import { vis } from "./vis";

const FAR = 1500;
const NEAR = 110;
const LINGER = 40; // frames after at_i over which the front fades (it is overhead by then)

const NOISE = /* glsl */ `
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
float fbm(vec2 p) { float s = 0.0, a = 0.5; for (int k = 0; k < 5; k++) { s += a * vnoise(p); p *= 2.03; a *= 0.5; } return s; }
`;

function makeFront(): Mesh {
  // A curved wall of cloud, 155 degrees wide, facing the ships from the horizon (-z).
  const geo = new CylinderGeometry(1, 1, 1, 96, 1, true, Math.PI - 1.35, 2.7);
  geo.translate(0, 0.5, 0);
  const mat = new ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uOpacity: { value: 0 }, uFlash: { value: 0 } },
    vertexShader: /* glsl */ `
      varying vec2 vUv;
      void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: /* glsl */ `
      uniform float uTime; uniform float uOpacity; uniform float uFlash;
      varying vec2 vUv;
      ${NOISE}
      void main() {
        vec2 p = vec2(vUv.x * 20.0, vUv.y * 3.0);
        float n = fbm(p + vec2(uTime * 0.03, uTime * 0.01));
        float top = 0.55 + 0.35 * fbm(vec2(vUv.x * 9.0 + uTime * 0.02, 1.7));
        float body = 1.0 - smoothstep(top - 0.12, top, vUv.y);
        float sides = smoothstep(0.0, 0.12, vUv.x) * smoothstep(1.0, 0.88, vUv.x);
        // Rain curtains hanging under the shelf cloud.
        float curtain = smoothstep(0.35, 0.0, vUv.y) * (0.55 + 0.45 * vnoise(vec2(vUv.x * 120.0, uTime * 0.5)));
        // Opaque body: in the HDR (bloom) path a translucent wall would let the bright horizon glow through.
        float a = clamp(body + curtain * 0.3, 0.0, 1.0) * sides * uOpacity;
        vec3 col = mix(vec3(0.05, 0.065, 0.08), vec3(0.17, 0.2, 0.23), n * vUv.y);
        col += uFlash * vec3(0.5, 0.55, 0.7) * n;
        gl_FragColor = vec4(col, a);
      }`,
    transparent: true,
    depthWrite: false,
    side: DoubleSide,
    fog: false,
  });
  const m = new Mesh(geo, mat);
  m.frustumCulled = false;
  m.renderOrder = 0;
  return m;
}

/** One storm front per watch event: appears at e.i, closes from the horizon to overhead by e.at_i. */
export function StormFronts({ watches }: { watches: WatchEvent[] }) {
  // Build meshes and their group in one memo (StrictMode may run memo factories twice).
  const { fronts, group } = useMemo(() => {
    const fronts = watches.map(() => makeFront());
    const group = new Group();
    fronts.forEach((f) => group.add(f));
    return { fronts, group };
  }, [watches]);

  useFrame(() => {
    watches.forEach((e, k) => {
      const f = fronts[k];
      const t = vis.t;
      const span = Math.max(1, e.at_i - e.i);
      const visible = t >= e.i && t <= e.at_i + LINGER;
      f.visible = visible;
      if (!visible) return;
      const p = Math.min(1, (t - e.i) / span);
      const dist = FAR + (NEAR - FAR) * Math.pow(p, 0.85);
      const fadeIn = Math.min(1, (t - e.i) / 6);
      const fadeOut = t > e.at_i ? 1 - (t - e.at_i) / LINGER : 1;
      f.scale.set(dist, 60 + dist * 0.12, dist);
      const u = (f.material as ShaderMaterial).uniforms;
      u.uTime.value = vis.elapsed;
      u.uOpacity.value = fadeIn * Math.max(0, fadeOut);
      u.uFlash.value = vis.flash;
    });
  });

  if (watches.length === 0) return null;
  return <primitive object={group} />;
}
