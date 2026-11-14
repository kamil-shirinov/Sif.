import { useEffect, useMemo } from "react";
import { useFrame, useThree } from "@react-three/fiber";

/** ?stats=1: fps, frame time, draw calls and triangles, measured over the last second. */
export const statsEnabled = (() => {
  try {
    return new URLSearchParams(window.location.search).get("stats") === "1";
  } catch {
    return false;
  }
})();

export interface SceneStats {
  fps: number;
  frameMs: number;
  p95Ms: number;
  calls: number;
  triangles: number;
  dpr: number;
  quality: string;
}

declare global {
  interface Window {
    __sceneStats?: SceneStats;
  }
}

/**
 * Counts every render of a frame (the water's mirror pass and the post-processing passes included): three's
 * renderer info is reset once per animation frame here instead of once per render call.
 */
export function Stats({ quality }: { quality: string }) {
  const gl = useThree((s) => s.gl);
  const el = useMemo(() => {
    const d = document.createElement("div");
    d.className = "scene-stats";
    return d;
  }, []);
  useEffect(() => {
    document.body.appendChild(el);
    gl.info.autoReset = false;
    return () => {
      el.remove();
      gl.info.autoReset = true;
    };
  }, [el, gl]);

  const acc = useMemo(() => ({ last: performance.now(), win: 0, frames: 0, samples: new Float32Array(240), k: 0, calls: 0, tris: 0 }), []);
  useFrame(() => {
    const now = performance.now();
    const dt = now - acc.last;
    acc.last = now;
    // The info counters hold the whole previous frame here.
    acc.calls = gl.info.render.calls;
    acc.tris = gl.info.render.triangles;
    gl.info.reset();
    acc.samples[acc.k++ % acc.samples.length] = dt;
    acc.frames++;
    acc.win += dt;
    if (acc.win >= 1000) {
      const m = Math.min(acc.k, acc.samples.length);
      const sorted = Array.from(acc.samples.subarray(0, m)).sort((a, b) => a - b);
      const s: SceneStats = {
        fps: (acc.frames * 1000) / acc.win,
        frameMs: acc.win / acc.frames,
        p95Ms: sorted[Math.floor(m * 0.95)] ?? 0,
        calls: acc.calls,
        triangles: acc.tris,
        dpr: gl.getPixelRatio(),
        quality,
      };
      window.__sceneStats = s;
      el.textContent = `${s.fps.toFixed(0)} fps · ${s.frameMs.toFixed(1)} ms (p95 ${s.p95Ms.toFixed(1)}) · ${s.calls} calls · ${(s.triangles / 1000).toFixed(0)}k tris · dpr ${s.dpr.toFixed(2)} · ${quality}`;
      acc.win = 0;
      acc.frames = 0;
      acc.k = 0;
    }
  }, -2);
  return null;
}
