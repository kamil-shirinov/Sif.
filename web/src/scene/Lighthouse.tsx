import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import {
  AdditiveBlending,
  BufferAttribute,
  BufferGeometry,
  CanvasTexture,
  Color,
  ConeGeometry,
  CylinderGeometry,
  DoubleSide,
  Group,
  IcosahedronGeometry,
  Mesh,
  MeshBasicMaterial,
  PointLight,
  ShaderMaterial,
  SRGBColorSpace,
  TorusGeometry,
} from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { vis } from "./vis";
import { show } from "./debugFlags";

export const LIGHTHOUSE_POS: [number, number, number] = [-42, 0, -72];
const TOWER_H = 17;
const LAMP_Y = TOWER_H + 1.75;
const BASE_Y = 2.4; // foot of the plinth, bedded into the levelled top of the rock

/** Cheap 3D value noise for shaping rock (JS, build time only). */
function hash3(x: number, y: number, z: number): number {
  const s = Math.sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453;
  return s - Math.floor(s);
}
function noise3(x: number, y: number, z: number): number {
  const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
  const xf = x - xi, yf = y - yi, zf = z - zi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf), w = zf * zf * (3 - 2 * zf);
  const l = (a: number, b: number, t: number) => a + (b - a) * t;
  return l(
    l(l(hash3(xi, yi, zi), hash3(xi + 1, yi, zi), u), l(hash3(xi, yi + 1, zi), hash3(xi + 1, yi + 1, zi), u), v),
    l(l(hash3(xi, yi, zi + 1), hash3(xi + 1, yi, zi + 1), u), l(hash3(xi, yi + 1, zi + 1), hash3(xi + 1, yi + 1, zi + 1), u), v),
    w,
  );
}
/** Ridged fractal noise: sharp ledges and cracks, like weathered rock. */
function ridged(x: number, y: number, z: number): number {
  let s = 0;
  let a = 0.5;
  let f = 1;
  for (let k = 0; k < 5; k++) {
    s += a * (1 - Math.abs(2 * noise3(x * f, y * f, z * f) - 1));
    f *= 2.1;
    a *= 0.5;
  }
  return s;
}

/**
 * A skerry: a displaced sphere, wide and low, with ledges. `plateau` flattens the top (for the lighthouse plinth).
 * Vertex colours: dark and wet near the waterline, weathered grey above, a little lichen on the upper faces.
 */
function makeRock(seed: number, rx: number, ry: number, rz: number, plateau?: number): BufferGeometry {
  const g = new IcosahedronGeometry(1, 24);
  const p = g.attributes.position;
  const col = new Float32Array(p.count * 3);
  const c = new Color();
  const wet = new Color("#23262a");
  const dry = new Color("#6f6a62");
  const lichen = new Color("#7d7a52");
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
    const n = ridged(x * 1.7 + seed, y * 1.7 + seed * 0.3, z * 1.7 - seed);
    const big = noise3(x * 0.9 + seed * 2, y * 0.9, z * 0.9 + seed);
    const k = 0.72 + 0.34 * n + 0.22 * big;
    let wy = y * k * ry;
    // Terraces: the rock steps down in ledges.
    wy = wy * 0.75 + Math.round(wy / 0.9) * 0.9 * 0.25;
    if (plateau !== undefined && wy > plateau) wy = plateau + (wy - plateau) * 0.08;
    const wx = x * k * rx;
    const wz = z * k * rz;
    p.setXYZ(i, wx, Math.max(-ry * 0.5, wy), wz);
    const t = Math.min(1, Math.max(0, (wy - 0.2) / 1.6));
    c.copy(wet).lerp(dry, t * (0.75 + 0.5 * n));
    if (wy > 1.8) c.lerp(lichen, Math.max(0, big - 0.45) * 0.9);
    c.multiplyScalar(0.8 + 0.4 * n);
    col[i * 3] = c.r;
    col[i * 3 + 1] = c.g;
    col[i * 3 + 2] = c.b;
  }
  g.setAttribute("color", new BufferAttribute(col, 3));
  g.computeVertexNormals();
  return g;
}

