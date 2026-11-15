import { useEffect, useMemo } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import {
  Color,
  DataTexture,
  DynamicDrawUsage,
  InstancedBufferAttribute,
  InstancedBufferGeometry,
  LinearFilter,
  Mesh,
  PlaneGeometry,
  RedFormat,
  RepeatWrapping,
  ShaderMaterial,
  UnsignedByteType,
  Vector3,
  type FogExp2,
} from "three";
import type { Bundle } from "../types/bundle";
import type { Derived } from "../lib/derive";
import { sampleAt } from "../lib/derive";
import { vis } from "./vis";
import { strikeZone } from "./Lightning";
import { makeStormTrack } from "./stormTrack";

// A storm cell: one cumulonimbus built from a few hundred lit, camera-facing puffs (layered impostors): a dark flat
// base, a tower, an anvil spreading downwind, rain shafts under it, lightning inside. Where it is comes from
// stormTrack.ts, which reads only the data up to the current frame. The same puff system draws the fair-weather
// cumulus that stands far off on a calm day.

/** Distance of the upwind and downwind horizon points of the track from the ships. */
const TRACK_RADIUS = 1500;
/** The cell comes in from the far left behind the ships and leaves to the far right: both ends in the default view. */
const APPROACH = new Vector3(-0.74, 0, -0.67).normalize();
const EXIT = new Vector3(0.88, 0, -0.47).normalize();
// Sizes are set by what the default camera can see: it looks almost level, so only the lowest 16 degrees of sky are
// in frame. On the horizon (1500 away) the whole cell, anvil included, stands inside that band; over the ships its
// base is a dark shelf across the top of the frame with the rain shafts hanging from it behind the ships.
const BASE_Y = 110; // cloud base
const TOP_Y = 470; // anvil top
const BASE_R = 430; // radius of the base and the rain under it
/** "Over the ships": the cell's core stands a little behind them, so its shelf and rain are in the default view. */
const OVER = new Vector3(-60, 0, -360);
const FAIR_COUNT = 34; // fair-weather clouds on the horizon

/** Tileable value-noise texture for eroding the puffs' edges (generated once). */
function makeNoise(): DataTexture {
  const N = 128;
  const data = new Uint8Array(N * N);
  const hash = (x: number, y: number, s: number) => {
    const v = Math.sin((x % s) * 127.1 + (y % s) * 311.7 + s * 17.3) * 43758.5453;
    return v - Math.floor(v);
  };
  const noise = (x: number, y: number, s: number) => {
    const xi = Math.floor(x), yi = Math.floor(y);
    const xf = x - xi, yf = y - yi;
    const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
    const a = hash(xi, yi, s), b = hash(xi + 1, yi, s), c = hash(xi, yi + 1, s), d = hash(xi + 1, yi + 1, s);
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
  };
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      let v = 0;
      let amp = 0.5;
      for (let o = 0, s = 4; o < 5; o++, s *= 2) {
        v += amp * noise((x / N) * s, (y / N) * s, s);
        amp *= 0.5;
      }
      data[y * N + x] = Math.round(255 * Math.min(1, v / 0.97));
    }
  }
  const t = new DataTexture(data, N, N, RedFormat, UnsignedByteType);
  t.wrapS = t.wrapT = RepeatWrapping;
  t.magFilter = t.minFilter = LinearFilter;
  t.needsUpdate = true;
  return t;
}

interface Puff {
  x: number;
  y: number;
  z: number;
  size: number;
  seed: number;
  /** 0 = part of the storm cell (cell-local position), 1 = a fair-weather cloud (world position). */
  kind: number;
  /** Cell: how built the cell must be before this puff shows (base first, anvil last). */
  grow: number;
}

