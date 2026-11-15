import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { WebGLRenderTarget } from "three";

/**
 * Compiles every material of the scene at load, including those of objects that are still hidden (the wreck's foam,
 * splash rings, the crane, lightning, the sun-break shaft, rain). Without it each of them compiled its shader on the
 * frame it first appeared: 60 to 70 ms frames at the first cut, the first restore, the margin call and the fair wind.
 *
 * `throughComposer`: the scene is drawn into a render target (the post-processing input, the water's mirror), and a
 * program for a render target is a different program from one for the screen (linear output, no tone mapping), so
 * the compile runs with a render target bound. It runs on the first and the third frame after anything that rebuilds
 * materials (`stamp` changes: a new bundle, a quality tier, the mode).
 *
 * Mount it last: its frame callback must run after every other component's, which have set their uniforms by then.
 */
export function Warmup({ stamp, throughComposer }: { stamp: string; throughComposer: boolean }) {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  const target = useMemo(() => new WebGLRenderTarget(4, 4), []);
  useEffect(() => () => target.dispose(), [target]);
  const left = useRef(3);
  useEffect(() => {
    left.current = 3;
  }, [stamp, throughComposer]);
  useFrame(() => {
    if (left.current <= 0) return;
    left.current--;
    if (left.current === 1) return;
    const prev = gl.getRenderTarget();
    gl.setRenderTarget(throughComposer ? target : null);
    gl.compile(scene, camera);
    gl.setRenderTarget(prev);
  });
  return null;
}
