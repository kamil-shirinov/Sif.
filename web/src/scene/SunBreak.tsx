import { useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Color, CylinderGeometry, DoubleSide, Mesh, NormalBlending, ShaderMaterial, Vector3 } from "three";
import { vis } from "./vis";
import { SHIP_LAYOUT } from "./Ship";

const HEIGHT = 420;
const UP = new Vector3(0, 1, 0);
const _dir = new Vector3();

const SUN = new Color(2.6, 2.1, 1.1); // HDR: brighter than the thinned sky, so the column reads
const MOON = new Color(1.0, 1.25, 1.9);

/**
 * A fair_wind event: the cloud opens and a shaft of sunlight falls on the ships (the sky thinning and the
 * brighter sun are in Atmosphere.tsx; the sails filling are in Ship.tsx). The shaft follows the sun's
 * direction by day and falls straight down, pale, at night.
 */
export function SunBreak() {
  const shaft = useMemo(() => {
    const geo = new CylinderGeometry(15, 30, HEIGHT, 32, 1, true);
    geo.translate(0, HEIGHT / 2, 0); // base on the sea, tip toward the sky
    const mat = new ShaderMaterial({
      uniforms: { uOpacity: { value: 0 }, uTint: { value: new Color().copy(SUN) } },
      vertexShader: /* glsl */ `
        varying vec3 vN; varying float vH;
        void main() {
          vN = normalize(normalMatrix * normal);
          vH = position.y / ${HEIGHT.toFixed(1)};
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: /* glsl */ `
        uniform float uOpacity; uniform vec3 uTint;
        varying vec3 vN; varying float vH;
        void main() {
          // Soft edges: the shaft is brightest where the surface faces the camera.
          float face = pow(abs(normalize(vN).z), 1.8);
          float a = uOpacity * face * pow(1.0 - vH, 1.3) * smoothstep(0.0, 0.05, vH + 0.04);
          gl_FragColor = vec4(uTint, a);
        }`,
      transparent: true,
      depthWrite: false,
      blending: NormalBlending,
      side: DoubleSide,
      fog: false,
      toneMapped: false,
    });
    const m = new Mesh(geo, mat);
    m.frustumCulled = false;
    m.renderOrder = 2;
    m.visible = false;
    return m;
  }, []);

  useFrame(() => {
    const fw = vis.fairWind;
    shaft.visible = fw > 0.01;
    if (!shaft.visible) return;
    // By day the shaft leans along the sun; keep it steep enough to read as a column of light.
    const day = vis.dayFactor;
    _dir.copy(vis.sunDir).lerp(UP, 1 - day);
    _dir.y = Math.max(_dir.y, 0.55);
    _dir.normalize();
    shaft.quaternion.setFromUnitVectors(UP, _dir);
    const cx = (SHIP_LAYOUT.prepared.x + SHIP_LAYOUT.unprepared.x) / 2;
    const cz = (SHIP_LAYOUT.prepared.z + SHIP_LAYOUT.unprepared.z) / 2;
    shaft.position.set(cx, 0, cz);
    const u = (shaft.material as ShaderMaterial).uniforms;
    u.uOpacity.value = fw * (0.22 + 0.3 * day);
    u.uTint.value.copy(MOON).lerp(SUN, day);
  });

  return <primitive object={shaft} />;
}
