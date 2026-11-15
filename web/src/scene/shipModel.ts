import {
  BoxGeometry,
  BufferAttribute,
  BufferGeometry,
  CanvasTexture,
  Color,
  CylinderGeometry,
  DoubleSide,
  MeshStandardMaterial,
  Quaternion,
  RepeatWrapping,
  SRGBColorSpace,
  Vector3,
} from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

// Procedural coaster: everything here is generated in code (no external assets). Hull-local axes: +x is the bow,
// +y up, +z starboard. The main deck is y = 0, the keel y = -HULL_H.

export const HULL_L = 15; // length
export const HULL_B = 4.6; // beam
export const HULL_H = 2.7; // depth, deck to keel
export const PAINT_LINE = -1.3; // design waterline: antifouling red below, a white boot stripe just above
export const BULWARK = 0.42; // the hull side rises this far above the deck
/** Cargo deck (hatch) where the containers stand. */
export const DECK = { x0: -2.1, x1: 4.9, z0: -1.86, z1: 1.86 };
export const MAST_X = -2.75;
export const MAST_TOP = 9.2;
export const YARD_Y = 7.6;
export const SAIL_W = 4.4;
export const SAIL_H = 4.5;

const smooth = (a: number, b: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};
const mix = (a: number, b: number, t: number) => a + (b - a) * t;

/** Half breadth at the deck edge, t = 0 at the transom, 1 at the stem. */
function halfBeam(t: number): number {
  const hb = HULL_B / 2;
  if (t < 0.16) return hb * mix(0.8, 1, smooth(0, 0.16, t));
  if (t < 0.6) return hb;
  return Math.max(0.03, hb * (1 - Math.pow((t - 0.6) / 0.4, 2.3)));
}
/** Deck height: flat over the cargo deck, rising to a forecastle at the bow and a little at the stern. */
export function sheerAt(t: number): number {
  return 1.05 * smooth(0.8, 0.9, t) + 0.25 * Math.pow(Math.max(0, (t - 0.9) / 0.1), 2);
}
/** Keel height: rises to the transom (a counter stern) and a little at the forefoot. */
function keelAt(t: number): number {
  const aft = mix(0.38, 1, smooth(0, 0.22, t));
  const fore = 1 - 0.3 * Math.pow(Math.max(0, (t - 0.88) / 0.12), 2);
  return -HULL_H * aft * fore;
}
/** Section fullness: boxy amidships, a V with flare toward the bow, a softer U at the stern. */
function fullness(t: number): number {
  if (t < 0.22) return mix(2.4, 4.2, smooth(0, 0.22, t));
  return mix(4.2, 1.28, smooth(0.5, 0.98, t));
}

const STATIONS = 44;
const RING = 10; // points from keel to sheer on each side

/** Position on the hull surface: t along the hull, s from 0 (keel centre) to 1 (top of the bulwark). */
function hullPoint(t: number, s: number, side: number, out: Vector3): Vector3 {
  const b = halfBeam(t);
  const yk = keelAt(t);
  const top = sheerAt(t) + BULWARK;
  const n = fullness(t);
  const phi = (s * Math.PI) / 2;
  const z = b * Math.pow(Math.sin(phi), 2 / n);
  const y = yk + (top - yk) * (1 - Math.pow(Math.cos(phi), 2 / n));
  // Raked stem: the keel is shorter than the deck at the bow. A little tumble-home rake at the transom.
  const rake = (1 - s) * 2.1 * Math.pow(Math.max(0, (t - 0.72) / 0.28), 1.6) - (1 - s) * 0.5 * (1 - smooth(0, 0.12, t));
  return out.set(-HULL_L / 2 + t * HULL_L - rake, y, side * z);
}

