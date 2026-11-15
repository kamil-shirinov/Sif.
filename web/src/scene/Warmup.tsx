import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { HalfFloatType, WebGLRenderTarget, type BufferGeometry, type Object3D } from "three";
import { warmupState } from "./cameraDirector";

interface Touched {
  o: Object3D;
  visible: boolean;
  culled: boolean;
  geo: BufferGeometry | null;
  count: number;
}

/**
 * Draws the whole scene once at load into an offscreen target, hidden objects included (the wreck's foam and planks,
 * the crane, lightning, the sun-break shaft, rain), so that nothing is drawn for the first time while the replay
 * plays. On this Mac (ANGLE on Metal) the cost of a new shader lands on its first draw, not on its compile:
 * each of those objects gave a 50 to 70 ms frame the moment it first appeared.
 *
 * The target matches what the scene is normally drawn into (`throughComposer`: half-float with the tier's MSAA
 * sample count, the post-processing input; otherwise the canvas itself, which the real render overwrites in the same
 * tick). The water's mirror pass runs inside this render too. It runs on the first and third frame after anything
 * that rebuilds materials (`stamp`: a new bundle, a quality tier, the mode).
 *
 * Mount it last: its frame callback must run after every other component's, which have set their uniforms by then.
 */
export function Warmup({ stamp, throughComposer, samples }: { stamp: string; throughComposer: boolean; samples: number }) {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  const target = useMemo(() => new WebGLRenderTarget(96, 64, { type: HalfFloatType, samples }), [samples]);
  useEffect(() => () => target.dispose(), [target]);
  const left = useRef(3);
  const touched = useMemo<Touched[]>(() => [], []);
  useEffect(() => {
    left.current = 3;
    warmupState.pending = true;
  }, [stamp, throughComposer, target]);
  useFrame(() => {
    if (left.current <= 0) return;
    left.current--;
    if (left.current === 0) warmupState.pending = false;
    if (left.current === 1) return;
    // Everything visible, nothing culled, every draw range at least one primitive.
    scene.traverse((o) => {
      const geo = (o as { geometry?: BufferGeometry }).geometry ?? null;
      const count = geo ? geo.drawRange.count : 0;
      if (o.visible && !o.frustumCulled && count !== 0) return;
      touched.push({ o, visible: o.visible, culled: o.frustumCulled, geo, count });
      o.visible = true;
      o.frustumCulled = false;
      if (geo && count === 0) geo.drawRange.count = 6;
    });
    const prev = gl.getRenderTarget();
    gl.setRenderTarget(throughComposer ? target : null);
    gl.render(scene, camera);
    gl.setRenderTarget(prev);
    for (const t of touched) {
      t.o.visible = t.visible;
      t.o.frustumCulled = t.culled;
      if (t.geo) t.geo.drawRange.count = t.count;
    }
    touched.length = 0;
  });
  return null;
}
