import { useEffect, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { CircleGeometry, Color, DoubleSide, Mesh, ShaderMaterial } from "three";
import { vis } from "./vis";

// Two decks of storm cloud under the sky, at different heights and speeds, so the sky has depth (parallax) as the
// camera orbits. Cover and darkness from risk (thinned by a fair wind, like the sky); drift speed from the wind
// (series.state); a lightning strike lights the cloud base around the bolt for its few frames.

const DECKS = [
  { y: 560, radius: 4200, scale: 0.0016, speed: 1.0, alpha: 0.95 },
  { y: 820, radius: 5200, scale: 0.0009, speed: 0.55, alpha: 0.8 },
];

const FRAG = /* glsl */ `
uniform float uTime; uniform float uCover; uniform float uDense; uniform float uScale; uniform float uAlpha;
uniform vec3 uLit; uniform vec3 uShade; uniform vec2 uWind; uniform vec3 uFlashPos; uniform float uFlash; uniform float uRadius;
varying vec3 vW;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
float fbm(vec2 p) { float s = 0.0, a = 0.5; for (int k = 0; k < 4; k++) { s += a * vnoise(p); p = p * 2.07 + 1.3; a *= 0.5; } return s; }
void main() {
  vec2 p = vW.xz * uScale + uWind * uTime;
  float n = fbm(p + 0.35 * vec2(fbm(p * 0.5 + 3.1), fbm(p * 0.5 - 1.7)));
  float thr = 1.0 - uCover;
  float d = smoothstep(thr * 0.75, thr * 0.75 + 0.35, n);
  float r = length(vW.xz) / uRadius;
  float edge = 1.0 - smoothstep(0.55, 1.0, r);
  float a = d * edge * uAlpha * uDense;
  if (a < 0.003) discard;
  // Thick cloud is darker underneath; thin edges catch the light.
  vec3 col = mix(uLit, uShade, smoothstep(0.2, 0.9, d * uDense));
  float fl = uFlash * (1.0 - smoothstep(0.0, 900.0, length(vW.xz - uFlashPos.xz)));
  col += vec3(0.75, 0.8, 1.0) * fl * (0.6 + 0.8 * n);
  gl_FragColor = vec4(max(col, 0.0), clamp(a, 0.0, 1.0));
}`;

const LIT_DAY = new Color("#9aa7b4");
const SHADE_DAY = new Color("#2e3840");
const LIT_STORM = new Color("#4a535c");
const SHADE_STORM = new Color("#0d1115");

export function Clouds({ lowQuality }: { lowQuality: boolean }) {
  const decks = useMemo(
    () =>
      DECKS.map((d) => {
        const mat = new ShaderMaterial({
          uniforms: {
            uTime: { value: 0 },
            uCover: { value: 0.2 },
            uDense: { value: 0.5 },
            uScale: { value: d.scale },
            uAlpha: { value: d.alpha },
            uRadius: { value: d.radius },
            uLit: { value: new Color() },
            uShade: { value: new Color() },
            uWind: { value: [0, 0] },
            uFlashPos: { value: vis.flashPos },
            uFlash: { value: 0 },
          },
          vertexShader: /* glsl */ `
            varying vec3 vW;
            void main() { vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`,
          fragmentShader: FRAG,
          transparent: true,
          depthWrite: false,
          side: DoubleSide,
          fog: false,
        });
        const m = new Mesh(new CircleGeometry(d.radius, 48), mat);
        m.rotation.x = -Math.PI / 2;
        m.position.y = d.y;
        m.renderOrder = 1;
        m.frustumCulled = false;
        return { m, mat, d };
      }),
    [],
  );
  useEffect(
    () => () => {
      for (const { m, mat } of decks) {
        m.geometry.dispose();
        mat.dispose();
      }
    },
    [decks],
  );

  const drift = useMemo(() => ({ x: 0, z: 0 }), []);
  useFrame(() => {
    const r = vis.risk * (1 - 0.55 * vis.fairWind);
    // Wind blows the decks from the storm-front side (-z) over the ships; faster in a storm.
    drift.x += vis.dt * (0.006 + 0.05 * vis.wind);
    drift.z += vis.dt * (0.004 + 0.03 * vis.wind);
    const light = Math.max(0.04, vis.dayFactor) * (1 - 0.35 * r);
    decks.forEach(({ m, mat, d }, k) => {
      m.visible = !(lowQuality && k > 0);
      const u = mat.uniforms;
      u.uTime.value = 1;
      (u.uWind.value as number[])[0] = drift.x * d.speed;
      (u.uWind.value as number[])[1] = drift.z * d.speed;
      u.uCover.value = 0.25 + 0.7 * r;
      u.uDense.value = 0.35 + 0.65 * r;
      (u.uLit.value as Color).copy(LIT_DAY).lerp(LIT_STORM, r).multiplyScalar(light);
      (u.uShade.value as Color).copy(SHADE_DAY).lerp(SHADE_STORM, r).multiplyScalar(light);
      u.uFlash.value = vis.flash * 2.2;
    });
  });
  return (
    <>
      {decks.map(({ m }, k) => (
        <primitive key={k} object={m} />
      ))}
    </>
  );
}