/** The hull shell (both sides, the transom, the inside of the bulwark is the same surface seen from behind). */
export function makeHullGeometry(): BufferGeometry {
  const pos: number[] = [];
  const idx: number[] = [];
  const v = new Vector3();
  const per = RING * 2 + 1; // port sheer .. keel .. starboard sheer
  for (let i = 0; i <= STATIONS; i++) {
    const t = i / STATIONS;
    for (let j = 0; j < per; j++) {
      const k = j - RING; // -RING .. RING
      const s = Math.pow(Math.abs(k) / RING, 0.85);
      hullPoint(t, s, Math.sign(k), v);
      pos.push(v.x, v.y, v.z);
    }
  }
  for (let i = 0; i < STATIONS; i++) {
    for (let j = 0; j < per - 1; j++) {
      const a = i * per + j;
      const b = a + per;
      idx.push(a, a + 1, b, b, a + 1, b + 1);
    }
  }
  const shell = new BufferGeometry();
  shell.setAttribute("position", new BufferAttribute(new Float32Array(pos), 3));
  shell.setIndex(idx);
  shell.computeVertexNormals();

  // Transom: a flat fan with its own vertices, so the edge stays crisp.
  const tp: number[] = [];
  const ti: number[] = [];
  hullPoint(0, 0.55, 0, v);
  tp.push(v.x, v.y, 0);
  for (let j = 0; j < per; j++) {
    const k = j - RING;
    hullPoint(0, Math.pow(Math.abs(k) / RING, 0.85), Math.sign(k), v);
    tp.push(v.x, v.y, v.z);
  }
  for (let j = 1; j < per; j++) ti.push(0, j, j + 1);
  const transom = new BufferGeometry();
  transom.setAttribute("position", new BufferAttribute(new Float32Array(tp), 3));
  transom.setIndex(ti);
  transom.computeVertexNormals();

  const g = mergeGeometries([shell.toNonIndexed(), transom.toNonIndexed()])!;
  // Smooth normals on the shell were computed before merging; keep them.
  return g;
}