function makePuffs(): Puff[] {
  let s = 20260730;
  const r = () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
  const out: Puff[] = [];
  const H = TOP_Y - BASE_Y;
  // Base: a wide, flat, dark shelf.
  for (let k = 0; k < 46; k++) {
    const a = r() * Math.PI * 2;
    const d = Math.sqrt(r()) * BASE_R;
    out.push({ x: Math.cos(a) * d, y: BASE_Y + r() * 35, z: Math.sin(a) * d * 0.9, size: 95 + r() * 70, seed: r(), kind: 0, grow: 0.02 + 0.12 * r() });
  }
  // Tower: stacked turrets, narrowing a little with height.
  for (let k = 0; k < 70; k++) {
    const h = Math.pow(r(), 0.8);
    const rad = BASE_R * (0.62 - 0.22 * h) * Math.sqrt(r());
    const a = r() * Math.PI * 2;
    out.push({ x: Math.cos(a) * rad, y: BASE_Y + 35 + h * H * 0.7, z: Math.sin(a) * rad * 0.85, size: 70 + r() * 70, seed: r(), kind: 0, grow: 0.12 + 0.55 * h });
  }
  // Anvil: a flat sheet at the top, spreading downwind (+x in cell space, turned to the exit direction).
  for (let k = 0; k < 56; k++) {
    const along = -0.35 + 1.6 * r();
    const across = (r() - 0.5) * (0.9 + 0.5 * Math.max(0, along));
    out.push({ x: along * BASE_R * 1.25, y: TOP_Y - 55 + r() * 55 - 25 * Math.abs(across), z: across * BASE_R * 1.3, size: 80 + r() * 70, seed: r(), kind: 0, grow: 0.72 + 0.26 * r() });
  }
  // Fair-weather cumulus: small flat-bottomed heaps far off, all round the horizon.
  for (let c = 0; c < FAIR_COUNT; c++) {
    const a = (c / FAIR_COUNT) * Math.PI * 2 + r() * 0.2;
    const d = 1700 + r() * 1300;
    const cy = 150 + r() * 190;
    const w = 130 + r() * 190;
    const n = 4 + Math.floor(r() * 3);
    for (let k = 0; k < n; k++) {
      const o = (k / (n - 1) - 0.5) * w * 1.5;
      const lift = (1 - Math.abs(k / (n - 1) - 0.5) * 2) * w * 0.3;
      out.push({ x: Math.cos(a) * d - Math.sin(a) * o, y: cy + lift * (0.5 + r()), z: Math.sin(a) * d + Math.cos(a) * o, size: w * (0.5 + 0.35 * r()), seed: r(), kind: 1, grow: 0 });
    }
  }
  return out;
}

const VERT = /* glsl */ `
attribute vec3 aCenter; attribute vec4 aInfo; // size, seed, kind, grow
uniform vec3 uCellPos; uniform float uCellScale; uniform float uLife; uniform float uFair; uniform float uYaw;
varying vec2 vUv; varying float vAlpha; varying float vH; varying float vSeed; varying float vKind; varying float vDist; varying vec3 vCenter;
void main() {
  vUv = uv; vSeed = aInfo.y; vKind = aInfo.z;
  vec3 c; float size = aInfo.x;
  if (aInfo.z < 0.5) {
    // The anvil points downwind: turn the cell about its axis.
    float cs = cos(uYaw), sn = sin(uYaw);
    vec3 l = vec3(aCenter.x * cs - aCenter.z * sn, aCenter.y, aCenter.x * sn + aCenter.z * cs);
    // A young cell is lower and narrower; it reaches its full height only when fully built.
    float tall = 0.45 + 0.55 * uLife;
    c = uCellPos + vec3(l.x * uCellScale, ${BASE_Y.toFixed(1)} + (l.y - ${BASE_Y.toFixed(1)}) * uCellScale * tall, l.z * uCellScale);
    size *= uCellScale;
    vH = clamp((aCenter.y - ${BASE_Y.toFixed(1)}) / ${(TOP_Y - BASE_Y).toFixed(1)}, 0.0, 1.0);
    vAlpha = smoothstep(aInfo.w, aInfo.w + 0.22, uLife);
  } else {
    c = aCenter;
    vH = 0.75;
    vAlpha = uFair;
  }
  vCenter = c;
  vec4 mv = viewMatrix * vec4(c, 1.0);
  vDist = -mv.z;
  mv.xy += position.xy * size * 2.0;
  gl_Position = projectionMatrix * mv;
}`;

