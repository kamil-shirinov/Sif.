import { Vector3, type Camera } from "three";

// DOM labels that follow 3D anchors. The overlay registers elements; the scene positions them each frame.
export const labelEls = new Map<string, HTMLElement>();

const _p = new Vector3();

export function hideLabel(id: string) {
  const el = labelEls.get(id);
  if (el) el.style.visibility = "hidden";
}

/** Pin a DOM label to a world point. `clampTop` (NDC y, e.g. 0.7) keeps a label on screen when its anchor rises above it. */
export function placeLabel(id: string, world: Vector3, camera: Camera, width: number, height: number, clampTop?: number) {
  const el = labelEls.get(id);
  if (!el) return;
  const p = _p.copy(world).project(camera);
  const visible = p.z < 1 && p.z > -1 && Math.abs(p.x) < 1.2 && Math.abs(p.y) < 1.2;
  if (!visible) {
    el.style.visibility = "hidden";
    return;
  }
  if (clampTop !== undefined && p.y > clampTop) p.y = clampTop;
  const x = (p.x * 0.5 + 0.5) * width;
  const y = (-p.y * 0.5 + 0.5) * height;
  el.style.visibility = "visible";
  el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) translate(-50%, -100%)`;
}
