import { useMemo } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { BufferAttribute, BufferGeometry, LineSegments, ShaderMaterial } from "three";
import { vis } from "./vis";

const MAX_DROPS = 9000;
const BOX = [90, 60, 90] as const;

/** Rain streaks around the camera. Amount from risk; slant from wind (state). Animated on the GPU. */
export function Rain({ lowQuality }: { lowQuality: boolean }) {
  const camera = useThree((s) => s.camera);
  const lines = useMemo(() => {
    const seeds = new Float32Array(MAX_DROPS * 2 * 3);
    const ends = new Float32Array(MAX_DROPS * 2);
    let s = 12345;
    const r = () => {
      s = (s * 16807) % 2147483647;
      return (s - 1) / 2147483646;
    };
    for (let i = 0; i < MAX_DROPS; i++) {
      const x = r() * BOX[0];
      const y = r() * BOX[1];
      const z = r() * BOX[2];
      for (let k = 0; k < 2; k++) {
        seeds.set([x, y, z], (i * 2 + k) * 3);
        ends[i * 2 + k] = k;
      }
    }
    const g = new BufferGeometry();
    g.setAttribute("position", new BufferAttribute(seeds, 3));
    g.setAttribute("aEnd", new BufferAttribute(ends, 1));
    const m = new ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uWind: { value: 0 },
        uCam: { value: camera.position },
        uOpacity: { value: 0 },
      },
      vertexShader: /* glsl */ `
        attribute float aEnd;
        uniform float uTime; uniform float uWind; uniform vec3 uCam;
        varying float vEnd;
        const vec3 BOX = vec3(${BOX[0].toFixed(1)}, ${BOX[1].toFixed(1)}, ${BOX[2].toFixed(1)});
        void main() {
          vec3 vel = vec3(uWind * 14.0, -38.0, uWind * 4.0);
          vec3 p = mod(position + vel * uTime - uCam, BOX) - BOX * 0.5 + uCam;
          p -= normalize(vel) * aEnd * (1.2 + uWind * 0.8);
          vEnd = aEnd;
          gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0);
        }`,
      fragmentShader: /* glsl */ `
        uniform float uOpacity; varying float vEnd;
        void main() { gl_FragColor = vec4(0.72, 0.78, 0.86, uOpacity * (0.35 + 0.65 * vEnd)); }`,
      transparent: true,
      depthWrite: false,
      fog: false,
    });
    const l = new LineSegments(g, m);
    l.frustumCulled = false;
    return l;
  }, [camera]);

  useFrame(() => {
    const m = lines.material as ShaderMaterial;
    m.uniforms.uTime.value = vis.elapsed;
    m.uniforms.uWind.value = vis.wind;
    m.uniforms.uCam.value = camera.position;
    const amount = Math.max(0, (vis.risk - 0.25) / 0.75);
    const max = lowQuality ? MAX_DROPS / 3 : MAX_DROPS;
    const drops = Math.floor(max * amount);
    lines.geometry.setDrawRange(0, drops * 2);
    lines.visible = drops > 0;
    m.uniforms.uOpacity.value = 0.25 + 0.3 * amount + vis.flash * 0.4;
  });

  return <primitive object={lines} />;
}