/** The deck plating inside the bulwark, following the sheer (flat cargo deck, raised forecastle). */
export function makeDeckGeometry(): BufferGeometry {
  const pos: number[] = [];
  const idx: number[] = [];
  const v = new Vector3();
  for (let i = 0; i <= STATIONS; i++) {
    const t = i / STATIONS;
    const y = sheerAt(t);
    // Width of the hull at deck height (just under the bulwark top).
    hullPoint(t, 0.93, 1, v);
    const z = Math.max(0.02, v.z - 0.04);
    const x = -HULL_L / 2 + t * HULL_L;
    pos.push(x, y, -z, x, y, z);
  }
  for (let i = 0; i < STATIONS; i++) {
    const a = i * 2;
    idx.push(a, a + 1, a + 2, a + 2, a + 1, a + 3);
  }
  const g = new BufferGeometry();
  g.setAttribute("position", new BufferAttribute(new Float32Array(pos), 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

/** Painted steel hull: topsides in the material colour, a white boot stripe, antifouling red below the waterline. */
export function makeHullMaterial(topside: string): MeshStandardMaterial {
  const m = new MeshStandardMaterial({ color: topside, roughness: 0.52, metalness: 0.05, side: DoubleSide });
  m.onBeforeCompile = (shader) => {
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\nvarying float vLocalY;")
      .replace("#include <begin_vertex>", "#include <begin_vertex>\nvLocalY = position.y;");
    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", "#include <common>\nvarying float vLocalY;")
      .replace(
        "vec4 diffuseColor = vec4( diffuse, opacity );",
        `float bootLo = smoothstep(${PAINT_LINE.toFixed(2)} - 0.015, ${PAINT_LINE.toFixed(2)} + 0.015, vLocalY);
         float bootHi = smoothstep(${(PAINT_LINE + 0.2).toFixed(2)} - 0.015, ${(PAINT_LINE + 0.2).toFixed(2)} + 0.015, vLocalY);
         vec3 hullC = mix(vec3(0.42, 0.07, 0.05), vec3(0.86, 0.86, 0.83), bootLo);
         hullC = mix(hullC, diffuse, bootHi);
         // A rubbing strake just under the bulwark top.
         hullC = mix(hullC, diffuse * 0.45, smoothstep(-0.06, -0.04, vLocalY) * (1.0 - smoothstep(0.04, 0.06, vLocalY)) * 0.8);
         vec4 diffuseColor = vec4( hullC, opacity );`,
      );
  };
  return m;
}

// ---------- textures (canvas, generated once) ----------
function canvas(w: number, h: number): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  return [c, c.getContext("2d")!];
}

let windowTex: { map: CanvasTexture; glow: CanvasTexture } | null = null;
/** Superstructure plating with two rows of windows; `glow` is the same layout as an emissive mask (lit at night). */
export function windowTextures() {
  if (windowTex) return windowTex;
  const [c, g] = canvas(256, 128);
  const [e, eg] = canvas(256, 128);
  g.fillStyle = "#e8e6e0";
  g.fillRect(0, 0, 256, 128);
  // plating seams and a little weathering under each seam
  g.strokeStyle = "rgba(60,70,80,0.18)";
  g.lineWidth = 1;
  for (const y of [42, 86]) {
    g.beginPath();
    g.moveTo(0, y);
    g.lineTo(256, y);
    g.stroke();
  }
  eg.fillStyle = "#000";
  eg.fillRect(0, 0, 256, 128);
  for (const y of [20, 64]) {
    for (let k = 0; k < 8; k++) {
      const x = 12 + k * 30.5;
      g.fillStyle = "#16222e";
      g.fillRect(x, y, 18, 13);
      g.fillStyle = "rgba(140,170,195,0.35)";
      g.fillRect(x + 1, y + 1, 16, 4);
      // a few rooms stay dark
      eg.fillStyle = (k * 7 + y) % 5 === 0 ? "#2a2010" : "#ffd28a";
      eg.fillRect(x, y, 18, 13);
    }
  }
  g.fillStyle = "rgba(90,60,40,0.10)";
  g.fillRect(0, 104, 256, 24);
  const map = new CanvasTexture(c);
  map.colorSpace = SRGBColorSpace;
  const glow = new CanvasTexture(e);
  glow.colorSpace = SRGBColorSpace;
  windowTex = { map, glow };
  return windowTex;
}

let bridgeTex: { map: CanvasTexture; glow: CanvasTexture } | null = null;
/** Wheelhouse: one continuous band of raked windows. */
export function bridgeTextures() {
  if (bridgeTex) return bridgeTex;
  const [c, g] = canvas(256, 64);
  const [e, eg] = canvas(256, 64);
  g.fillStyle = "#ecebe6";
  g.fillRect(0, 0, 256, 64);
  eg.fillStyle = "#000";
  eg.fillRect(0, 0, 256, 64);
  for (let k = 0; k < 10; k++) {
    const x = 6 + k * 25;
    g.fillStyle = "#101c27";
    g.fillRect(x, 12, 21, 28);
    g.fillStyle = "rgba(150,185,210,0.4)";
    g.fillRect(x + 1, 13, 19, 8);
    eg.fillStyle = "#9fb4a0";
    eg.fillRect(x, 12, 21, 28);
  }
  const map = new CanvasTexture(c);
  map.colorSpace = SRGBColorSpace;
  const glow = new CanvasTexture(e);
  glow.colorSpace = SRGBColorSpace;
  bridgeTex = { map, glow };
  return bridgeTex;
}

let containerTex: { map: CanvasTexture; bump: CanvasTexture } | null = null;
/** Corrugated container side: ribs, corner posts, top and bottom rails. Greyscale, so the instance colour tints it. */
export function containerTextures() {
  if (containerTex) return containerTex;
  const W = 256;
  const H = 128;
  const [c, g] = canvas(W, H);
  const [b, bg] = canvas(W, H);
  const img = g.createImageData(W, H);
  const bmp = bg.createImageData(W, H);
  const RIBS = 22;
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const u = x / W;
      const v = y / H;
      const rib = 0.5 + 0.5 * Math.cos(u * RIBS * Math.PI * 2);
      const frame = u < 0.035 || u > 0.965 || v < 0.07 || v > 0.93;
      let shade = frame ? 0.72 : 0.78 + 0.22 * rib;
      let height = frame ? 1 : rib * 0.75;
      // streaks of dirt and rust running down from the top rail
      const streak = Math.max(0, Math.sin(u * 61.0) * Math.sin(u * 17.3 + 1.2)) * (1 - v) * 0.14;
      shade -= streak;
      if (!frame && v > 0.86) shade -= 0.06;
      const i = (y * W + x) * 4;
      const s = Math.round(255 * Math.min(1, Math.max(0, shade)));
      img.data[i] = img.data[i + 1] = img.data[i + 2] = s;
      img.data[i + 3] = 255;
      const hgt = Math.round(255 * height);
      bmp.data[i] = bmp.data[i + 1] = bmp.data[i + 2] = hgt;
      bmp.data[i + 3] = 255;
    }
  }
  g.putImageData(img, 0, 0);
  bg.putImageData(bmp, 0, 0);
  const map = new CanvasTexture(c);
  map.colorSpace = SRGBColorSpace;
  map.wrapS = map.wrapT = RepeatWrapping;
  map.anisotropy = 4;
  const bump = new CanvasTexture(b);
  bump.wrapS = bump.wrapT = RepeatWrapping;
  containerTex = { map, bump };
  return containerTex;
}