const FRAG = /* glsl */ `
uniform sampler2D uNoise; uniform vec3 uSunView; uniform vec3 uLit; uniform vec3 uShade; uniform vec3 uBase; uniform vec3 uFog;
uniform float uFogDensity; uniform float uTime; uniform float uPower; uniform vec3 uFlashPos; uniform float uFlash;
varying vec2 vUv; varying float vAlpha; varying float vH; varying float vSeed; varying float vKind; varying float vDist; varying vec3 vCenter;
void main() {
  if (vAlpha < 0.004) discard;
  vec2 p = vUv * 2.0 - 1.0;
  float r = length(p);
  // Billowing, eroded edge: two octaves of noise drifting slowly, different on every puff.
  vec2 q = vUv * 0.55 + vSeed * 7.31;
  float n = texture2D(uNoise, q + vec2(uTime * 0.004, 0.0)).r * 0.65 + texture2D(uNoise, q * 2.7 - vec2(0.0, uTime * 0.007)).r * 0.35;
  float body = 1.0 - smoothstep(0.42, 1.0, r + (n - 0.5) * 0.85);
  // Fair-weather heaps have flat bottoms.
  if (vKind > 0.5) body *= smoothstep(-0.55, -0.2, p.y + (n - 0.5) * 0.2);
  float a = body * vAlpha;
  if (a < 0.01) discard;
  // Shade it as a sphere, roughened by the noise: lit on the sun's side, dark underneath.
  vec3 nrm = normalize(vec3(p + (n - 0.5) * 0.7, sqrt(max(0.0, 1.0 - min(r * r, 1.0))) + 0.25));
  float sun = clamp(dot(nrm, uSunView) * 0.55 + 0.5, 0.0, 1.0);
  float under = clamp(-nrm.y * 0.5 + 0.5, 0.0, 1.0);
  // Tops catch the sky's light whatever side the sun is on; with the sun behind the cloud its edges glow (silver lining).
  float top = smoothstep(-0.2, 0.9, nrm.y);
  float rim = smoothstep(0.45, 1.0, r) * max(0.0, -uSunView.z) * body;
  vec3 col = mix(uShade, uLit, clamp(max(sun * sun, top * 0.75) + rim * 0.6, 0.0, 1.0));
  // The storm cell: a dark base (darker with power), a pale tower, a grey-white anvil.
  if (vKind < 0.5) {
    float baseDark = (1.0 - smoothstep(0.0, 0.3, vH)) * (0.5 + 0.5 * uPower);
    col = mix(col, uBase, clamp(baseDark + under * 0.35 * (1.0 - vH), 0.0, 1.0));
    col *= 0.86 + 0.14 * n;
    // Lightning inside the cloud lights it from within.
    float fl = uFlash * exp(-distance(vCenter, uFlashPos) / 320.0);
    col += vec3(0.75, 0.82, 1.0) * fl * (0.6 + 0.8 * n);
  } else {
    // Fair-weather cumulus: white heaps with a blue-grey underside.
    col = mix(mix(uShade, uLit, 0.55), uLit, clamp(max(sun * sun, top), 0.0, 1.0));
    col = mix(col, uShade, under * under * 0.7);
  }
  // Aerial perspective: far clouds take the haze colour, but never vanish into it.
  float fogF = 1.0 - exp(-pow(vDist * uFogDensity, 2.0));
  col = mix(col, uFog, min(fogF, 0.72) * (vKind > 0.5 ? 0.3 : 0.75));
  gl_FragColor = vec4(max(col, 0.0), clamp(a, 0.0, 1.0));
}`;

