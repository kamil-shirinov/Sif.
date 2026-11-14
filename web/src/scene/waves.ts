// One wave model, used twice: in GLSL (the sea surface) and in JS (ships and crates ride it).
// Amplitude comes from vol_ratio, chop from vol_ratio, phase speed from wind (state).

// [dirX, dirZ, wavelength, swell weight, chop weight]
const TABLE: [number, number, number, number, number][] = [
  [1.0, 0.25, 58, 0.5, 0.0],
  [0.65, 0.75, 33, 0.32, 0.05],
  [0.15, 1.0, 19, 0.18, 0.25],
  [-0.55, 0.85, 10.5, 0.04, 0.32],
  [0.9, -0.45, 6.2, 0.0, 0.22],
  [-0.2, -1.0, 3.9, 0.0, 0.12],
];

const G = 9.8;
interface Wave {
  dx: number;
  dz: number;
  k: number;
  w: number;
  swell: number;
  chop: number;
}
export const WAVES: Wave[] = TABLE.map(([x, z, L, swell, chop]) => {
  const len = Math.hypot(x, z);
  const k = (2 * Math.PI) / L;
  return { dx: x / len, dz: z / len, k, w: Math.sqrt(G * k) * 0.55, swell, chop };
});

/** Waves fade out beyond this radius so the far sea does not alias. */
export const WAVE_FADE_START = 260;
export const WAVE_FADE_END = 900;

export interface WaveParams {
  amp: number;
  chop: number;
  time: number;
}

export interface WaveSample {
  h: number;
  dhdx: number;
  dhdz: number;
}

function smoothstep(a: number, b: number, x: number) {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
}

export function waveAt(x: number, z: number, p: WaveParams, out: WaveSample = { h: 0, dhdx: 0, dhdz: 0 }): WaveSample {
  let h = 0;
  let gx = 0;
  let gz = 0;
  for (const wv of WAVES) {
    const a = wv.swell + p.chop * wv.chop;
    if (a === 0) continue;
    const ph = (wv.dx * x + wv.dz * z) * wv.k + p.time * wv.w;
    h += a * Math.sin(ph);
    const c = a * Math.cos(ph) * wv.k;
    gx += c * wv.dx;
    gz += c * wv.dz;
  }
  const att = 1 - smoothstep(WAVE_FADE_START, WAVE_FADE_END, Math.hypot(x, z));
  out.h = h * p.amp * att;
  out.dhdx = gx * p.amp * att;
  out.dhdz = gz * p.amp * att;
  return out;
}

const f = (v: number) => (Number.isInteger(v) ? v.toFixed(1) : String(v));

/** Shared uniform objects: every shader that rides the waves references these same objects. */
export const waveUniforms = {
  uWaveAmp: { value: 0.3 },
  uWaveChop: { value: 0.2 },
  uWaveTime: { value: 0 },
};

/** GLSL: uniforms + vec3 waveEval(vec2 p) returning (h, dh/dx, dh/dz). */
export const WAVE_GLSL = /* glsl */ `
uniform float uWaveAmp;
uniform float uWaveChop;
uniform float uWaveTime;
vec3 waveEval(vec2 p) {
  float h = 0.0; vec2 g = vec2(0.0);
  float a; float ph; float c;
${WAVES.map(
  (w) => `  a = ${f(w.swell)} + uWaveChop * ${f(w.chop)};
  ph = dot(vec2(${f(w.dx)}, ${f(w.dz)}), p) * ${f(w.k)} + uWaveTime * ${f(w.w)};
  h += a * sin(ph); c = a * cos(ph) * ${f(w.k)}; g += c * vec2(${f(w.dx)}, ${f(w.dz)});`,
).join("\n")}
  float att = 1.0 - smoothstep(${f(WAVE_FADE_START)}, ${f(WAVE_FADE_END)}, length(p));
  return vec3(h, g) * uWaveAmp * att;
}
`;