/** Container proportions from the crate's size (bundle: cube root of notional per crate): long, low, narrow. */
export function containerDims(size: number): { len: number; h: number; w: number } {
  return { len: size * 1.9, h: size * 0.8, w: size * 0.82 };
}

let containerGeo: BoxGeometry | null = null;
/** Unit container (1 x 1 x 1, scaled per instance); the short ends use a third of the texture so ribs keep their pitch. */
export function containerGeometry(): BoxGeometry {
  if (containerGeo) return containerGeo;
  const g = new BoxGeometry(1, 1, 1);
  const uv = g.attributes.uv;
  // BoxGeometry face order: +x, -x, +y, -y, +z, -z; four vertices each. Ends are the +x / -x faces.
  for (let i = 0; i < 8; i++) uv.setX(i, uv.getX(i) * 0.42);
  // The roof and floor: ribs run across.
  for (let i = 8; i < 16; i++) uv.setXY(i, uv.getX(i), 0.3 + uv.getY(i) * 0.4);
  containerGeo = g;
  return g;
}

let containerMat: MeshStandardMaterial | null = null;
export function containerMaterial(): MeshStandardMaterial {
  if (containerMat) return containerMat;
  const t = containerTextures();
  containerMat = new MeshStandardMaterial({ map: t.map, bumpMap: t.bump, bumpScale: 1.6, roughness: 0.62, metalness: 0.1 });
  return containerMat;
}

/** Container liveries: one family per position in the book, varied crate by crate. */
const LIVERIES = ["#b5532a", "#2f6fae", "#3f8f62", "#b33a3a", "#7d63b0", "#c2a23a"];
export function containerColor(positionIndex: number, k: number, out = new Color()): Color {
  out.set(LIVERIES[positionIndex % LIVERIES.length]);
  const r1 = ((k * 37 + 11) % 17) / 17;
  const r2 = ((k * 53 + 5) % 13) / 13;
  // A few boxes in a faded or neighbouring livery, as on any real deck.
  out.offsetHSL((r2 - 0.5) * 0.045, (r1 - 0.5) * 0.18, (r1 - 0.5) * 0.16 + (k % 5 === 3 ? 0.07 : 0));
  return out;
}

