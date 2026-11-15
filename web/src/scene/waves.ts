// One wave model, used twice: in GLSL (the sea surface) and in JS (ships, crates and spray ride it).
// Layered Gerstner waves: amplitude and steepness come from vol_ratio, chop (the short waves) from vol_ratio,
// phase speed from wind (state). Each wave moves the surface up and down and pushes it toward the crests,
// so crests sharpen and troughs flatten as steepness rises.

// [dirX, dirZ, wavelength, swell weight, chop weight]
const TABLE: [number, number, number, number, number][] = [
  [1.0, 0.25, 62, 0.46, 0.0],
  [0.7, 0.72, 37, 0.3, 0.04],
  [0.2, 1.0, 23, 0.18, 0.16],
  [0.95, -0.3, 15.5, 0.07, 0.24],
  [-0.55, 0.85, 10.5, 0.03, 0.26],
  [0.85, 0.55, 7.1, 0.0, 0.2],
  [0.35, -0.95, 4.6, 0.0, 0.12],
  [-0.9, -0.2, 3.1, 0.0, 0.07],
];

/**
 * Waves fade out with distance, each before the sea's grid gets too coarse to carry it (the grid is 0.7 units fine
 * out to 105 units and grows about 6.4% a step beyond): a wave of length L fades between about 4 L and 9 L, so it
 * always has six or more grid points per wavelength while it still has height. No wave is ever under-sampled: no
 * facets and no teeth on the horizon. Beyond that the surface is flat geometry and the waves live on in the shading
 * (waveShade, evaluated per pixel, with the fade pushed SHADE_REACH times further out).
 */
export const WAVE_FADE_START = 260;
export const WAVE_FADE_END = 600;
export const SHADE_REACH = 2.6;
const G = 9.8;
interface Wave {
  dx: number;
  dz: number;
  k: number;
  w: number;
  swell: number;
  chop: number;
  /** This wave fades out between these distances from the centre (short waves first: the far grid is coarse). */
  f0: number;
  f1: number;
}
export const WAVES: Wave[] = TABLE.map(([x, z, L, swell, chop]) => {
  const len = Math.hypot(x, z);
  const k = (2 * Math.PI) / L;
  const f0 = Math.min(WAVE_FADE_START, Math.max(60, L * 4));
  const f1 = Math.min(WAVE_FADE_END, Math.max(150, L * 9));
  return { dx: x / len, dz: z / len, k, w: Math.sqrt(G * k) * 0.55, swell, chop, f0, f1 };
});

/** Per-wave sharpness (Q k A) never exceeds this, so the summed crests can never fold over (sum < 1). */
const SHARP_CAP = 0.85 / WAVES.length;
/** Converts steepness x k x A into sharpness: calm swell stays round, a storm sea runs into the cap. */
const SHARP_GAIN = 6;

