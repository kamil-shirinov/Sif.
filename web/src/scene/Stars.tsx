import { useEffect, useMemo } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { BufferAttribute, BufferGeometry, Points, ShaderMaterial } from "three";
import { vis } from "./vis";

const COUNT = 1400;
const R = 3900;

/** Stars at night (vis.dayFactor, which follows the solar clock and series.market_open), hidden by storm cloud (risk). */
export function Stars() {
  const camera = useThree((s) => s.camera);
  const pts = useMemo(() => {
    const p = new Float32Array(COUNT * 3);
    const m = new Float32Array(COUNT);
    let s = 2024;
    const r = () => {
      s = (s * 16807) % 2147483647;
      return (s - 1) / 2147483646;
    };
    for (let i = 0; i < COUNT; i++) {
      const az = r() * Math.PI * 2;
      const el = Math.asin(0.06 + 0.94 * r()); // denser toward the horizon, none below it
      p[i * 3] = Math.cos(az) * Math.cos(el) * R;
      p[i * 3 + 1] = Math.sin(el) * R;
      p[i * 3 + 2] = Math.sin(az) * Math.cos(el) * R;
      m[i] = Math.pow(r(), 3); // mostly faint, a few bright
    }
    const g = new BufferGeometry();
    g.setAttribute("position", new BufferAttribute(p, 3));
    g.setAttribute("aMag", new BufferAttribute(m, 1));
    const mat = new ShaderMaterial({
      uniforms: { uOpacity: { value: 0 }, uTime: { value: 0 } },
      vertexShader: /* glsl */ `
        attribute float aMag; uniform float uTime; varying float vB;
        void main() {
          vB = (0.35 + 0.65 * aMag) * (0.75 + 0.25 * sin(uTime * (1.5 + aMag * 3.0) + position.x));
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_Position = projectionMatrix * mv;
          gl_PointSize = 1.2 + 2.4 * aMag;
        }`,
      fragmentShader: /* glsl */ `
        uniform float uOpacity; varying float vB;
        void main() {
          float r = length(gl_PointCoord - 0.5) * 2.0;
          float a = smoothstep(1.0, 0.0, r) * vB * uOpacity;
          if (a < 0.01) discard;
          gl_FragColor = vec4(vec3(0.85, 0.9, 1.0) * 1.4, a);
        }`,
      transparent: true,
      depthWrite: false,
      fog: false,
    });
    const points = new Points(g, mat);
    points.frustumCulled = false;
    points.renderOrder = 0;
    return points;
  }, []);
  useEffect(() => () => {
    pts.geometry.dispose();
    (pts.material as ShaderMaterial).dispose();
  }, [pts]);
  useFrame(() => {
    const night = 1 - vis.dayFactor;
    const clear = 1 - Math.min(1, vis.risk * 1.3) * (1 - 0.5 * vis.fairWind);
    const o = night * night * clear * (1 - vis.flash);
    pts.visible = o > 0.01;
    pts.position.set(camera.position.x, 0, camera.position.z);
    const u = (pts.material as ShaderMaterial).uniforms;
    u.uOpacity.value = o;
    u.uTime.value = vis.elapsed;
  });
  return <primitive object={pts} />;
}