const UP = new Vector3(0, 1, 0);
/** A thin rod between two points (mast stays, yards, rails). */
function rod(a: [number, number, number], b: [number, number, number], r: number, seg = 5): BufferGeometry {
  const va = new Vector3(...a);
  const vb = new Vector3(...b);
  const len = va.distanceTo(vb);
  const g = new CylinderGeometry(r, r, len, seg, 1, true);
  g.translate(0, len / 2, 0);
  g.applyQuaternion(new Quaternion().setFromUnitVectors(UP, vb.clone().sub(va).normalize()));
  g.translate(va.x, va.y, va.z);
  return g;
}

/** Mast, yard, radar mast, jackstaff and the standing rigging, as one geometry. */
export function makeRigGeometry(): BufferGeometry {
  const bowTop: [number, number, number] = [HULL_L / 2 - 0.5, sheerAt(1) + BULWARK, 0];
  const mastHead: [number, number, number] = [MAST_X, MAST_TOP - 0.15, 0];
  const parts: BufferGeometry[] = [];
  const mast = new CylinderGeometry(0.1, 0.17, MAST_TOP, 10);
  mast.translate(MAST_X, MAST_TOP / 2, 0);
  parts.push(mast);
  // yard and a lower boom for the sail
  parts.push(rod([MAST_X + 0.12, YARD_Y, -SAIL_W / 2 - 0.2], [MAST_X + 0.12, YARD_Y, SAIL_W / 2 + 0.2], 0.075, 6));
  parts.push(rod([MAST_X + 0.12, YARD_Y - SAIL_H, -SAIL_W / 2 - 0.1], [MAST_X + 0.12, YARD_Y - SAIL_H, SAIL_W / 2 + 0.1], 0.06, 6));
  // crow's nest ring
  const nest = new CylinderGeometry(0.34, 0.26, 0.38, 10, 1, true);
  nest.translate(MAST_X, YARD_Y + 0.75, 0);
  parts.push(nest);
  // standing rigging: forestay, backstay, shrouds, yard lifts
  parts.push(rod(mastHead, bowTop, 0.022));
  parts.push(rod(mastHead, [-HULL_L / 2 + 0.5, 0.42, 0], 0.022));
  for (const s of [-1, 1]) {
    parts.push(rod(mastHead, [MAST_X - 0.9, BULWARK, s * (HULL_B / 2 - 0.12)], 0.022));
    parts.push(rod(mastHead, [MAST_X + 1.0, BULWARK, s * (HULL_B / 2 - 0.12)], 0.022));
    parts.push(rod(mastHead, [MAST_X + 0.12, YARD_Y, s * (SAIL_W / 2 + 0.15)], 0.016));
  }
  // jackstaff at the bow
  parts.push(rod([HULL_L / 2 - 0.75, sheerAt(1), 0], [HULL_L / 2 - 0.75, sheerAt(1) + 1.9, 0], 0.035));
  const withAttrs = parts.map((p) => (p.index ? p.toNonIndexed() : p));
  return mergeGeometries(withAttrs)!;
}

/** Railings around the forecastle and the bridge deck, bollards, the hatch coaming: small dark steel details. */
export function makeDetailGeometry(): BufferGeometry {
  const parts: BufferGeometry[] = [];
  const box = (w: number, h: number, d: number, x: number, y: number, z: number) => {
    const g = new BoxGeometry(w, h, d);
    g.translate(x, y, z);
    parts.push(g);
  };
  // hatch coaming under the containers
  box(DECK.x1 - DECK.x0 + 0.3, 0.16, DECK.z1 - DECK.z0 + 0.1, (DECK.x0 + DECK.x1) / 2, 0.08, 0);
  // windlass and bollards on the forecastle
  const fy = sheerAt(0.95);
  box(0.7, 0.4, 1.3, HULL_L / 2 - 1.9, fy + 0.2, 0);
  for (const s of [-1, 1]) {
    box(0.22, 0.34, 0.22, HULL_L / 2 - 2.6, fy + 0.17, s * 0.75);
    box(0.22, 0.3, 0.22, -HULL_L / 2 + 0.7, 0.15, s * 1.3);
  }
  // rail on the forecastle break
  const fx = -HULL_L / 2 + 0.81 * HULL_L;
  parts.push(rod([fx, 1.05, -1.5], [fx, 1.05 + 0.75, -1.5], 0.03), rod([fx, 1.05, 1.5], [fx, 1.05 + 0.75, 1.5], 0.03), rod([fx, 1.8, -1.5], [fx, 1.8, 1.5], 0.03), rod([fx, 1.45, -1.5], [fx, 1.45, 1.5], 0.022));
  return mergeGeometries(parts.map((p) => (p.index ? p.toNonIndexed() : p)))!;
}

