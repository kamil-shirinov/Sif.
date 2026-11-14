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
/** Sky size. The sky is a sphere of radius SKY_SCALE / 2 (225,000) that follows the camera; the far plane (Scene.tsx: CAMERA_FAR) is 2,000,000. */
export const SKY_SCALE = 450_000;
/** Radius of the sky sphere: the camera sits at its centre (it follows the camera), far inside CAMERA_FAR. */
export const SKY_RADIUS = SKY_SCALE / 2;
/** ?sky=0 hides the sky (debugging the black-screen report on Apple GPUs). */
const SKY_ON = (() => {
  try {
    return new URLSearchParams(window.location.search).get("sky") !== "0";
  } catch {
    return true;
  }
})();

/** Replace one shader snippet, and fail loudly in development if three changed it (a silent no-op would undo a fix). */
function patch(src: string, from: string, to: string): string {
  if (!src.includes(from)) {
    console.warn("Sky shader patch did not apply:", from);
    return src;
  }
  return src.replace(from, to);
}

/**
 * NaN-proof the Sky fragment shader. On Apple GPUs acos/asin outside [-1, 1], atan(0, 0), pow() of a negative base and
 * huge values fed to the hash noise give NaN, and a NaN pixel goes black (and spreads through bloom).
 */
function sanitizeSkyShader(src: string): string {
  let f = src;
  f = patch(f, "uniform float cloudScale;", "uniform float cloudScale;\nuniform float uDim;");
  f = patch(
    f,
    "vec3 direction = normalize( vWorldPosition - cameraPosition );",
    "vec3 dirRaw = vWorldPosition - cameraPosition;\n\t\t\tvec3 direction = dirRaw / max( length( dirRaw ), 1e-6 );",
  );
  f = patch(f, "float zenithAngle = acos( max( 0.0, direction.y ) );", "float zenithAngle = acos( clamp( direction.y, 0.0, 1.0 ) );");
  f = patch(f, "float theta = acos( direction.y );", "float theta = acos( clamp( direction.y, -1.0, 1.0 ) );");
  f = patch(f, "float phi = atan( direction.z, direction.x );", "float phi = atan( direction.z, abs( direction.x ) + abs( direction.z ) < 1e-6 ? 1.0 : direction.x );");
  // Near the horizon direction.y -> 0 and the cloud plane projection runs to infinity; the noise of an infinite
  // coordinate is NaN, and mix(x, NaN, 0) is still NaN. The horizon fade hides clouds there anyway.
  f = patch(f, "vec2 cloudUV = direction.xz / ( direction.y * elevation );", "vec2 cloudUV = direction.xz / ( max( direction.y, 0.02 ) * elevation );");
  f = patch(f, "float silver = clamp( 0.51 / pow( 1.49 - cosTheta * 1.4, 1.5 ), 0.0, 3.0 );", "float silver = clamp( 0.51 / pow( max( 1.49 - cosTheta * 1.4, 0.05 ), 1.5 ), 0.0, 3.0 );");
  // Final colour: never negative (the cloud pass subtracts the sun glow, and pow() of a negative in the sRGB
  // transfer is NaN), never NaN or Inf.
  f = patch(
    f,
    "gl_FragColor = vec4( texColor, 1.0 );",
    `vec3 skyC = texColor * uDim;
\t\t\tskyC = vec3( skyC.r >= 0.0 && skyC.r < 1e5 ? skyC.r : 0.0, skyC.g >= 0.0 && skyC.g < 1e5 ? skyC.g : 0.0, skyC.b >= 0.0 && skyC.b < 1e5 ? skyC.b : 0.0 );
\t\t\tgl_FragColor = vec4( skyC, 1.0 );`,
  );
  return f;
}

/**
 * Sky (three.js Sky with its built-in clouds), sun light, fog, storm darkening and horizon haze.
 * risk -> darkness, cloud cover, fog; state -> wind (cloud speed); time of day -> sun.
 */
export function Atmosphere() {
  const { scene, camera } = useThree();

  const sky = useMemo(() => {
    const s = new Sky();
    // three's Sky is a 12-triangle box pinned to the far plane (gl_Position.z = w). Triangles of that box that cross
    // the camera plane clip degenerately on some GPUs (Apple), giving NaN pixels that bloom spreads over the screen.
    // Draw the same material on a finely subdivided sphere instead, well inside the far plane, with normal depth.
    s.geometry.dispose();
    (s as Mesh).geometry = new SphereGeometry(1, 64, 32);
    s.scale.setScalar(SKY_RADIUS);
    // Never cull the sky: it surrounds the camera whatever the orbit, and a culling decision must not drop it.
    s.frustumCulled = false;
    s.visible = SKY_ON;
    const u = s.material.uniforms;
    u.turbidity.value = 4;
    u.rayleigh.value = 2.2;
    u.mieCoefficient.value = 0.004;
    u.mieDirectionalG.value = 0.8;
    u.cloudElevation.value = 0.55;
    u.cloudScale.value = 0.00025;
    // Storm dimming happens inside the sky shader (before tone mapping), so it works in HDR too.
    u.uDim = { value: 1 };
    // Normal depth. The main camera never needs a clamp (the sphere is far inside its far plane), but the water's mirror
    // camera uses an oblique near plane, which drags its far plane in: there, and only for vertices beyond the far
    // plane (always w > 0), depth is held just inside it. Vertices with w <= 0 are never touched, so clipping at the
    // camera plane stays the GPU's ordinary near-plane clip.
    s.material.vertexShader = patch(
      s.material.vertexShader,
      "gl_Position.z = gl_Position.w; // set z to camera.far",
      "if ( gl_Position.w > 0.0 ) gl_Position.z = min( gl_Position.z, gl_Position.w * 0.99999 );",
    );
    s.material.fragmentShader = sanitizeSkyShader(s.material.fragmentShader);
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
    // The sky box rides with the camera, so wherever the camera is (orbit, pan, zoom) it sits at the box's centre:
    // no face or corner can come near it. The sky shader looks along (vertex - camera), which the move does not change.
    sky.position.copy(camera.position);
    const u = sky.material.uniforms;
    // A fair_wind event thins the cloud: the sky reads as if risk had dropped, so the sun breaks through.
    const fw = vis.fairWind;
    const r = vis.risk * (1 - 0.55 * fw);
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
    fog.color.lerp(SUN_WHITE, vis.flash * 0.35 + fw * 0.12);
    fog.density = 0.00035 + 0.0032 * r * r + 0.0006 * r;
    const hz = (haze.material as ShaderMaterial).uniforms;
    hz.uColor.value.copy(fog.color);
    hz.uAmount.value = 0.2 + 0.75 * r;

    if (sunRef.current) {
      const s = sunRef.current;
      s.position.copy(vis.sunDir).multiplyScalar(120);
      s.intensity = 2.4 * vis.dayFactor * (1 - 0.8 * r) + vis.flash * 5 + fw * 1.6 * Math.max(0.3, vis.dayFactor);
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

