import { DataTexture, LinearMipmapLinearFilter, LinearFilter, RepeatWrapping, RGBAFormat, UnsignedByteType } from "three";

// Procedural, tileable water normal map (no external textures).
// Height field = sum of random sinusoids with integer frequencies, so it tiles exactly.
export function makeWaterNormals(size = 256, seed = 7): DataTexture {
  let s = seed;
  const rand = () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
  const waves: { fx: number; fy: number; amp: number; phase: number }[] = [];
  for (let k = 0; k < 48; k++) {
    const r = 1 + Math.floor(rand() * 22);
    const ang = rand() * Math.PI * 2;
    const fx = Math.round(Math.cos(ang) * r);
    const fy = Math.round(Math.sin(ang) * r);
    if (fx === 0 && fy === 0) continue;
    waves.push({ fx, fy, amp: 1 / Math.pow(Math.hypot(fx, fy), 1.15), phase: rand() * Math.PI * 2 });
  }
  const data = new Uint8Array(size * size * 4);
  const TAU = Math.PI * 2;
  const strength = 2.2;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const u = x / size;
      const v = y / size;
      let dx = 0;
      let dy = 0;
      for (const w of waves) {
        const c = Math.cos(TAU * (w.fx * u + w.fy * v) + w.phase) * w.amp * TAU;
        dx += c * w.fx;
        dy += c * w.fy;
      }
      dx *= strength / size;
      dy *= strength / size;
      const nx = -dx;
      const ny = -dy;
      const nz = 1;
      const len = Math.hypot(nx, ny, nz);
      const i = (y * size + x) * 4;
      data[i] = Math.round(((nx / len) * 0.5 + 0.5) * 255);
      data[i + 1] = Math.round(((ny / len) * 0.5 + 0.5) * 255);
      data[i + 2] = Math.round(((nz / len) * 0.5 + 0.5) * 255);
      data[i + 3] = 255;
    }
  }
  const tex = new DataTexture(data, size, size, RGBAFormat, UnsignedByteType);
  tex.wrapS = tex.wrapT = RepeatWrapping;
  tex.magFilter = LinearFilter;
  tex.minFilter = LinearMipmapLinearFilter;
  tex.generateMipmaps = true;
  tex.anisotropy = 4;
  tex.needsUpdate = true;
  return tex;
}
