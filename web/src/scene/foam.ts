/** GLSL value noise shared by the foam shaders (splash rings, the foam a sinking ship leaves). */
export const FOAM_NOISE_GLSL = /* glsl */ `
float fmHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float fmNoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(fmHash(i), fmHash(i + vec2(1.0, 0.0)), u.x), mix(fmHash(i + vec2(0.0, 1.0)), fmHash(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fmFbm(vec2 p) { return 0.5 * fmNoise(p) + 0.28 * fmNoise(p * 2.13 + 4.7) + 0.15 * fmNoise(p * 4.31 - 2.9) + 0.07 * fmNoise(p * 8.7 + 1.3); }
`;

/** How bright foam, spray and wakes are: daylight dimmed by the storm, lifted by lightning and the lanterns. */
export function foamLight(dayFactor: number, risk: number, flash: number, lantern: number): number {
  return Math.min(1.5, 0.1 + 0.9 * dayFactor * (1 - 0.55 * risk) + flash * 1.2 + 0.08 * lantern);
}
