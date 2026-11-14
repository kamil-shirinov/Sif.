import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import {
  BackSide,
  Color,
  CylinderGeometry,
  DirectionalLight,
  FogExp2,
  HemisphereLight,
  Mesh,
  NormalBlending,
  ShaderMaterial,
  SphereGeometry,
} from "three";
import { Sky } from "three/examples/jsm/objects/Sky.js";
import { vis } from "./vis";

const FOG_CALM = new Color("#9db2c2");
const FOG_STORM = new Color("#1b232b");
const SUN_WARM = new Color("#ffb070");
const SUN_WHITE = new Color("#fff4e6");
/** Sky radiance scale: keeps the HDR sky under the bloom threshold so only lamp and lightning glow. */
const SKY_BASE = 0.6;

/**
 * Sky (three.js Sky with its built-in clouds), sun light, fog, storm darkening and horizon haze.
 * risk -> darkness, cloud cover, fog; state -> wind (cloud speed); time of day -> sun.
 */
export function Atmosphere() {
  const { scene } = useThree();

  const sky = useMemo(() => {
    const s = new Sky();
    s.scale.setScalar(10000);
    const u = s.material.uniforms;
    u.turbidity.value = 4;
    u.rayleigh.value = 2.2;
    u.mieCoefficient.value = 0.004;
    u.mieDirectionalG.value = 0.8;
    u.cloudElevation.value = 0.55;
    u.cloudScale.value = 0.00025;
    // Storm dimming happens inside the sky shader (before tone mapping), so it works in HDR too.
    u.uDim = { value: 1 };
    s.material.fragmentShader = s.material.fragmentShader
      .replace("uniform float cloudScale;", "uniform float cloudScale;\nuniform float uDim;")
      .replace("gl_FragColor = vec4( texColor, 1.0 );", "gl_FragColor = vec4( texColor * uDim, 1.0 );");
    return s;
  }, []);

  // Storm darkening dome: sits inside the sky box, alpha from risk (and night).
  const dome = useMemo(() => {
    const mat = new ShaderMaterial({
      uniforms: { uDark: { value: 0 }, uTop: { value: new Color("#05080b") }, uHorizon: { value: new Color("#1a2128") } },
      vertexShader: /* glsl */ `
        varying vec3 vDir;
        void main() {
          vDir = normalize(position);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: /* glsl */ `
        uniform float uDark; uniform vec3 uTop; uniform vec3 uHorizon;
        varying vec3 vDir;
        void main() {
          float up = clamp(vDir.y, 0.0, 1.0);
          vec3 c = mix(uHorizon, uTop, smoothstep(0.0, 0.6, up));
          float a = uDark * mix(0.8, 1.0, smoothstep(0.0, 0.4, up));
          gl_FragColor = vec4(c, a);
        }`,
      side: BackSide,
      transparent: true,
      depthWrite: false,
      fog: false,
      blending: NormalBlending,
    });
    const m = new Mesh(new SphereGeometry(4200, 32, 16), mat);
    m.renderOrder = -1;
    m.frustumCulled = false;
    return m;
  }, []);

  // Horizon haze: blends the far sea into the sky so fog has no hard seam.
  const haze = useMemo(() => {
    const mat = new ShaderMaterial({
      uniforms: { uColor: { value: new Color() }, uAmount: { value: 0.3 } },
      vertexShader: /* glsl */ `
        varying float vY;
        void main() {
          vY = position.y;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: /* glsl */ `
        uniform vec3 uColor; uniform float uAmount;
        varying float vY;
        void main() {
          float a = uAmount * (1.0 - smoothstep(-40.0, 420.0, vY));
          gl_FragColor = vec4(uColor, a);
        }`,
      side: BackSide,
      transparent: true,
      depthWrite: false,
      fog: false,
    });
    const m = new Mesh(new CylinderGeometry(3200, 3200, 1400, 48, 1, true), mat);
    m.position.y = 0;
    m.renderOrder = -1;
    m.frustumCulled = false;
    return m;
  }, []);

  const fog = useMemo(() => new FogExp2(FOG_CALM.getHex(), 0.0006), []);
  useEffect(() => {
    scene.fog = fog;
    return () => {
      scene.fog = null;
    };
  }, [scene, fog]);

  const sunRef = useRef<DirectionalLight>(null);
  const hemiRef = useRef<HemisphereLight>(null);
  const tmp = useMemo(() => new Color(), []);

  useFrame(() => {
    const u = sky.material.uniforms;
    const r = vis.risk;
    u.sunPosition.value.copy(vis.sunDir);
    u.time.value = vis.elapsed;
    u.cloudCoverage.value = 0.18 + 0.8 * r;
    u.cloudDensity.value = 0.25 + 0.7 * r;
    u.cloudSpeed.value = 0.00002 + 0.00012 * vis.wind;
    u.turbidity.value = 4 + 11 * r;
    u.rayleigh.value = 2.2 + 0.8 * r;
    u.showSunDisc.value = r < 0.6 ? 1 : 0;

    const night = 1 - vis.dayFactor;
    const dark = Math.min(0.96, 0.85 * r * r + 0.15 * r + 0.3 * night) * (1 - 0.85 * vis.flash);
    u.uDim.value = SKY_BASE * (Math.max(0.03, 1 - dark) + vis.flash * 0.6);
    (dome.material as ShaderMaterial).uniforms.uDark.value = dark * 0.8;

    fog.color.copy(FOG_CALM).lerp(FOG_STORM, Math.min(1, r * 1.1)).multiplyScalar(0.25 + 0.75 * vis.dayFactor);
    fog.color.lerp(SUN_WHITE, vis.flash * 0.35);
    fog.density = 0.00035 + 0.0032 * r * r + 0.0006 * r;
    const hz = (haze.material as ShaderMaterial).uniforms;
    hz.uColor.value.copy(fog.color);
    hz.uAmount.value = 0.2 + 0.75 * r;

    if (sunRef.current) {
      const s = sunRef.current;
      s.position.copy(vis.sunDir).multiplyScalar(120);
      s.intensity = 2.4 * vis.dayFactor * (1 - 0.8 * r) + vis.flash * 5;
      tmp.copy(SUN_WARM).lerp(SUN_WHITE, Math.min(1, vis.sunDir.y * 3));
      s.color.copy(tmp);
    }
    if (hemiRef.current) {
      hemiRef.current.intensity = 0.25 + 0.75 * vis.dayFactor * (1 - 0.6 * r) + vis.flash * 2.5;
    }
  });

  return (
    <>
      <primitive object={sky} />
      <primitive object={dome} />
      <primitive object={haze} />
      <directionalLight ref={sunRef} intensity={2} />
      <hemisphereLight ref={hemiRef} args={["#b8cde0", "#1b2a33", 0.8]} />
    </>
  );
}