/** Tower paint: white with three red bands, a few small windows, weathering streaks. Generated in code. */
function makeTowerTexture(): CanvasTexture {
  const c = document.createElement("canvas");
  c.width = 256;
  c.height = 512;
  const g = c.getContext("2d")!;
  g.fillStyle = "#ece8de";
  g.fillRect(0, 0, 256, 512);
  g.fillStyle = "#b02a2c";
  for (const v of [0.14, 0.42, 0.7]) g.fillRect(0, 512 * (1 - v - 0.13), 256, 512 * 0.13);
  // streaks running down from each band and the gallery
  for (let k = 0; k < 60; k++) {
    const x = (k * 97) % 256;
    const y = (k * 53) % 400;
    g.fillStyle = `rgba(70,60,50,${0.03 + ((k * 13) % 7) / 140})`;
    g.fillRect(x, y, 2 + (k % 3), 50 + ((k * 31) % 90));
  }
  // windows on the side facing the ships (u = 0.25 is +z on a three.js cylinder)
  g.fillStyle = "#18222c";
  for (const v of [0.3, 0.58]) g.fillRect(256 * 0.25 - 5, 512 * (1 - v) - 9, 10, 18);
  // door at the foot
  g.fillStyle = "#3a2a22";
  g.fillRect(256 * 0.25 - 9, 512 - 44, 18, 44);
  const t = new CanvasTexture(c);
  t.colorSpace = SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}

/** Gallery railing and lantern-room glazing bars: thin dark steel, one geometry. */
function makeIronwork(galleryY: number, lampY: number): BufferGeometry {
  const parts: BufferGeometry[] = [];
  const N = 14;
  for (let k = 0; k < N; k++) {
    const a = (k / N) * Math.PI * 2;
    const post = new CylinderGeometry(0.035, 0.035, 0.95, 5);
    post.translate(Math.cos(a) * 2.45, galleryY + 0.6, Math.sin(a) * 2.45);
    parts.push(post);
  }
  for (const h of [0.55, 1.05]) {
    const rail = new TorusGeometry(2.45, 0.03, 5, 40);
    rail.rotateX(Math.PI / 2);
    rail.translate(0, galleryY + h, 0);
    parts.push(rail);
  }
  for (let k = 0; k < 10; k++) {
    const a = (k / 10) * Math.PI * 2;
    const bar = new CylinderGeometry(0.04, 0.04, 2.4, 5);
    bar.translate(Math.cos(a) * 1.27, lampY, Math.sin(a) * 1.27);
    parts.push(bar);
  }
  for (const h of [-1.2, 1.2]) {
    const ring = new TorusGeometry(1.27, 0.06, 6, 32);
    ring.rotateX(Math.PI / 2);
    ring.translate(0, lampY + h, 0);
    parts.push(ring);
  }
  return mergeGeometries(parts.map((q) => (q.index ? q.toNonIndexed() : q)))!;
}