export interface WaveParams {
  amp: number;
  chop: number;
  /** 0..1: how far the crests are pushed together (Gerstner Q), from vol_ratio. */
  steep: number;
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

// Scratch for the JS evaluation (no allocation per call).
const _d = { x: 0, y: 0, z: 0, nx: 0, ny: 1, nz: 0 };

/** Gerstner displacement and normal of the undisplaced point (x, z). */
function gerstner(x: number, z: number, p: WaveParams) {
  let dx = 0;
  let dy = 0;
  let dz = 0;
  // Partial derivatives of the displaced surface.
  let pxx = 1;
  let pxz = 0;
  let pyx = 0;
  let pyz = 0;
  let pzz = 1;
  const dist = Math.hypot(x, z);
  for (const wv of WAVES) {
    const a = (wv.swell + p.chop * wv.chop) * p.amp * (1 - smoothstep(wv.f0, wv.f1, dist));
    if (a === 0) continue;
    const s = Math.min(SHARP_CAP, p.steep * SHARP_GAIN * wv.k * a); // Q k A
    const ph = (wv.dx * x + wv.dz * z) * wv.k + p.time * wv.w;
    const sn = Math.sin(ph);
    const cs = Math.cos(ph);
    const hor = (s / wv.k) * cs;
    dx += wv.dx * hor;
    dz += wv.dz * hor;
    dy += a * sn;
    const ak = a * wv.k * cs;
    pyx += ak * wv.dx;
    pyz += ak * wv.dz;
    pxx -= s * wv.dx * wv.dx * sn;
    pzz -= s * wv.dz * wv.dz * sn;
    pxz -= s * wv.dx * wv.dz * sn;
  }
  // normal = cross(dP/dz, dP/dx), with dP/dx = (pxx, pyx, pxz) and dP/dz = (pxz, pyz, pzz)
  const nx = pyz * pxz - pzz * pyx;
  const ny = pzz * pxx - pxz * pxz;
  const nz = pxz * pyx - pyz * pxx;
  _d.x = dx;
  _d.y = dy;
  _d.z = dz;
  _d.nx = nx;
  _d.ny = ny;
  _d.nz = nz;
  return _d;
}

/** Height and slope of the sea at world point (x, z): two fixed-point steps undo the horizontal push. */
export function waveAt(x: number, z: number, p: WaveParams, out: WaveSample = { h: 0, dhdx: 0, dhdz: 0 }): WaveSample {
  let qx = x;
  let qz = z;
  for (let k = 0; k < 2; k++) {
    const d = gerstner(qx, qz, p);
    qx = x - d.x;
    qz = z - d.z;
  }
  const d = gerstner(qx, qz, p);
  const ny = Math.max(1e-3, d.ny);
  out.h = d.y;
  out.dhdx = -d.nx / ny;
  out.dhdz = -d.nz / ny;
  return out;
}

const f = (v: number) => (Number.isInteger(v) ? v.toFixed(1) : String(v));

/** Shared uniform objects: every shader that rides the waves references these same objects. */
export const waveUniforms = {
  uWaveAmp: { value: 0.3 },
  uWaveChop: { value: 0.2 },
  uWaveSteep: { value: 0.35 },
  uWaveTime: { value: 0 },
};

/**
 * GLSL: uniforms +
 *   vec3 waveDisp(vec2 p, out vec3 n, out float jac): Gerstner displacement of the undisplaced point p, its normal
 *     and the Jacobian of the horizontal push (1 = untouched, toward 0 = crest squeezed together: whitecaps);
 *   vec3 waveEval(vec2 p): (h, dh/dx, dh/dz) at world point p (one fixed-point step), for things riding the sea.
 */
/** One Gerstner sum as GLSL; `reach` scales the distances over which each wave fades. */
const waveSum = (name: string, reach: number) => /* glsl */ `
vec3 ${name}(vec2 p, out vec3 n, out float jac) {
  vec3 d = vec3(0.0);
  float pxx = 1.0, pxz = 0.0, pyx = 0.0, pyz = 0.0, pzz = 1.0;
  float dist = length(p);
  float a; float s; float ph; float sn; float cs; vec2 D;
${WAVES.map(
  (w) => `  a = (${f(w.swell)} + uWaveChop * ${f(w.chop)}) * uWaveAmp * (1.0 - smoothstep(${f(w.f0 * reach)}, ${f(w.f1 * reach)}, dist));
  s = min(${f(SHARP_CAP)}, uWaveSteep * ${f(SHARP_GAIN * w.k)} * a);
  D = vec2(${f(w.dx)}, ${f(w.dz)});
  ph = dot(D, p) * ${f(w.k)} + uWaveTime * ${f(w.w)};
  sn = sin(ph); cs = cos(ph);
  d.xz += D * (s / ${f(w.k)}) * cs; d.y += a * sn;
  pyx += a * ${f(w.k)} * cs * D.x; pyz += a * ${f(w.k)} * cs * D.y;
  pxx -= s * D.x * D.x * sn; pzz -= s * D.y * D.y * sn; pxz -= s * D.x * D.y * sn;`,
).join("\n")}
  vec3 tx = vec3(pxx, pyx, pxz);
  vec3 tz = vec3(pxz, pyz, pzz);
  n = normalize(cross(tz, tx));
  jac = pxx * pzz - pxz * pxz;
  return d;
}
`;

const WAVE_UNIFORMS_GLSL = /* glsl */ `
uniform float uWaveAmp;
uniform float uWaveChop;
uniform float uWaveSteep;
uniform float uWaveTime;
`;

/** For the sea's fragment shader: the wave uniforms and waveShade(p, n, jac), the same waves with a longer reach. */
export const WAVE_SHADE_GLSL = WAVE_UNIFORMS_GLSL + waveSum("waveShade", SHADE_REACH);

export const WAVE_GLSL = /* glsl */ `${WAVE_UNIFORMS_GLSL}${waveSum("waveDisp", 1)}
vec3 waveEval(vec2 p) {
  vec3 n; float j;
  vec3 d = waveDisp(p, n, j);
  d = waveDisp(p - d.xz, n, j);
  float ny = max(n.y, 1e-3);
  return vec3(d.y, -n.x / ny, -n.z / ny);
}
`;