const RAIN_VERT = /* glsl */ `
attribute vec4 aShaft; // x, z offset in the cell; width; seed
uniform vec3 uCellPos; uniform float uCellScale;
varying vec2 vUv; varying float vSeed; varying float vDist;
void main() {
  vUv = uv; vSeed = aShaft.w;
  vec3 foot = uCellPos + vec3(aShaft.x, 0.0, aShaft.y) * uCellScale;
  vec3 toCam = cameraPosition - foot; toCam.y = 0.0;
  float len = max(length(toCam), 1e-3);
  vec3 right = vec3(toCam.z, 0.0, -toCam.x) / len;
  vec3 wp = foot + right * position.x * aShaft.z * uCellScale + vec3(0.0, (position.y + 0.5) * ${(BASE_Y + 25).toFixed(1)}, 0.0);
  vec4 mv = viewMatrix * vec4(wp, 1.0);
  vDist = -mv.z;
  gl_Position = projectionMatrix * mv;
}`;
const RAIN_FRAG = /* glsl */ `
uniform sampler2D uNoise; uniform vec3 uColor; uniform float uOpacity; uniform float uTime;
varying vec2 vUv; varying float vSeed; varying float vDist;
void main() {
  float x = vUv.x * 2.0 - 1.0;
  float side = 1.0 - smoothstep(0.35, 1.0, abs(x));
  // Streaks falling and leaning: stretched noise scrolling down.
  float n = texture2D(uNoise, vec2(vUv.x * 1.6 + vSeed * 3.1 + vUv.y * 0.12, vUv.y * 0.22 + uTime * 0.06 + vSeed)).r;
  float streak = smoothstep(0.3, 0.75, n);
  float top = smoothstep(1.0, 0.8, vUv.y);
  float foot = 0.55 + 0.45 * smoothstep(0.0, 0.25, vUv.y);
  float a = uOpacity * side * top * foot * (0.35 + 0.65 * streak) * smoothstep(40.0, 160.0, vDist);
  if (a < 0.008) discard;
  gl_FragColor = vec4(uColor, clamp(a, 0.0, 1.0));
}`;

const LIT_DAY = new Color(1.0, 0.99, 0.96);
const SHADE_DAY = new Color(0.4, 0.47, 0.57);
const SHADE_STORM = new Color(0.2, 0.24, 0.29);
const BASE_DARK = new Color(0.07, 0.09, 0.12);
const NIGHT_TINT = new Color(0.1, 0.14, 0.24);
const RAIN_COLOR = new Color(0.2, 0.25, 0.3);
const _sun = new Vector3();
const _v = new Vector3();
const damp = (cur: number, target: number, rate: number, dt: number) => cur + (target - cur) * (1 - Math.exp(-rate * dt));