function makeBeam(): Mesh {
  const len = 160;
  const geo = new ConeGeometry(16, len, 32, 1, true);
  geo.translate(0, -len / 2, 0); // apex at origin
  geo.rotateZ(Math.PI / 2); // point along +x
  const mat = new ShaderMaterial({
    uniforms: { uOpacity: { value: 0 }, uTint: { value: new Color(1.6, 1.45, 1.0) } },
    vertexShader: /* glsl */ `
      varying float vAlong;
      void main() { vAlong = clamp(position.x / ${len.toFixed(1)}, 0.0, 1.0); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: /* glsl */ `
      uniform float uOpacity; uniform vec3 uTint; varying float vAlong;
      void main() {
        // No pow(): with MSAA a varying is extrapolated past the triangle at its edges, 1.0 - vAlong goes negative
        // there, pow() of a negative base is NaN on Apple GPUs, and one NaN sample ruins the whole MSAA resolve.
        float t = clamp(1.0 - vAlong, 0.0, 1.0);
        float a = clamp(uOpacity, 0.0, 1.0) * t * sqrt(t);
        gl_FragColor = vec4(uTint * a, a);
      }`,
    transparent: true,
    depthWrite: false,
    blending: AdditiveBlending,
    side: DoubleSide,
    fog: false,
    toneMapped: false,
  });
  return new Mesh(geo, mat);
}

const LAMP_ON = new Color(16, 13, 7);
const LAMP_OFF = new Color("#3a3a33");
const LAMP_AMBER = new Color(18, 8, 0.6);
const BEAM_WHITE = new Color(1.6, 1.45, 1.0);
const BEAM_AMBER = new Color(1.9, 0.95, 0.2);
const LIGHT_WHITE = new Color("#ffd9a0");
const LIGHT_AMBER = new Color("#ff9a1f");

/**
 * Lighthouse on a stepped stone plinth on a skerry. The lamp lights and the beam sweeps white while an alarm event is active.
 * A squall event flashes the lamp and beam amber for a few market minutes: a warning, no cut.
 */
export function Lighthouse() {
  const rock = useMemo(() => makeRock(42, 13, 6.2, 10.5, 3.3), []);
  const rock2 = useMemo(() => makeRock(7, 5.5, 3.2, 4.5), []);
  const rock3 = useMemo(() => makeRock(19, 3.4, 2.2, 3.0), []);
  const towerTex = useMemo(makeTowerTexture, []);
  const iron = useMemo(() => makeIronwork(TOWER_H + 0.3, LAMP_Y), []);
  const beams = useMemo(() => [makeBeam(), makeBeam()], []);
  const lampMat = useMemo(() => new MeshBasicMaterial({ toneMapped: false }), []);
  // The lantern glass is unlit on purpose. A glossy lit surface a metre from the 900 cd lamp gave specular
  // highlights in the millions, which overflowed the half-float MSAA buffer and blacked out the frame on Apple GPUs.
  const glassMat = useMemo(() => new MeshBasicMaterial({ color: new Color(0.22, 0.3, 0.34), transparent: true, opacity: 0.38, depthWrite: false, side: DoubleSide }), []);
  // Amber halo around the lamp: the squall flash, visible from far away.
  const haloMat = useMemo(
    () => new MeshBasicMaterial({ color: new Color(3.2, 1.5, 0.2), transparent: true, opacity: 0, blending: AdditiveBlending, depthWrite: false, toneMapped: false, fog: false }),
    [],
  );
  const spin = useRef<Group>(null);
  const light = useRef<PointLight>(null);

  useFrame((_, dt) => {
    const a = vis.alarm;
    // Squall: strobing amber, between dim and full.
    const amber = vis.squall > 0 ? vis.squall * (0.45 + 0.55 * Math.max(0, Math.sin(vis.elapsed * 15))) : 0;
    lampMat.color.copy(LAMP_OFF).lerp(LAMP_ON, a).lerp(LAMP_AMBER, amber);
    haloMat.opacity = amber * 0.55;
    // Unlit, so it is dimmed by hand: by daylight and the storm when dark, lit from inside when the lamp is on.
    const amb = 0.06 + 0.94 * vis.dayFactor * (1 - 0.6 * vis.risk);
    glassMat.color.setRGB(0.22 * amb + a * 2.0 + amber * 2.4, 0.3 * amb + a * 1.6 + amber * 1.1, 0.34 * amb + a * 0.9 + amber * 0.15);
    if (spin.current) spin.current.rotation.y += dt * 1.15 * Math.min(1, Math.max(a, vis.squall) * 1.5);
    const op = Math.max(a * (0.3 + 0.25 * vis.risk + 0.15 * (1 - vis.dayFactor)), amber * 0.9);
    const amberShare = amber / (amber + a + 1e-4);
    beams.forEach((b) => {
      const u = (b.material as ShaderMaterial).uniforms;
      u.uOpacity.value = op;
      u.uTint.value.copy(BEAM_WHITE).lerp(BEAM_AMBER, amberShare);
    });
    if (light.current) {
      light.current.intensity = Math.max(a * 520, amber * 430);
      light.current.color.copy(LIGHT_WHITE).lerp(LIGHT_AMBER, amberShare);
    }
  });

  return (
    <group position={LIGHTHOUSE_POS}>
      {/* the skerry: one large rock with a levelled top, two outliers */}
      <mesh geometry={rock} position={[0, 0.4, 0]}>
        <meshStandardMaterial vertexColors roughness={0.94} metalness={0} />
      </mesh>
      <mesh geometry={rock2} position={[13, -0.3, 6]} rotation={[0, 1.1, 0]}>
        <meshStandardMaterial vertexColors roughness={0.94} metalness={0} />
      </mesh>
      <mesh geometry={rock3} position={[-12, -0.4, 7.5]} rotation={[0, 2.4, 0]}>
        <meshStandardMaterial vertexColors roughness={0.94} metalness={0} />
      </mesh>
      <group position={[0, BASE_Y, 0]}>
        {/* stepped stone plinth bedded into the rock */}
        <mesh position={[0, 0.2, 0]}>
          <cylinderGeometry args={[4.1, 4.5, 2.4, 28]} />
          <meshStandardMaterial color="#8d8a82" roughness={0.9} />
        </mesh>
        <mesh position={[0, 1.65, 0]}>
          <cylinderGeometry args={[3.2, 3.5, 0.6, 28]} />
          <meshStandardMaterial color="#a19d94" roughness={0.88} />
        </mesh>
        <group position={[0, 1.95, 0]}>
          {/* tower: white with red bands (painted in the texture) */}
          <mesh position={[0, TOWER_H / 2, 0]}>
            <cylinderGeometry args={[1.5, 2.5, TOWER_H, 32]} />
            <meshStandardMaterial map={towerTex} roughness={0.72} metalness={0} />
          </mesh>
          {/* gallery deck with its corbel, railing, and the lantern room's glazing bars */}
          <mesh position={[0, TOWER_H - 0.25, 0]}>
            <cylinderGeometry args={[2.3, 1.55, 0.7, 24]} />
            <meshStandardMaterial color="#d8d4ca" roughness={0.75} />
          </mesh>
          <mesh position={[0, TOWER_H + 0.2, 0]}>
            <cylinderGeometry args={[2.6, 2.6, 0.22, 24]} />
            <meshStandardMaterial color="#2a2c2e" roughness={0.7} metalness={0.2} />
          </mesh>
          <mesh geometry={iron}>
            <meshStandardMaterial color="#1c1e20" roughness={0.65} metalness={0.3} />
          </mesh>
          {/* lantern room */}
          {show("lhglass") && (
            <mesh position={[0, LAMP_Y, 0]} material={glassMat} renderOrder={2}>
              <cylinderGeometry args={[1.25, 1.25, 2.4, 20, 1, true]} />
            </mesh>
          )}
          {show("lhlamp") && (
            <mesh position={[0, LAMP_Y, 0]} material={lampMat}>
              <sphereGeometry args={[0.62, 16, 12]} />
            </mesh>
          )}
          {show("lhhalo") && (
            <mesh position={[0, LAMP_Y, 0]} material={haloMat} renderOrder={3}>
              <sphereGeometry args={[2.6, 20, 14]} />
            </mesh>
          )}
          <mesh position={[0, LAMP_Y + 1.95, 0]}>
            <coneGeometry args={[1.6, 1.5, 20]} />
            <meshStandardMaterial color="#7a2420" metalness={0.15} roughness={0.7} />
          </mesh>
          <mesh position={[0, LAMP_Y + 2.85, 0]}>
            <sphereGeometry args={[0.22, 10, 8]} />
            <meshStandardMaterial color="#1e1e1e" metalness={0.3} roughness={0.7} />
          </mesh>
          <group ref={spin} position={[0, LAMP_Y, 0]} visible={show("lhbeam")}>
            <primitive object={beams[0]} />
            <primitive object={beams[1]} rotation={[0, Math.PI, 0]} />
          </group>
          {/* Lights the gallery, the tower and the rock. Every lit surface near it is rough: see glassMat above. */}
          {show("lhlight") && <pointLight ref={light} position={[0, LAMP_Y + 0.2, 0]} intensity={0} distance={140} decay={1.4} color="#ffd9a0" />}
        </group>
      </group>
    </group>
  );
}
