/** Pure market-to-sound mapping; gains are linear amplitudes. */
export const clamp = (value: number, low = 0, high = 1): number =>
  Math.min(high, Math.max(low, value));

export function smoothstep(low: number, high: number, value: number): number {
  const x = clamp((value - low) / (high - low));
  return x * x * (3 - 2 * x);
}

export function marketIntensity(risk: number, volRatio: number, state: number): number {
  const safeRisk = Number.isFinite(risk) ? risk : 0;
  const safeVol = Number.isFinite(volRatio) ? volRatio : 1;
  return clamp(0.5 * safeRisk + 0.3 * Math.min(1, (safeVol - 1) / 8) + 0.2 * Number(state === 2));
}

export function ambienceGains(intensity: number): Record<string, number> {
  return {
    sea_calm: 1 - intensity,
    sea_rough: intensity,
    wind: smoothstep(0.2, 0.8, intensity),
    rain: smoothstep(0.35, 0.7, intensity),
    storm: smoothstep(0.6, 1, intensity),
  };
}