/** The storm cell and the fair-weather clouds. Position, build and power from stormTrack (risk and alarm, past only). */
export function StormCell({ bundle, derived }: { bundle: Bundle; derived: Derived }) {
  const camera = useThree((s) => s.camera);
  const scene = useThree((s) => s.scene);
  const track = useMemo(() => makeStormTrack(bundle, derived), [bundle, derived]);
  const puffs = useMemo(makePuffs, []);
  const noise = useMemo(makeNoise, []);

  const cloud = useMemo(() => {
    const quad = new PlaneGeometry(1, 1);
    const g = new InstancedBufferGeometry();
    g.index = quad.index;
    g.setAttribute("position", quad.attributes.position);
    g.setAttribute("uv", quad.attributes.uv);
    const aCenter = new InstancedBufferAttribute(new Float32Array(puffs.length * 3), 3).setUsage(DynamicDrawUsage);
    const aInfo = new InstancedBufferAttribute(new Float32Array(puffs.length * 4), 4).setUsage(DynamicDrawUsage);
    g.setAttribute("aCenter", aCenter);
    g.setAttribute("aInfo", aInfo);
    g.instanceCount = puffs.length;
    const mat = new ShaderMaterial({
      uniforms: {
        uNoise: { value: noise },
        uCellPos: { value: new Vector3() },
        uCellScale: { value: 1 },
        uLife: { value: 0 },
        uFair: { value: 1 },
        uYaw: { value: Math.atan2(EXIT.z, EXIT.x) },
        uSunView: { value: new Vector3(0, 1, 0) },
        uLit: { value: new Color() },
        uShade: { value: new Color() },
        uBase: { value: new Color() },
        uFog: { value: new Color() },
        uFogDensity: { value: 0.0005 },
        uTime: { value: 0 },
        uPower: { value: 0 },
        uFlashPos: { value: vis.flashPos },
        uFlash: { value: 0 },
      },
      vertexShader: VERT,
      fragmentShader: FRAG,
      transparent: true,
      depthWrite: false,
      fog: false,
    });
    const m = new Mesh(g, mat);
    m.frustumCulled = false;
    m.renderOrder = 2;
    return { m, mat, aCenter, aInfo, quad };
  }, [puffs, noise]);

  const rain = useMemo(() => {
    const SHAFTS = 7;
    const quad = new PlaneGeometry(2, 1, 1, 1);
    const g = new InstancedBufferGeometry();
    g.index = quad.index;
    g.setAttribute("position", quad.attributes.position);
    g.setAttribute("uv", quad.attributes.uv);
    const a = new Float32Array(SHAFTS * 4);
    for (let k = 0; k < SHAFTS; k++) {
      const ang = (k / SHAFTS) * Math.PI * 2 + k * 0.7;
      const d = (0.15 + 0.5 * ((k * 37) % 11) / 11) * BASE_R;
      a.set([Math.cos(ang) * d, Math.sin(ang) * d * 0.85, 70 + ((k * 53) % 7) * 16, k * 0.173], k * 4);
    }
    g.setAttribute("aShaft", new InstancedBufferAttribute(a, 4));
    g.instanceCount = SHAFTS;
    const mat = new ShaderMaterial({
      uniforms: { uNoise: { value: noise }, uCellPos: cloud.mat.uniforms.uCellPos, uCellScale: cloud.mat.uniforms.uCellScale, uColor: { value: new Color() }, uOpacity: { value: 0 }, uTime: { value: 0 } },
      vertexShader: RAIN_VERT,
      fragmentShader: RAIN_FRAG,
      transparent: true,
      depthWrite: false,
      fog: false,
    });
    const m = new Mesh(g, mat);
    m.frustumCulled = false;
    m.renderOrder = 2;
    return { m, mat, quad };
  }, [noise, cloud]);

  useEffect(
    () => () => {
      cloud.m.geometry.dispose();
      cloud.quad.dispose();
      cloud.mat.dispose();
      rain.m.geometry.dispose();
      rain.quad.dispose();
      rain.mat.dispose();
      strikeZone.active = false;
    },
    [cloud, rain],
  );
  useEffect(() => () => noise.dispose(), [noise]);

  // Back-to-front order of the puffs (they blend): re-sorted a few times a second, in place.
  const order = useMemo(() => puffs.map((_, i) => i), [puffs]);
  const depth = useMemo(() => new Float32Array(puffs.length), [puffs]);
  const st = useMemo(() => ({ u: -1, life: 0, power: 0, tick: 0, x: 0, z: 0, scale: 1 }), []);

  useFrame(() => {
    const t = vis.t;
    const dt = vis.dt;
    // The track, sampled at the playhead and eased (a seek settles within a second).
    st.u = damp(st.u, sampleAt(track.u, t), 2.5, dt);
    st.life = damp(st.life, sampleAt(track.life, t), 2.5, dt);
    st.power = damp(st.power, sampleAt(track.power, t), 2.5, dt);
    const dir = st.u < 0 ? APPROACH : EXIT;
    const dist = Math.abs(st.u) * TRACK_RADIUS;
    st.x = OVER.x + dir.x * dist;
    st.z = OVER.z + dir.z * dist;
    st.scale = 0.55 + 0.45 * st.life;
    vis.cellX = st.x;
    vis.cellZ = st.z;
    vis.cellLife = st.life;
    vis.cellNear = Math.max(0, 1 - Math.abs(st.u) / 0.3) * st.life;

    const u = cloud.mat.uniforms;
    (u.uCellPos.value as Vector3).set(st.x, 0, st.z);
    u.uCellScale.value = st.scale;
    u.uLife.value = st.life;
    u.uPower.value = st.power;
    u.uTime.value = vis.elapsed;
    u.uFlash.value = vis.flash * 2.4;
    // Fair-weather clouds stand on the horizon while it is calm and thin out as risk rises.
    u.uFair.value = Math.max(0, 1 - Math.max(0, vis.risk - 0.12) / 0.4) * (0.25 + 0.75 * vis.dayFactor);
    // Light: the sun by day (in view space, for the sphere shading), dim blue at night; darker with the storm.
    const day = vis.dayFactor;
    _sun.copy(vis.sunDir).transformDirection(camera.matrixWorldInverse);
    (u.uSunView.value as Vector3).copy(_sun);
    const light = (0.07 + 0.93 * day) * (1 - 0.3 * vis.risk);
    (u.uLit.value as Color).copy(LIT_DAY).multiplyScalar(light).lerp(NIGHT_TINT, (1 - day) * 0.6);
    (u.uShade.value as Color).copy(SHADE_DAY).lerp(SHADE_STORM, Math.min(1, vis.risk + st.power * 0.5)).multiplyScalar(light).lerp(NIGHT_TINT, (1 - day) * 0.4);
    (u.uBase.value as Color).copy(BASE_DARK).multiplyScalar(0.25 + 0.75 * day);
    const fog = scene.fog as FogExp2 | null;
    if (fog) {
      (u.uFog.value as Color).copy(fog.color);
      u.uFogDensity.value = Math.min(fog.density, 0.0009);
    }

    const ru = rain.mat.uniforms;
    ru.uOpacity.value = st.life * (0.25 + 0.6 * st.power) * Math.min(1, st.life * 1.5);
    ru.uTime.value = vis.elapsed;
    (ru.uColor.value as Color).copy(RAIN_COLOR).multiplyScalar(0.2 + 0.8 * day).lerp(fog ? fog.color : RAIN_COLOR, 0.45);
    rain.m.visible = ru.uOpacity.value > 0.01;

    // Lightning strikes under the cell whenever one stands.
    strikeZone.active = st.life > 0.25;
    strikeZone.x = st.x;
    strikeZone.z = st.z;
    strikeZone.radius = BASE_R * 0.6 * st.scale;
    strikeZone.top = BASE_Y + 60;

    // Sort back to front every sixth frame (insertion sort: the order barely changes between sorts).
    if (st.tick++ % 6 === 0) {
      const cs = Math.cos(u.uYaw.value);
      const sn = Math.sin(u.uYaw.value);
      const tall = 0.45 + 0.55 * st.life;
      for (let i = 0; i < puffs.length; i++) {
        const p = puffs[i];
        if (p.kind < 0.5) _v.set(st.x + (p.x * cs - p.z * sn) * st.scale, BASE_Y + (p.y - BASE_Y) * st.scale * tall, st.z + (p.x * sn + p.z * cs) * st.scale);
        else _v.set(p.x, p.y, p.z);
        depth[i] = _v.distanceToSquared(camera.position);
      }
      for (let i = 1; i < order.length; i++) {
        const k = order[i];
        const dk = depth[k];
        let j = i - 1;
        while (j >= 0 && depth[order[j]] < dk) {
          order[j + 1] = order[j];
          j--;
        }
        order[j + 1] = k;
      }
      const ac = cloud.aCenter.array as Float32Array;
      const ai = cloud.aInfo.array as Float32Array;
      for (let i = 0; i < order.length; i++) {
        const p = puffs[order[i]];
        ac[i * 3] = p.x;
        ac[i * 3 + 1] = p.y;
        ac[i * 3 + 2] = p.z;
        ai[i * 4] = p.size;
        ai[i * 4 + 1] = p.seed;
        ai[i * 4 + 2] = p.kind;
        ai[i * 4 + 3] = p.grow;
      }
      cloud.aCenter.needsUpdate = true;
      cloud.aInfo.needsUpdate = true;
    }
  });

  return (
    <>
      <primitive object={cloud.m} />
      <primitive object={rain.m} />
    </>
  );
}