/** Square sail grid (vertices are moved every frame by the wind). Local frame: hangs from the yard, across the beam. */
export const SAIL_SEG = 12;
export function makeSailGeometry(): BufferGeometry {
  const n = SAIL_SEG + 1;
  const pos = new Float32Array(n * n * 3);
  const uv = new Float32Array(n * n * 2);
  const idx: number[] = [];
  for (let j = 0; j < n; j++) {
    for (let i = 0; i < n; i++) {
      const k = j * n + i;
      uv[k * 2] = i / SAIL_SEG;
      uv[k * 2 + 1] = j / SAIL_SEG;
    }
  }
  for (let j = 0; j < SAIL_SEG; j++) {
    for (let i = 0; i < SAIL_SEG; i++) {
      const a = j * n + i;
      idx.push(a, a + 1, a + n, a + n, a + 1, a + n + 1);
    }
  }
  const g = new BufferGeometry();
  g.setAttribute("position", new BufferAttribute(pos, 3));
  g.setAttribute("uv", new BufferAttribute(uv, 2));
  g.setIndex(idx);
  return g;
}

/**
 * Shape the sail. `fill` 0..1 is how full it draws (bundle: equity rising, or a fair wind); `wind` 0..1 the wind
 * (bundle: state); `time` seconds. A full sail bellies forward; a slack one hangs and shivers along its foot.
 */
export function shapeSail(g: BufferGeometry, fill: number, wind: number, time: number) {
  const p = g.attributes.position as BufferAttribute;
  const n = SAIL_SEG + 1;
  const a = p.array as Float32Array;
  // A slack sail is furled: a neat roll under the yard. It unrolls as it fills.
  const open = Math.pow(Math.min(1, Math.max(0, fill)), 0.8);
  const drop = SAIL_H * (0.09 + 0.91 * open);
  for (let j = 0; j < n; j++) {
    const v = j / SAIL_SEG; // 0 at the yard, 1 at the foot
    for (let i = 0; i < n; i++) {
      const u = i / SAIL_SEG - 0.5; // -0.5 .. 0.5 across
      const k = (j * n + i) * 3;
      const edge = 1 - 4 * u * u; // 1 at the middle, 0 at the leeches
      const belly = Math.sin(Math.PI * Math.min(1, v * 1.08)) * (0.35 + 0.65 * edge);
      // The foot is narrower when the sail is clewed up.
      const width = SAIL_W * (1 - (1 - fill) * 0.22 * v);
      const flutterAmp = (0.05 + 0.2 * wind) * (1 - 0.75 * fill) * v * (0.15 + 0.85 * open);
      const flutter = Math.sin(time * (5 + 7 * wind) + v * 7 + u * 9) * flutterAmp + Math.sin(time * 3.1 + u * 14) * flutterAmp * 0.5;
      const gust = 1 + 0.07 * Math.sin(time * 1.3 + u * 2) * wind;
      a[k] = belly * (0.2 + 1.55 * fill) * gust + flutter; // forward (+x)
      a[k + 1] = -v * drop + (1 - edge) * 0.0 - belly * 0.12 * fill;
      a[k + 2] = u * width;
    }
  }
  p.needsUpdate = true;
  g.computeVertexNormals();
}
