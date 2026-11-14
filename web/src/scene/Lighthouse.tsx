import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import {
  AdditiveBlending,
  Color,
  ConeGeometry,
  DodecahedronGeometry,
  DoubleSide,
  Group,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  PointLight,
  ShaderMaterial,
} from "three";
import { vis } from "./vis";

export const LIGHTHOUSE_POS: [number, number, number] = [-42, 0, -72];
const TOWER_H = 17;
const LAMP_Y = TOWER_H + 1.6;

function makeRock(seed: number, radius: number): DodecahedronGeometry {
  const g = new DodecahedronGeometry(radius, 2);
  const p = g.attributes.position;
  let s = seed;
  const r = () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
  const cache = new Map<string, number>();
  for (let i = 0; i < p.count; i++) {
    const key = `${p.getX(i).toFixed(3)},${p.getY(i).toFixed(3)},${p.getZ(i).toFixed(3)}`;
    let k = cache.get(key);
    if (k === undefined) {
      k = 0.78 + r() * 0.42;
      cache.set(key, k);
    }
    p.setXYZ(i, p.getX(i) * k * 1.25, Math.max(-radius * 0.6, p.getY(i) * k * 0.62), p.getZ(i) * k);
  }
  g.computeVertexNormals();
  return g;
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
        float a = uOpacity * pow(1.0 - vAlong, 1.6);
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
 * Lighthouse on a rock. The lamp lights and the beam sweeps white while an alarm event is active.
 * A squall event flashes the lamp and beam amber for a few market minutes: a warning, no cut.
 */
export function Lighthouse() {
  const rock = useMemo(() => makeRock(42, 9), []);
  const rock2 = useMemo(() => makeRock(7, 5), []);
  const beams = useMemo(() => [makeBeam(), makeBeam()], []);
  const lampMat = useMemo(() => new MeshBasicMaterial({ toneMapped: false }), []);
  const glassMat = useMemo(
    () => new MeshStandardMaterial({ color: "#9fb7c2", transparent: true, opacity: 0.35, emissive: new Color(0, 0, 0), roughness: 0.1 }),
    [],
  );
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
    glassMat.emissive.setRGB(a * 2.2 + amber * 2.4, a * 1.8 + amber * 1.1, a * 1.0 + amber * 0.15);
    if (spin.current) spin.current.rotation.y += dt * 1.15 * Math.min(1, Math.max(a, vis.squall) * 1.5);
    const op = Math.max(a * (0.3 + 0.25 * vis.risk + 0.15 * (1 - vis.dayFactor)), amber * 0.9);
    const amberShare = amber / (amber + a + 1e-4);
    beams.forEach((b) => {
      const u = (b.material as ShaderMaterial).uniforms;
      u.uOpacity.value = op;
      u.uTint.value.copy(BEAM_WHITE).lerp(BEAM_AMBER, amberShare);
    });
    if (light.current) {
      light.current.intensity = Math.max(a * 900, amber * 750);
      light.current.color.copy(LIGHT_WHITE).lerp(LIGHT_AMBER, amberShare);
    }
  });

  return (
    <group position={LIGHTHOUSE_POS}>
      <mesh geometry={rock} position={[0, 0.6, 0]}>
        <meshStandardMaterial color="#3b3936" roughness={0.95} flatShading />
      </mesh>
      <mesh geometry={rock2} position={[8, 0, 5]}>
        <meshStandardMaterial color="#34322f" roughness={0.95} flatShading />
      </mesh>
      <group position={[0, 3.2, 0]}>
        {/* tower, banded */}
        <mesh position={[0, TOWER_H / 2, 0]}>
          <cylinderGeometry args={[1.5, 2.4, TOWER_H, 24]} />
          <meshStandardMaterial color="#eeeae0" roughness={0.7} />
        </mesh>
        {[0.22, 0.52, 0.8].map((h) => (
          <mesh key={h} position={[0, TOWER_H * h, 0]}>
            <cylinderGeometry args={[2.45 - 0.9 * (h + 1 / TOWER_H), 2.45 - 0.9 * (h - 1 / TOWER_H), 2, 24]} />
            <meshStandardMaterial color="#b3262a" roughness={0.6} />
          </mesh>
        ))}
        {/* gallery */}
        <mesh position={[0, TOWER_H + 0.15, 0]}>
          <cylinderGeometry args={[2.3, 2.3, 0.3, 24]} />
          <meshStandardMaterial color="#222" />
        </mesh>
        {/* lantern room */}
        <mesh position={[0, LAMP_Y, 0]} material={glassMat}>
          <cylinderGeometry args={[1.25, 1.25, 2.4, 16, 1, true]} />
        </mesh>
        <mesh position={[0, LAMP_Y, 0]} material={lampMat}>
          <sphereGeometry args={[0.62, 16, 12]} />
        </mesh>
        <mesh position={[0, LAMP_Y, 0]} material={haloMat} renderOrder={3}>
          <sphereGeometry args={[2.6, 20, 14]} />
        </mesh>
        <mesh position={[0, LAMP_Y + 1.9, 0]}>
          <coneGeometry args={[1.55, 1.5, 16]} />
          <meshStandardMaterial color="#1e1e1e" metalness={0.4} roughness={0.5} />
        </mesh>
        <group ref={spin} position={[0, LAMP_Y, 0]}>
          <primitive object={beams[0]} />
          <primitive object={beams[1]} rotation={[0, Math.PI, 0]} />
        </group>
        <pointLight ref={light} position={[0, LAMP_Y, 0]} intensity={0} distance={140} decay={1.4} color="#ffd9a0" />
      </group>
    </group>
  );
}

